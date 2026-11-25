# -*- coding: utf-8 -*-
"""Kirara 个性化知识库（Personal Knowledge Base）。

目的：JRVS-7B-1.0.1 容易对用户个人事实产生幻觉（编造 GPA、留学经历等）。
本模块把 knowledge_base.md 作为"权威档案"接入检索链路：
- Markdown 标题结构化分块（保留标题面包屑，不按裸行切碎）
- 向量检索（chromadb 可用时）+ IDF 加权中文 bigram 词法检索（始终可用的兜底）
- 统一 0~1 分数量纲：先打分、再按阈值过滤、最后 TopK 截断
- mtime/size 签名增量重建；稳定 content-hash 文档 ID，杜绝重复灌入
- 向量索引后台构建，构建期间/失败后自动退化为纯词法检索，不阻塞对话

检索结果由 JRVS_Kernel.build_prompt 以"权威事实"区块注入，聊天与 Agent 模式同源复用。
"""
import os
import re
import math
import hashlib
import threading

# ----------------------------------------------------------------------
# 常量
# ----------------------------------------------------------------------
SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(SERVICE_DIR)                       # kirara/
PROJECT_ROOT = os.path.dirname(APP_DIR)                     # LMBrewer/

# 路径解析优先级：显式配置 > kirara 自有副本 > openmaid 共享档案
DEFAULT_PATH_CANDIDATES = [
    os.path.join(APP_DIR, "memories", "knowledge_base.md"),
    os.path.join(PROJECT_ROOT, "openmaid", "memories", "knowledge_base.md"),
]

VECTOR_DB_PATH = os.path.join(APP_DIR, "memories", "kirara_memory", "knowledge_base")
VECTOR_COLLECTION = "kirara_knowledge_base"

MAX_CHUNK_CHARS = 600          # 单个分块目标长度（汉字字符）
MIN_CHUNK_CHARS = 12           # 短于此的纯标题块跳过
DEFAULT_TOP_K = 4
DEFAULT_MIN_SCORE = 0.30

_HEADING_RE = re.compile(r'^(#{1,6})\s*(.+?)\s*#*\s*$')
_CJK_RUN_RE = re.compile(r'[一-鿿]+')
_LATIN_WORD_RE = re.compile(r'[a-z0-9][a-z0-9_.+\-]*')

# 中文疑问/功能词停用表（bigram）。无分词依赖时，这些词在查询里只是脚手架，
# 放任它们参与 IDF 会让"什么/多少/怎么"压过"高考/GPA"这类真正的区分词。
_STOP_BIGRAMS = {
    "什么", "怎么", "怎样", "咋么", "为什么", "为何", "多少", "几个", "是谁",
    "谁啊", "谁吗", "哪里", "哪儿", "哪个", "哪些", "哪种", "哪所", "哪年",
    "哪天", "啥时", "难道", "是否", "能否", "能不能", "可以", "会不会",
    "应该", "需要", "想要", "告诉", "解释", "一下", "请问", "谢谢",
    "我们", "你们", "他们", "她们", "它们", "咱们", "自己", "俺们",
    "这个", "那个", "这些", "那些", "这样", "那样", "这么", "那么",
    "这里", "那里", "这儿", "那儿", "就是", "还是", "或者", "还有",
    "以及", "没有", "有的", "有点", "一些", "一点", "现在", "以前",
    "以后", "之前", "之后", "时候", "时间", "事情", "东西", "地方",
    "样子", "意义", "意思", "知道", "觉得", "感觉", "认为", "以为",
    "看到", "看见", "听过", "听说", "一直", "一定", "已经", "曾经",
    "正在", "马上", "立刻", "突然", "果然", "居然", "竟然", "其实",
    "特别", "非常", "十分", "比较", "相当", "可能", "确实", "真的",
    "是的", "对吗", "好吗", "行吗", "的话", "如果", "假设", "因为",
    "所以", "但是", "不过", "然后", "而且", "并且", "虽然", "尽管",
    "即使", "只要", "只有", "无论", "不管", "关于", "对于", "至于",
    "由于", "因此", "此外", "另外", "同时", "首先", "其次", "最后",
    "最终", "开始", "结束", "进行", "发生", "成为", "得到", "找到",
    "罗的", "里的", "上的", "下的", "似的", "了吗", "了呢", "是不",
    "有什", "有什", "之什", "关于", "了多", "考了", "的生",
    # 寒暄/时间/情绪功能词：语料内虽稀有但不指向任何个人事实，不能当锚点
    "今天", "明天", "昨天", "最近", "心情", "情绪", "开心", "难过",
    "高兴", "么样", "啥样", "你好", "好呀", "好吖", "在吗", "忙吗",
    "累吗", "晚安", "早安", "看看", "讲讲", "说说", "说下", "来着",
    "聊天", "聊聊", "陪我",
}

# 人名/自称：可作为覆盖率权重，但在 query 含其他实体锚点时不能单独作为放行锚点
# （否则"巴里的GPA"会召回所有提到巴里的杂文，"绮罗的生日"会召回全部产品文档）
_NAME_TERMS = {"巴里", "barry", "molynton", "绮罗", "kirara", "主人", "kiraras"}

# 功能字集合：两个字都属于功能字的 bigram 视为功能词自动停用。
# 解决跨词 bigram 漏网问题（"是什"←是什么、"有没"←有没有搞错，
# 它们在语料中偶然稀有，IDF 虚高会冒充实体锚点）。
_FUNC_CHARS = set(
    "的了是不在有著过地得吗呢吧啊呀哦嘛呗喽哈么什怎咋啥谁哪几多为何"
    "否能会要想可以应该需这那些个把被让给对向从到朝往于就也还都只"
    "才又再已曾正上下里外中内前后或而且但虽若因虽故则及与和或乃是"
    "我你他她它们咱们俺您"
)


def _extract_terms(text):
    """中文按字 bigram、英文/数字按词切分；无第三方依赖。"""
    terms = []
    for run in _CJK_RUN_RE.findall(text or ""):
        if len(run) == 1:
            terms.append(run)
        else:
            terms.extend(run[i:i + 2] for i in range(len(run) - 1))
    for word in _LATIN_WORD_RE.findall((text or "").lower()):
        if len(word) >= 2:
            terms.append(word)
    return terms


class KnowledgeBase:
    """knowledge_base.md 的加载、结构化分块与混合检索。线程安全。"""

    def __init__(self, path=None, top_k=DEFAULT_TOP_K, min_score=DEFAULT_MIN_SCORE):
        self._lock = threading.RLock()
        self._configured_path = path          # 用户显式指定（可为 None → 自动解析）
        self._resolved_path = None
        self._signature = None                # (path, mtime, size)

        self.top_k = self._clamp_top_k(top_k)
        self.min_score = self._clamp_min_score(min_score)

        # 索引数据
        self._chunks = []                     # [{"title", "body", "text", "terms":set}]
        self._idf = {}                        # term -> idf weight
        self._anchor_idf = 999.0             # 稀有锚点词 IDF 阈值（建索引后重算）
        self._available = False

        # 向量后端
        self._vector_ok = False               # 探测/构建成功后置 True
        self._vector_tried = False            # 是否已启动过后台构建
        self._client = None
        self._collection = None

    # ------------------------------------------------------------------
    # 配置
    # ------------------------------------------------------------------
    @staticmethod
    def _clamp_top_k(value):
        try:
            value = int(value)
        except (TypeError, ValueError):
            value = DEFAULT_TOP_K
        return max(1, min(value, 8))

    @staticmethod
    def _clamp_min_score(value):
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = DEFAULT_MIN_SCORE
        return max(0.0, min(value, 1.0))

    def configure(self, path=None, top_k=None, min_score=None):
        """运行时更新配置。路径变化会使签名失效，下次检索自动重建。"""
        with self._lock:
            if top_k is not None:
                self.top_k = self._clamp_top_k(top_k)
            if min_score is not None:
                self.min_score = self._clamp_min_score(min_score)
            norm_path = (path or "").strip()
            new_path = norm_path if norm_path else None
            if new_path != self._configured_path:
                self._configured_path = new_path
                self._signature = None
                self._available = False

    def _resolve_path(self):
        candidates = []
        if self._configured_path:
            p = self._configured_path
            candidates.append(p if os.path.isabs(p) else os.path.join(PROJECT_ROOT, p))
        candidates.extend(DEFAULT_PATH_CANDIDATES)
        for candidate in candidates:
            if candidate and os.path.isfile(candidate):
                return candidate
        return None

    @property
    def available(self):
        with self._lock:
            self._ensure_index_locked()
            return self._available

    # ------------------------------------------------------------------
    # Markdown 解析与分块
    # ------------------------------------------------------------------
    def _parse_markdown(self, raw_text):
        """按 ATX 标题切成 (标题面包屑, 正文) 单元。"""
        units = []
        stack = []                            # [(level, title)]
        current_title = "（文档导言）"
        current_lines = []

        def flush():
            body = "\n".join(current_lines).strip()
            if body or current_title != "（文档导言）":
                units.append((current_title, body))

        for raw_line in raw_text.splitlines():
            m = _HEADING_RE.match(raw_line)
            if m:
                flush()
                level = len(m.group(1))
                title = m.group(2).strip()
                while stack and stack[-1][0] >= level:
                    stack.pop()
                stack.append((level, title))
                current_title = " / ".join(t for _, t in stack)
                current_lines = []
            else:
                current_lines.append(raw_line.rstrip())
        flush()
        return units

    def _split_long_body(self, body):
        """长正文贪心分组：不拆表格行/代码块，超长单行硬切。"""
        blocks = []
        buf = []
        buf_len = 0
        in_fence = False

        def push_buf():
            nonlocal buf, buf_len
            if buf:
                blocks.append("\n".join(buf).strip())
                buf = []
                buf_len = 0

        for line in body.splitlines():
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
                buf.append(line)
                buf_len += len(line)
                if not in_fence and buf_len >= MAX_CHUNK_CHARS:
                    push_buf()
                continue

            hard = len(line) > MAX_CHUNK_CHARS * 1.6 and not in_fence
            if hard:
                push_buf()
                for i in range(0, len(line), MAX_CHUNK_CHARS):
                    blocks.append(line[i:i + MAX_CHUNK_CHARS].strip())
                continue

            if buf_len + len(line) + 1 > MAX_CHUNK_CHARS and not in_fence:
                push_buf()
            buf.append(line)
            buf_len += len(line) + 1
            if not line.strip() and not in_fence and buf_len >= MAX_CHUNK_CHARS * 0.6:
                push_buf()
        push_buf()
        return [b for b in blocks if b.strip()]

    def _build_chunks(self, raw_text):
        chunks = []
        for title, body in self._parse_markdown(raw_text):
            leaf = title.split(" / ")[-1].strip()
            body = body.strip()
            # 空正文节：叶子标题自身即内容（本文档大量事实直接写在 ### 标题行里，
            # 例如"### Barry...高考以535分..."，绝不能丢弃）
            if not body:
                body = leaf
            pieces = [body] if len(body) <= MAX_CHUNK_CHARS else self._split_long_body(body)
            for piece in pieces:
                piece = piece.strip()
                if len(piece) < MIN_CHUNK_CHARS:
                    continue
                text = f"【{title}】\n{piece}"
                chunks.append({
                    "title": title,
                    "body": piece,
                    "text": text,
                    "terms": set(_extract_terms(text)),
                })
        return chunks

    # ------------------------------------------------------------------
    # 索引生命周期
    # ------------------------------------------------------------------
    def _current_signature(self, path):
        try:
            stat = os.stat(path)
            return path, stat.st_mtime_ns, stat.st_size
        except OSError:
            return None

    def _ensure_index_locked(self):
        """签名变化时重新加载与重建词法索引，并异步构建向量索引。"""
        path = self._resolve_path()
        if not path:
            self._available = False
            self._resolved_path = None
            return False

        signature = self._current_signature(path)
        if self._available and signature == self._signature and path == self._resolved_path:
            return True
        if not signature:
            self._available = False
            return False

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw_text = f.read()
        except OSError as e:
            print(f"[KB] 读取知识库失败 {path}: {e}")
            self._available = False
            return False

        chunks = self._build_chunks(raw_text)
        idf = self._build_idf(chunks)
        self._chunks = chunks
        self._idf = idf
        self._resolved_path = path
        self._signature = signature
        self._available = bool(chunks)
        self._vector_ok = False
        self._vector_tried = False
        print(f"[KB] 已加载 {os.path.basename(path)}：{len(chunks)} 个知识分块，词法索引就绪")

        if self._available:
            threading.Thread(target=self._build_vector_index, args=(list(chunks),),
                             daemon=True).start()
        return self._available

    def _build_idf(self, chunks):
        n = len(chunks)
        doc_freq = {}
        for chunk in chunks:
            for term in chunk["terms"]:
                doc_freq[term] = doc_freq.get(term, 0) + 1
        idf = {term: math.log((n + 1) / (df + 1)) + 0.5 for term, df in doc_freq.items()}
        # "稀有锚点"阈值：df<=8 的词才算有区分度的锚点；只命中常见词的分块不予放行
        self._anchor_idf = math.log((n + 1) / 9.0) + 0.5 if n else 999.0
        return idf

    # ------------------------------------------------------------------
    # 向量后端（chromadb；失败静默退化为词法）
    # ------------------------------------------------------------------
    def _init_vector_store(self):
        try:
            import chromadb
        except Exception:
            return None
        try:
            # 与 jrvs.py 既有约定一致：sentence_transformers 可用时用它，否则交给 chroma 默认 EF
            embedding_function = None
            try:
                import chromadb.utils.embedding_functions as ef
                try:
                    from sentence_transformers import SentenceTransformer  # noqa: F401
                    embedding_function = ef.SentenceTransformerEmbeddingFunction(
                        model_name="all-MiniLM-L6-v2")
                except Exception:
                    embedding_function = None
            except Exception:
                embedding_function = None

            client = chromadb.PersistentClient(path=VECTOR_DB_PATH)
            collection = client.get_or_create_collection(
                name=VECTOR_COLLECTION,
                embedding_function=embedding_function,
            )
            return client, collection
        except Exception as e:
            print(f"[KB] 向量存储初始化失败，使用纯词法检索: {e}")
            return None

    def _build_vector_index(self, chunks_snapshot):
        """后台线程：清空旧文档并灌入当前分块。任何失败都永久降级到词法。"""
        with self._lock:
            if self._vector_tried:
                return
            self._vector_tried = True
            store = self._init_vector_store()
            if store is None:
                return
            client, collection = store
            try:
                existing = collection.get()
                if existing and existing.get("ids"):
                    collection.delete(ids=existing["ids"])
                ids, docs, metas = [], [], []
                for i, chunk in enumerate(chunks_snapshot):
                    ids.append("kb_" + hashlib.md5(
                        chunk["text"].encode("utf-8")).hexdigest()[:16])
                    docs.append(chunk["text"])
                    metas.append({"title": chunk["title"], "idx": i})
                # 分批添加，避免单次请求过大
                batch = 128
                for start in range(0, len(ids), batch):
                    collection.add(
                        documents=docs[start:start + batch],
                        metadatas=metas[start:start + batch],
                        ids=ids[start:start + batch],
                    )
                self._client = client
                self._collection = collection
                self._vector_ok = True
                print(f"[KB] 向量索引构建完成（{len(ids)} 分块），混合检索已启用")
            except Exception as e:
                self._vector_ok = False
                print(f"[KB] 向量索引构建失败，回退纯词法检索: {e}")

    def _vector_scores(self, query, fetch_k):
        """返回 {chunk_idx: 0~1 相似度}；与 Hippo 相同的 L2→相似度换算。"""
        if not self._vector_ok or self._collection is None:
            return {}
        try:
            res = self._collection.query(
                query_texts=[query],
                n_results=min(fetch_k, max(1, self._collection.count() or 1)),
                include=["metadatas", "distances"],
            )
            scores = {}
            metas = (res.get("metadatas") or [[]])[0]
            dists = (res.get("distances") or [[]])[0]
            for meta, dist in zip(metas, dists):
                idx = meta.get("idx")
                if isinstance(idx, int) and 0 <= idx < len(self._chunks):
                    scores[idx] = max(0.0, min(1.0, 1.0 - float(dist) / 2.0))
            return scores
        except Exception as e:
            print(f"[KB] 向量检索异常，本轮仅用词法: {e}")
            return {}

    # ------------------------------------------------------------------
    # 词法打分（IDF 加权 bigram/词覆盖率，0~1）
    # ------------------------------------------------------------------
    def _lexical_scores(self, query):
        """IDF 加权的 query 词覆盖率（0~1）。

        - 停用表中的功能/疑问 bigram 不参与；
        - 语料中完全不存在的词权重为 0（跨词边界噪声 bigram 只稀释分母，无匹配价值）；
        - 整句原文命中给 1.15 倍加成（封顶 1）。
        """
        raw_terms = _extract_terms(query)
        weighted = []
        for term in raw_terms:
            if term in _STOP_BIGRAMS:
                continue
            # 双字均为功能字（且均为汉字）的跨词 bigram 自动停用
            if (len(term) == 2 and _CJK_RUN_RE.fullmatch(term)
                    and term[0] in _FUNC_CHARS and term[1] in _FUNC_CHARS):
                continue
            weighted.append((term, self._idf.get(term, 0.0)))
        # IDF 平方加权：让"高考/GPA/托福"这类稀有实体词主导总分，
        # 避免"巴里/大学"等高频词稀释覆盖率。分母只计语料内出现过的词。
        total_weight = sum(w * w for _, w in weighted if w > 0)
        if total_weight <= 0:
            return {}

        # query 中若存在"非人名的稀有锚点"（如 GPA、高考、生日、原料），
        # 则人名锚点不能单独放行候选块，避免召回只提到巴里/绮罗的无关杂文。
        has_subject_anchor = any(
            w >= self._anchor_idf and term not in _NAME_TERMS
            for term, w in weighted
        )

        # 身份类提问（"巴里是谁？""介绍一下绮罗"）或极短的纯人名 query：
        # 人名直接作为锚点——即便人名在语料中 df 偏高达不到稀有锚点 IDF。
        compact_query = re.sub(
            r'[\s，。！？、~～·…—\-_!?.,:;：；""''（）()\[\]【】]+',
            '', query or '').lower()
        identity_query = bool(re.search(r'(是谁|是谁呀|是谁啊|什么人|何人|谁是|介绍一下|你了解|了解你)', query or '')) \
            or len(compact_query) <= 4

        scores = {}
        for idx, chunk in enumerate(self._chunks):
            hit = 0.0
            has_anchor = False
            distinct_hits = 0
            name_hit = False
            for term, w in weighted:
                if w > 0 and term in chunk["terms"]:
                    hit += w * w
                    distinct_hits += 1
                    if term in _NAME_TERMS:
                        name_hit = True
                        if identity_query:
                            has_anchor = True
                    if w >= self._anchor_idf:
                        if not (has_subject_anchor and term in _NAME_TERMS):
                            has_anchor = True
            # 放行条件：稀有锚点命中；或含人名且至少命中 2 个语料内有效词
            # （覆盖"绮罗是什么模型驱动的"这类多概念 query：基本信息块无"驱动"
            # 但同时命中"绮罗+模型"，不能因缺一个稀有词被误杀）。
            if not has_anchor and name_hit and distinct_hits >= 2:
                has_anchor = True
            if hit <= 0 or not has_anchor:
                continue
            score = hit / total_weight
            if compact_query and len(compact_query) >= 3 and compact_query in chunk["text"].lower():
                score = min(1.0, score * 1.15)
            scores[idx] = min(1.0, score)
        return scores

    # ------------------------------------------------------------------
    # 对外 API
    # ------------------------------------------------------------------
    def retrieve(self, query, top_k=None, min_score=None):
        """检索与 query 相关的权威知识片段。

        返回 [{"title", "content", "score"}]，按分数降序；
        流程：打分（向量与词法取大者）→ 阈值过滤 → TopK 截断。
        """
        top_k = self._clamp_top_k(self.top_k if top_k is None else top_k)
        min_score = self._clamp_min_score(
            self.min_score if min_score is None else min_score)

        with self._lock:
            if not self._ensure_index_locked():
                return []
            query = (query or "").strip()
            if not query:
                return []

            lex = self._lexical_scores(query)
            vec = self._vector_scores(query, fetch_k=top_k * 4)

            # 统一 0~1 分数量纲下的加权融合：词法精确匹配主导（0.65），
            # 向量补充同义改写（0.35）。按"实际生效的权重"归一化——某一路对该
            # 候选缺席时不惩罚另一路（向量未就绪/未命中时词法仍保持原分量纲）。
            w_lex, w_vec = 0.65, 0.35
            merged = {}
            lex_backed = {}
            for idx in set(lex) | set(vec):
                lx = lex.get(idx, 0.0)
                vv = vec.get(idx, 0.0)
                denom = (w_lex if lx > 0 else 0.0) + (w_vec if vv > 0 else 0.0)
                merged[idx] = (w_lex * lx + w_vec * vv) / denom if denom else 0.0
                lex_backed[idx] = lx > 0

            # 纯向量候选（无词法锚点佐证）提高门槛：弱中文向量模型对闲聊的
            # 语义噪声相似度普遍在 0.6~0.71，真正强语义近邻才允许 >0.72 放行
            vec_only_floor = max(min_score, 0.72)
            ranked = sorted(
                ((score, idx) for idx, score in merged.items()
                 if score >= (min_score if lex_backed[idx] else vec_only_floor)),
                key=lambda item: item[0],
                reverse=True,
            )

            hits = []
            for score, idx in ranked[:top_k]:
                chunk = self._chunks[idx]
                hits.append({
                    "title": chunk["title"],
                    "content": chunk["body"],
                    "score": round(score, 4),
                })
            return hits

    def status(self):
        """供 /api/kirara/knowledge/status 与诊断使用。"""
        with self._lock:
            self._ensure_index_locked()
            path = self._resolved_path or self._resolve_path()
            return {
                "available": self._available,
                "path": path,
                "chunks": len(self._chunks) if self._available else 0,
                "backend": "hybrid_chroma" if self._vector_ok else "lexical",
                "top_k": self.top_k,
                "min_score": self.min_score,
            }
