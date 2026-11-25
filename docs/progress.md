# Kirara 扩展系统迁移进度跟踪

> **用途**：跨对话跟进，新会话开始时优先读取此文档了解进度
> **最后更新**：2026-09-17
> **当前阶段**：技能 prompt 注入已实施 / 自动化设计中 / OpenMaid UI 废弃 Phase A 完成

---
## 一、三大工作线总览

| 工作线 | 状态 | 完成度 | 关键文件 |
|---|---|---|---|
| 技能管理（极客模式） | ✅ UI 交付 + ✅ prompt 注入 | UI 100% / 后端 100% / 注入 100% | [skills-design.md](file:///e:/LMBrewer/kirara/docs/skills-design.md) |
| 自动化系统（图形化） | 🔄 设计完成，⏸️ 暂不实施 | 设计 100% / 实施 0% | [skills-design.md](file:///e:/LMBrewer/kirara/docs/skills-design.md) §4 |
| OpenMaid UI 废弃 | 🚧 Phase A 完成 | 1/5 phases | 本文档 §三 |

---

## 二、技能管理系统（已交付）

### 2.1 已完成代码

**后端** [lmbrew.py](file:///e:/LMBrewer/lmbrew.py)
- [L1024-L1027](file:///e:/LMBrewer/lmbrew.py#L1024-L1027)：`DEFAULT_KIRARA_OPTIONS` 新增 `skills: []` 字段
- [L1068-L1088](file:///e:/LMBrewer/lmbrew.py#L1068-L1088)：`POST /api/kirara/options` 加入 skills 校验（数组/名称必填/长度截断/非法过滤）
- 复用现有 `load_kirara_options` / `save_kirara_options` 持久化机制

**前端 HTML** [kirara.html](file:///e:/LMBrewer/kirara/kirara.html)
- [L537](file:///e:/LMBrewer/kirara/kirara.html#L537)：选项卡新增 `🧩 技能管理`
- [L785-L796](file:///e:/LMBrewer/kirara/kirara.html#L785-L796)：`options-skills-panel`（列表+添加按钮）
- [L1035-L1068](file:///e:/LMBrewer/kirara/kirara.html#L1035-L1068)：技能编辑弹窗 `skill-editor-modal`
- [L1640-L1642](file:///e:/LMBrewer/kirara/kirara.html#L1640-L1642)：tab 切换调用 `renderSkillsList()`

**前端 JS** [kiraraGenCore.js](file:///e:/LMBrewer/kirara/js/kiraraGenCore.js)
- [L3063](file:///e:/LMBrewer/kirara/js/kiraraGenCore.js#L3063)：`kiraraOptions.skills: []` 默认值
- [L3591-L3592](file:///e:/LMBrewer/kirara/js/kiraraGenCore.js#L3591-L3592)：`bindOptionsEvents` 调用 `bindSkillEditorEvents()`
- [L3595-L3841](file:///e:/LMBrewer/kirara/js/kiraraGenCore.js#L3595-L3841)：技能管理函数集（render/open/close/save/delete/toggle/bind）

**样式** [kirara.css](file:///e:/LMBrewer/kirara/css/kirara.css)
- [L5620-L5961](file:///e:/LMBrewer/kirara/css/kirara.css#L5620-L5961)：技能卡片 + 编辑弹窗 + 移动端适配

### 2.2 数据结构

`e:\LMBrewer\kirara\memories\options.json` 的 `skills` 字段：

```json
"skills": [
    {
        "id": "skill_<ts>_<rand>",
        "name": "翻译助手",
        "description": "多语言互译",
        "content": "提示词内容...",
        "enabled": true,
        "created_at": "2026-09-17 12:00:00"
    }
]
```

### 2.3 prompt 注入实施（trigger=prompt 模式，✅ 2026-09-17）

实现 [skills-design.md](file:///e:/LMBrewer/kirara/docs/skills-design.md) §3.3.2：把 `options.json.skills` 中 `enabled=True` 的技能 `content` 拼接到 system prompt。

**新增辅助函数** [lmbrew.py](file:///e:/LMBrewer/lmbrew.py)
- [L1044-L1045](file:///e:/LMBrewer/lmbrew.py#L1044-L1045)：常量 `SKILLS_PROMPT_MAX_CHARS = 8000`（约 2000 tokens 上限）
- [L1047-L1092](file:///e:/LMBrewer/lmbrew.py#L1047-L1092)：`build_system_prompt_with_skills(persona_key)` 函数
  - 调用 `resolve_persona_system` 获取 SFT 触发词（"JRVS"/"Kirara"）或 None（native）
  - 从 `load_kirara_options()['skills']` 过滤 `enabled=True` 的技能
  - 按顺序拼接 content，超出 `SKILLS_PROMPT_MAX_CHARS` 时截断并打印日志
  - 与现有 persona system prompt 共存：触发词保持首位以维持 SFT 人设识别，技能指令以 `[技能指令]` 分隔符追加
  - native 人设 + 有技能时：直接以 `[技能指令]` 开头（无 SFT 触发词前缀）

**三处调用点替换**（原 `resolve_persona_system(persona_key)` → `build_system_prompt_with_skills(persona_key)`）
- [L566](file:///e:/LMBrewer/lmbrew.py#L566)：`POST /api/kirara/chat` 流式对话端点
- [L775](file:///e:/LMBrewer/lmbrew.py#L775)：`POST /api/kirara/agent` Agent 模式端点
- [L860](file:///e:/LMBrewer/lmbrew.py#L860)：`POST /api/kirara/agent/approve` 审批恢复端点

**验证状态**：✅ Python 语法 / ✅ 冒烟测试 4 用例（kirara/jrvs/native/unknown persona × enabled/disabled 过滤）

### 2.4 当前剩余限制

- skills **未注册为 Agent 工具**（trigger=tool 模式未实施）
- skills **未实现 hook 拦截**（trigger=hook 模式未实施）
- 现有 UI 数据结构无 `trigger` 字段，当前所有 skills 隐含为 `trigger=prompt` 类型
- 真正的"外部 .py 技能文件 + 三种 trigger"按 [skills-design.md](file:///e:/LMBrewer/kirara/docs/skills-design.md) §3 设计待实施
- 现有 UI 中的"技能管理"在 Phase 3 完成后将改名为"自动化"并嵌入 Blockly

### 2.5 原生 SkillManager 技能系统（独立存在，待统一）

**现状**：项目里已存在一套独立的"原生技能系统"，与 §2.3 的 prompt 注入系统**完全分离**。

**位置与核心**
- 目录：[e:\LMBrewer\kirara\services\skills\](file:///e:/LMBrewer/kirara/services/skills/)（与 rigard 镜像）
- 核心：[skills.py](file:///e:/LMBrewer/kirara/services/skills/skills.py) — `SkillManager` 单例 + `SkillRegistry` + `BaseSkill` 抽象类
- 4 个内置技能：
  - `readFile` — 文件读取（[readFile.py](file:///e:/LMBrewer/kirara/services/skills/readFile.py)）
  - `screenshotRecognition` — 截图识别
  - `webSearch` — 网络搜索（[webSearch.py](file:///e:/LMBrewer/kirara/services/skills/webSearch.py)）
  - `areYouUnderTrouble` — 烦恼检测

**触发与集成**
- 触发方式：`trigger_keywords` 关键词匹配（`SkillExecutor.auto_execute(query)`），**不是** LLM function calling
- 集成点：[jrvs.py L2346-L2373](file:///e:/LMBrewer/kirara/services/jrvs.py#L2346-L2373) `_bridge_skill_manager()` 在 JRVS_Kernel 启动时把这 4 个技能桥接到 `otherAI` orchestrator 的 `skill_registry`

**与 prompt 注入系统的关系**
- **互不影响**：prompt 注入只改 system prompt，不覆盖/禁用/重复注册原生技能
- **UI 不可见**：「技能管理」UI 只读 `options.json.skills`，看不到原生 4 个 Python 类技能
- **潜在重复**：原生 `webSearch` 走代码执行；若用户在 UI 写一个"网络搜索"prompt 技能，会双重影响模型行为

### 2.6 原生技能处理决策（2026-09-17）

**决策**：等实施 [skills-design.md](file:///e:/LMBrewer/kirara/docs/skills-design.md) §3.3.1 的 `trigger=tool` 模式后，再把 4 个原生技能重新封装为符合新 manifest 格式的 `.py` 技能文件，统一纳入 `options.json.skills` 管理；原生 `SkillManager` 系统届时可废弃。

**短期不动**：4 个原生技能继续在代码层运行，新 prompt 注入系统不干涉。

**trigger=tool 实施时的工作清单**
1. 设计新 manifest 格式（docstring manifest + `execute(input, context)` 签名，见设计文档 §3.1）
2. 实现 `skill_loader`：扫描 `kirara/skills/*.py`，解析 manifest，提取 `execute` 签名生成 JSON schema
3. 复用 [agent/tools.py](file:///e:/LMBrewer/kirara/services/agent/tools.py) 的工具注册机制，把技能注册为 OpenAI 兼容 function calling 工具
4. 把 4 个原生技能迁移到新格式：
   - `readFile.py` → 新 manifest 格式
   - `screenshotRecognition.py` → 新 manifest 格式
   - `webSearch.py` → 新 manifest 格式
   - `areYouUnderTrouble.py` → 新 manifest 格式
5. 在「技能管理」UI 增加 trigger 类型切换（prompt/tool/hook），支持编辑 tool 类技能
6. 废弃 `kirara/services/skills/` 目录与 `_bridge_skill_manager()` 桥接代码（jrvs.py L2346）
7. 评估是否同步处理 `rigard/services/skills/` 镜像目录

---

## 三、OpenMaid UI 废弃迁移

### 3.0 决策与原则

**目标**：废弃 `e:\LMBrewer\openmaid\openmaid.html` 及其前端资源，所有功能融合进 Kirara 选项面板。后端 API（`lmbrew.py` L154-L438 的 `/api/ai/openmaid/*` 路由）保留不动。

**原则**：
1. 后端 API 不动（已与 Kirara 共享同一 Flask 服务）
2. `openmaid/services/` Python 代码保留作为后端依赖
3. `openmaid/memories/knowledge_base.md` 被 Kirara 知识库引用，**不能删**
4. 迁移逐 Phase 推进，每 Phase 独立可验证

### 3.1 Phase A — 通讯接口配置 UI（✅ 已完成 2026-09-17）

**迁移内容**：iMessage + QQ 网关配置 UI 从 OpenMaid 迁入 Kirara 选项面板

**改动**：

[kirara.html](file:///e:/LMBrewer/kirara/kirara.html)
- [L537](file:///e:/LMBrewer/kirara/kirara.html#L537)：新增 tab `📡 通讯接口`
- [L786-L883](file:///e:/LMBrewer/kirara/kirara.html#L786-L883)：`options-comm-panel`（网关+iMessage+QQ 三卡片）
- [L1738-L1741](file:///e:/LMBrewer/kirara/kirara.html#L1738-L1741)：tab-switch 加 `comm` 分支

[kiraraGenCore.js](file:///e:/LMBrewer/kirara/js/kiraraGenCore.js)
- [L3592](file:///e:/LMBrewer/kirara/js/kiraraGenCore.js#L3592)：`bindOptionsEvents` 内调用 `bindCommPanelEvents()`
- [L3846-L4294](file:///e:/LMBrewer/kirara/js/kiraraGenCore.js#L3846-L4294)：通讯接口函数集（网关 4 函数 + iMessage 5 函数 + QQ 6 函数 + 辅助函数）

[kirara.css](file:///e:/LMBrewer/kirara/css/kirara.css)
- [L5963-L6206](file:///e:/LMBrewer/kirara/css/kirara.css#L5963-L6206)：通讯接口粉紫主题样式

**关键适配**：后端实际字段为 `{socketUrl, token, sessionKey, language}`（非模板假设的 model/base_url/api_key），UI 已按真实字段适配

**已对接 API**：
- GET/POST `/api/ai/openmaid/config/gateway`
- GET `/api/ai/openmaid/gateway/snapshot`
- GET `/api/ai/openmaid/comm/imessage/{status,check}`
- POST `/api/ai/openmaid/comm/imessage/{connect,disconnect,send}`
- GET `/api/ai/openmaid/comm/qq/{status,check,friends,groups}`
- POST `/api/ai/openmaid/comm/qq/{connect,disconnect,send,send_group}`

**验证状态**：✅ Python 语法 / ✅ JS 语法 / ⚠️ 未浏览器实测（建议手动验证一次表单读写）

### 3.2 Phase B — 调试与日志查看（⏸️ 待执行）

**迁移内容**：OpenMaid 的 🐞 调试 + 📜 日志面板

**预估工作**：
- 新增 `options-debug-panel`（日志流 + 调试控制台）
- 对接后端日志 API（需检查 lmbrew.py 是否已有，否则需补端点）
- 前端 JS：实时日志滚动 + 过滤 + 清空

**依赖**：需先确认 lmbrew.py 是否有日志查询 API，若无则需新增

### 3.3 Phase C — 实例/智能体/节点评估与迁移（⏸️ 待执行）

**迁移内容**：OpenMaid 的 🌐 实例 / 💿 可用智能体 / 🔗 节点

**前置任务**：先评估这些功能是否真有用户价值
- 若有用 → 迁移 UI
- 若无用 → 同时删除后端 API（lmbrew.py 对应路由）

**待确认问题**：
- 实例管理具体指什么（LLM 推理实例？Ollama 实例？）
- 节点功能边界（P2P 节点？算力节点？）
- 智能体列表与 Kirara 现有 Agent 模式关系

### 3.4 Phase D — 删除 OpenMaid 前端资源（⏸️ 待执行）

**删除范围**：
- `e:\LMBrewer\openmaid\openmaid.html`
- `e:\LMBrewer\openmaid\js\` 整个目录
- `e:\LMBrewer\openmaid\css\` 整个目录
- `e:\LMBrewer\openmaid\sprites\` 评估是否被 Kirara 引用

**保留**：
- `openmaid/services/` Python 代码
- `openmaid/memories/knowledge_base.md`（Kirara 知识库依赖）
- `openmaid/memories/gateway_config.json`（通讯配置）

**迁移**：
- `openmaid/memories/kirara_training_data.json` → `kirara-transformer/`
- `openmaid/memories/generate_training_data.py` → `kirara-transformer/`

**前置条件**：Phase B + C 完成，确认无 UI 引用残留

### 3.5 Phase E — 用户信息合并（⏸️ 待执行）

**当前状态**：两套用户信息并存
- `openmaid/memories/user_info.json`（333 bytes）
- `kirara/memories/user.json`（284 bytes）

**待决策**：
- 合并方向（OpenMaid → Kirara 或反之）
- 字段差异对比
- 迁移脚本是否需要

**前置条件**：Phase D 完成，确认 OpenMaid 代码不再引用 user_info.json

---

## 四、自动化系统（设计中，暂不实施）

详见 [skills-design.md](file:///e:/LMBrewer/kirara/docs/skills-design.md) §4

**当前状态**：设计完成 100%，实施 0%

**关键决策**：
- 执行后端：Blockly + 规则引擎（不生成 Python 代码）
- 存储：`kirara/memories/automations.json`（独立文件，不污染 options.json）
- Blockly 版本：v11+，离线打包到 `/static/blockly/`

**触发条件**：等技能系统 Phase 1-2 完成后再启动（自动化可调用技能）

---

## 五、跨对话跟进 checklist

新会话开始时，按此顺序确认进度：

### 5.1 快速核对（5 分钟）

1. 读取本文档 §一 总览表
2. 读取 [skills-design.md](file:///e:/LMBrewer/kirara/docs/skills-design.md) §1-§4
3. 检查 `e:\LMBrewer\kirara\memories\options.json` 是否含 `skills` 字段
4. Grep `lmbrew.py` 确认 `OPENMAID_USER_INFO_PATH` 等常量仍存在（Phase E 前不删）

### 5.2 待执行任务优先级

| 优先级 | 任务 | 依赖 |
|---|---|---|
| P0 | Phase A 浏览器实测（手动） | 无 |
| P1 | 技能系统 Phase 1（外部 .py 技能骨架） | 无 |
| P2 | 技能系统 Phase 2（hook trigger） | Phase 1 |
| P2 | OpenMaid Phase B（调试/日志 UI） | 确认后端 API |
| P3 | OpenMaid Phase C（实例/智能体评估） | Phase B |
| P3 | 自动化系统 Phase 3（Blockly 集成） | 技能 Phase 1-2 |
| P4 | OpenMaid Phase D（删除前端资源） | Phase B+C |
| P4 | OpenMaid Phase E（用户信息合并） | Phase D |

### 5.3 关键约束（来自 project_memory）

- Kirara 自称"绮罗罗"，禁用"Kirara Model-C IoT"
- 禁止修改辅助后端（jrvs.py 除外）
- Kirara 前端核心在 `kiraraGenCore.js`
- TTS 服务返回 base64 WAV
- 人设映射：`jrvs`→system JRVS、`kirara`→system Kirara、`native`→无注入
- 所有代码改动需通过 Python/JS 语法检查 + API 冒烟测试 + 浏览器测试
- 前端人设/语音面板在 ≤768px 纵向堆叠
- API 端点必须包含：`POST /api/kirara/tts`、`GET /api/kirara/tts/voices`、`GET /api/kirara/personas`
- 短期记忆 `e:/lmbrewer/kirara/memories/buffer.txt`，长期记忆 `mem.md`，记忆压缩用加权法不用大模型

---

## 六、文件索引

### 6.1 核心代码
- 后端入口：[lmbrew.py](file:///e:/LMBrewer/lmbrew.py)
- 前端 HTML：[kirara.html](file:///e:/LMBrewer/kirara/kirara.html)
- 前端 JS：[kiraraGenCore.js](file:///e:/LMBrewer/kirara/js/kiraraGenCore.js)
- 前端 CSS：[kirara.css](file:///e:/LMBrewer/kirara/css/kirara.css)
- LLM 核心：[jrvs.py](file:///e:/LMBrewer/jrvs.py)

### 6.2 配置与数据
- Kirara 选项：[kirara/memories/options.json](file:///e:/LMBrewer/kirara/memories/options.json)
- Kirara 用户：[kirara/memories/user.json](file:///e:/LMBrewer/kirara/memories/user.json)
- 短期记忆：[kirara/memories/buffer.txt](file:///e:/LMBrewer/kirara/memories/buffer.txt)
- 长期记忆：[kirara/memories/mem.md](file:///e:/LMBrewer/kirara/memories/mem.md)
- OpenMaid 网关配置：[openmaid/memories/gateway_config.json](file:///e:/LMBrewer/openmaid/memories/gateway_config.json)
- OpenMaid 用户：[openmaid/memories/user_info.json](file:///e:/LMBrewer/openmaid/memories/user_info.json)
- OpenMaid 知识库（不可删）：[openmaid/memories/knowledge_base.md](file:///e:/LMBrewer/openmaid/memories/knowledge_base.md)

### 6.3 文档
- 本文档：[progress.md](file:///e:/LMBrewer/kirara/docs/progress.md)
- 技能与自动化设计：[skills-design.md](file:///e:/LMBrewer/kirara/docs/skills-design.md)
- 项目规范：[project_memory.md](file:///c:/Users/10663/.trae-cn/memory/projects/-e-LMBrewer--p2-c99da371d200558aafbd/project_memory.md)

---

## 七、变更历史

| 日期 | 变更 | 会话标识 |
|---|---|---|
| 2026-09-16 | 添加生成停止机制（send 按钮双态） | session 6aa9ee |
| 2026-09-16 | Agent token 计数与压缩（PR-2） | session 6aaa3d |
| 2026-09-17 | 技能管理 UI（基础版，纯提示词存储） | 当前会话 |
| 2026-09-17 | 技能与自动化系统设计文档 | 当前会话 |
| 2026-09-17 | OpenMaid Phase A：通讯接口 UI 迁移 | 当前会话 |
| 2026-09-17 | 创建跨对话跟进文档 | 当前会话 |
| 2026-09-17 | 技能 prompt 注入实施（build_system_prompt_with_skills，三处调用替换） | 当前会话 |
| 2026-09-17 | 盘点原生 SkillManager 技能系统，决策等 trigger=tool 实施后统一 | 当前会话 |
