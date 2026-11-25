# Hippo 记忆系统诊断与修复记录

> **日期**：2026-09-22
> **背景**：用户反馈 Kirara 对英文长文处理异常、牛顿法回答完全错误（答成"调模型+梯度下降"），并在换话题时记忆串味。

---

## 一、故障现象

1. **英文作文被拒答**：发一篇正常的 AI agent 英文作文，Kirara 回复 `唔...这个话题让绮罗罗有点不知所措呢，请换一个话题吧`（`CATEGORY_YELLOW` 拒答模板）
2. **跨话题串味**：问牛顿法，Kirara 先答"评价一篇 AI 的文章"（上轮话题残留）
3. **内容答非所问**：纠正后回答"调用模型作为初始猜测，梯度下降逐步迭代优化"——这根本不是牛顿法
4. **旧对话残留**：所有对话堆进 `sessions/default.json`，不隔离

---

## 二、根因定位（4 层叠加）

### Layer 1：安全过滤器子串匹配误判（已修复）

**位置**：[jrvs.py:1970-1971](file:///e:/LMBrewer/kirara/services/jrvs.py) `ContentSafetySystem.detect`

**原代码**：`if keyword.lower() in text_lower:` 纯子串匹配

**误判案例**：违禁词 `hanging`（上吊）命中了英文作文里的 `changing`（`c**hanging** landscape`）
- `score = 0.35 >= 0.3` → 被判为 `self_harm` 类别 → 拒答模板
- 其他可命中的子串陷阱：`ass`→`class`/`pass`/`assign`，`pot`→`potential`/`approach`，`tit`→`title`，`cum`→`circumstances`，`hell`→`hello`

**修复**：英文关键词改用 `\b` 词边界正则，中文保持子串匹配。预编译存 `self._ascii_patterns`。

---

### Layer 2：ChromaDB include 参数不兼容（已修复）

**位置**：[jrvs.py:1103](file:///e:/LMBrewer/kirara/services/jrvs.py) `_vector_search`

**原代码**：`include=["documents", "metadatas", "distances", "ids"]`

**故障**：ChromaDB 0.11.x 不支持 `ids` 作为 query 的 include 项（只在 `.get()` 时返回 ids），抛出异常后 `retrieve_long_term_memory` 静默失败 → 回退到无意义的 `_hook_fallback`。**向量搜索全链路等于坏掉**。

**修复**：移除 `include=["documents", "metadatas", "distances"]` 中的 `"ids"`。

---

### Layer 3：话题转移检测算法报废（已修复）

**位置**：[jrvs.py:1012-1065](file:///e:/LMBrewer/kirara/services/jrvs.py) `detect_topic_shift`

**原算法**：中文 bigram 2-gram 相似度，阈值 0.2

**故障**：
- 英文作文 + 中文历史 → bigram 命中 `的`/`了`/`和` 等通用字对
- 实测 `detect_topic_shift("解释一下牛顿法求解的过程吧")` 相似度 = **1.0**
- 话题转移检测**永远不触发** → working memory 不截断 → 新旧话题混在一起

**修复**：完全重写为：
1. **关键词优先硬触发**（"换话题"/"别管"等 → 立即转移，不受历史条数限制）
2. **bigram recall**（不是 Jaccard，避免长历史分母稀释）：`命中 bigram 数 / query bigram 数`，阈值 **0.2**
3. 只对比**用户历史输入**（排除助手固定措辞如"好的主人sama"）

---

### Layer 4：无 session 隔离（已修复）

**前端根因**：[kiraraGenCore.js:767-772](file:///e:/LMBrewer/kirara/js/kiraraGenCore.js) `callJRVSWebSocket` fetch body **不带 `session_id`** → 后端 fallback 到 `default_session_id="default"` → 所有对话堆进 `sessions/default.json`

**后端根因**：Hippo 三层记忆（short_term / long_term / ChromaDB）都没有 session awareness
- `short_term_memory` 是全局列表，buffer.txt 里所有话题混排
- `_convert_to_long_term` 清空整个列表，不区分 session
- `detect_topic_shift` 读全局 `short_term_memory[-10:]`，不知道哪个属于当前对话

**修复**：
1. 前端：`initChatSessionId()` 生成 `chat_<ts>_<rand>` 存 localStorage，fetch body 带 `session_id`
2. 后端 Hippo 全链路加 session_id：
   - `add_short_term_memory(..., session_id=sid)` → 条目加 `[sid:xxx]` 标记
   - `_convert_to_long_term(force, session_id)` → 按 session 过滤，转换后只清当前 session 的
   - `force_convert_memory(keep_recent, session_id)` → 同理
   - `detect_topic_shift(..., session_id=sid)` → 只对比当前 session 用户历史
   - `retrieve_long_term_memory(..., session_id=sid)` → ChromaDB metadata 存 session_id（暂未 where 过滤，跨 session 回忆是合理需求）

---

### Layer 5（隐藏）：循环恶化链

模型回答错（牛顿法→梯度下降）→ 被 `add_short_term_memory` 记录 → 触发 `_convert_to_long_term` → 错误回答进 ChromaDB → 下次 `_vector_search` 命中 → 错误内容塞回 prompt → 模型跟着复制。**ChromaDB 修复后这条链才真正断开**。

---

## 三、脏数据清理

- 删除 `sessions/default.json`（重启后自动重建空文件）
- 删除 `memories/buffer.txt`（重启后自动重建）
- ChromaDB 删 1 条"牛顿-拉夫逊/梯度下降"脏 entry（id=`doc_e32108ea_1790045263`）

---

## 四、修复后测试矩阵（8/8 通过）

| 测试 | 期望 | 结果 |
|------|------|------|
| ContentSafety：正常英文 AI 作文 | safe=True | ✅ |
| ContentSafety：自残关键词 | safe=False | ✅ |
| ContentSafety：changing/类 passing 的普通词 | safe=True | ✅ |
| ChromaDB 向量搜索 | hits>0 不 crash | ✅ |
| detect_topic_shift：延续话题（chat_aaa） | shift=False | ✅ |
| detect_topic_shift：关键词换话题（chat_bbb） | shift=True, kw=True | ✅ |
| detect_topic_shift：完全不同话题（chat_aaa→牛顿法） | shift=True | ✅ |
| session 隔离：chat_aaa 记忆条数 = 2 | ✅ | ✅ |
| session 隔离：chat_bbb 记忆条数 = 1 | ✅ | ✅ |

---

## 五、后续待做（Follow-up）— 2026-09-23 全部完成 ✅

| # | 项 | 状态 | 落地说明 |
|---|----|------|----------|
| 1 | **前端"新对话"按钮** | ✅ 已完成 | 聊天区右上角新增胶囊按钮 `#new-chat-btn`（毛玻璃粉色风格，≤768px 自适应缩小）。`startNewChat()`：中止进行中的生成 → 生成新 `chat_xxx` sid 写 localStorage / `window.chatSessionId` → 清空 `conversationHistory` 与聊天区 → 插入新问候。`callJRVSWebSocket` 记录 `requestSid`，SSE/JSON 两分支在写入历史前比对 sid，被中止的旧会话迟到结果直接丢弃，不串进新会话 |
| 2 | **sentence_transformers 安装** | ✅ 已完成 | torch 2.8.0（CPU wheel，MiniLM 嵌入 CPU 足够；Ollama GPU 推理走自带 CUDA 不受影响）+ sentence-transformers 5.1.2 + `all-MiniLM-L6-v2`（经 hf-mirror.com 下载，`HF_ENDPOINT` 已持久化）。ChromaDB 初始化代码本就内置 `SentenceTransformerEmbeddingFunction`，导入成功即自动启用，无需改码。另修复 force-reinstall torch 导致的 pandas C 扩展 DLL 损坏（`--force-reinstall --no-deps pandas==2.3.3`） |
| 3 | **ChromaDB where 过滤** | ✅ 已完成 | `retrieve_long_term_memory` 抽出 `_hybrid_search`；`_vector_search` / `_keyword_search` 新增 `session_id` 参数，分别下推到 `collection.query(where=...)` 与 `collection.get(where=...)`。策略：**当前 session 优先，无命中自动回退跨 session 全局检索**——既做会话隔离，又保留长期事实知识的跨对话复用；无 sid 的旧 entry 走全局回退仍可命中 |

---

## 六、2026-09-23 环境依赖对齐记录

torch 重装后 pip 报 11 条版本冲突。反向依赖梳理后统一对齐（Python 3.9.7 全局环境）：

| 包 | 旧版本 | 新版本 | 冲突来源 |
|----|--------|--------|----------|
| httpx | 0.25.2 | 0.28.1 | chromadb / ollama 要求 ≥0.27；starlette extra 要求 <0.29 |
| PyYAML | 5.4.1 | 6.0.3 | chromadb 要求 ≥6.0.0 |
| rich | 9.13.0 | 13.9.4 | chromadb / typer / tyro 要求更高版本；升级同时消除 typing-extensions<4 冲突 |
| fsspec | 2025.10.0 | 2025.3.0 | datasets 4.0.0 要求 ≤2025.3.0 |
| MarkupSafe | 3.0.3 | 2.1.5 | gradio 4.44.1 要求 ~=2.0 |
| websockets | 15.0.1 | 12.0 | gradio-client 要求 <13.0 |
| pydantic | 2.13.4 | 2.10.6 | llamafactory 要求 ≤2.10.6（pydantic-core 连带 2.27.2） |

附带清理：

- **卸载 `pnpm` 1.0.14**：无任何包依赖它，却死钉 PyYAML<6 / rich<10 / click<8，与 chromadb 物理互斥，是冲突无法消除的根因
- **清理 pip 中断残留目录**：`~aml` / `~arkupsafe` / `~orch`（268MB 旧 torch）/ `~ttpx(-dist-info)` / `~ydantic_core` / `~andas`
- `py -m pip check` → **No broken requirements found**
- 重启 jrvs.py 后，启动日志应显示 `sentence_transformers 导入成功` 与 `ChromaDB 长期记忆库初始化成功，嵌入后端: sentence_transformers`
