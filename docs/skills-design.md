# Kirara 技能与自动化系统设计文档

> 状态：**设计阶段，暂未实现**  
> 创建日期：2026-09-17  
> 决策记录：技能执行模型=三者全支持、自动化后端=Blockly+规则引擎、依赖管理=用户自行 pip install

---

## 1. 背景与目标

### 1.1 现状
- 当前 `options.json.skills` 字段存储纯文本提示词数组，仅作为 system prompt 注入
- 无外部代码能力、无图形化编程、无依赖管理

### 1.2 设计目标
将"扩展 Kirara 能力"分为两条独立轨道，服务不同用户群体：

| 轨道 | 目标用户 | 编程方式 | 编辑位置 | 执行模型 |
|---|---|---|---|---|
| **技能 (Skills)** | 极客 / 开发者 | Python 文件 + import lib | 客户端**外部** IDE | tool / prompt / hook |
| **自动化 (Automations)** | 一般用户 | 图形化块编程 (Blockly) | 客户端**内部** | 规则引擎 |

### 1.3 设计原则
1. **能力隔离**：技能与自动化互不依赖，可独立启用
2. **安全优先**：技能代码沙箱执行；自动化块词汇受限
3. **零自动安装**：依赖由用户在项目 venv 中手动 `pip install`
4. **热重载可选**：不引入 watchdog，提供手动刷新按钮
5. **复用现有基础设施**：技能 hook 复用 agent_shell 的审批/超时/黑名单机制

---

## 2. 整体架构

```
kirara/
├── skills/                          # 极客模式：外部 .py 技能文件目录
│   ├── README.md                    # 技能开发说明
│   ├── translator.py                # 示例：翻译技能
│   ├── weather_query.py              # 示例：天气查询
│   └── ...
├── memories/
│   ├── options.json                  # 保留通用配置
│   └── automations.json             # 新增：Blockly workspace JSON
├── services/
│   ├── skill_loader.py              # 新增：技能扫描/注册/执行
│   └── automation_engine.py          # 新增：规则引擎
└── static/
    └── blockly/                     # 新增：Blockly 离线打包
        ├── blockly.min.js
        ├── blocks/
        └── msg/zh.js
```

---

## 3. 技能系统设计（外部编程）

### 3.1 技能文件格式

每个 `.py` 文件通过模块 docstring 声明 manifest，普通 Python 语法即可：

```python
"""
name: 翻译助手
description: 多语言互译，自动检测源语言
version: 1.0.0
author: Barry
dependencies: [deep_translator]          # 缺失时拒绝注册并提示
trigger: tool                            # tool | prompt | hook
risk: low                                # low | medium | high（影响审批策略）
enabled: true                            # 是否注册到运行时
"""

def execute(input: str, context: dict) -> dict:
    """
    统一入口签名。
    - input: 用户输入字符串或 LLM tool_call 参数（已 JSON parse）
    - context: 运行上下文，含 user_message / session_id / persona 等
    返回 dict，结构按 trigger 不同而不同。
    """
    from deep_translator import GoogleTranslator
    result = GoogleTranslator(source='auto', target='zh').translate(input)
    return {"output": result, "metadata": {"engine": "google"}}
```

### 3.2 Manifest 字段约定

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `name` | string | ✅ | 显示名（≤50 字符） |
| `description` | string | ✅ | 一句话描述（≤200 字符） |
| `version` | string | ❌ | 语义化版本号 |
| `author` | string | ❌ | 作者 |
| `dependencies` | string[] | ❌ | Python 包名列表 |
| `trigger` | enum | ✅ | `tool` / `prompt` / `hook` |
| `risk` | enum | ❌ | `low` / `medium` / `high`，默认 `low` |
| `enabled` | bool | ❌ | 默认 `true` |
| `hook_events` | string[] | ❌ | 仅 trigger=hook 时有效：`pre_message` / `post_response` / `on_session_start` |

### 3.3 三种执行模型

#### 3.3.1 `trigger: tool` — Agent 工具调用
- 技能注册为 OpenAI 兼容的 function calling 工具
- LLM 自主决定何时调用，参数通过 JSON schema 传递
- 复用现有 `jrvs.py` Agent 模式的工具注册机制
- 适用于：翻译、查询、计算、API 调用等"被调用方"

**注册流程**:
1. `skill_loader` 扫描 `skills/*.py`
2. 解析 manifest，提取 `execute` 函数签名生成 JSON schema
3. 调用 `jrvs_kernel.register_tool(name, schema, handler)`
4. LLM 在 Agent 模式下可调用

**执行流程**:
1. LLM 发起 tool_call
2. `skill_loader` 在沙箱中执行 `execute(input, context)`
3. 结果回传给 LLM 继续对话

#### 3.3.2 `trigger: prompt` — System prompt 注入
- 技能内容（manifest 下方所有文本）作为提示词片段注入 system prompt
- 不实际执行代码，仅影响 LLM 行为
- 适用于：角色设定、风格指令、知识背景

**实现**:
- `jrvs.py` 的 `resolve_persona_system` 读取所有 `enabled` 且 `trigger=prompt` 的技能
- 按顺序拼接，控制总长度（<2000 tokens）
- 与现有 persona system prompt 共存

#### 3.3.3 `trigger: hook` — 消息拦截器
- 技能在消息收发的特定阶段被回调
- 可改写消息、注入上下文、终止流程

**Hook 事件**:
| 事件 | 触发时机 | 可执行操作 |
|---|---|---|
| `pre_message` | 用户消息进入 LLM 前 | 改写消息、注入上下文、阻止该次发送 |
| `post_response` | LLM 回复生成后、展示前 | 改写回复、追加后处理 |
| `on_session_start` | 会话首次激活时 | 初始化状态、预加载资源 |

**Handler 签名**:
```python
def on_pre_message(message: str, context: dict) -> dict:
    return {"message": message, "continue": True, "extra_context": ""}
```

### 3.4 依赖管理

**策略**：用户自行 `pip install` 到项目 venv

**实现细节**:
1. `skill_loader` 扫描时通过 `importlib.util.find_spec` 检测依赖是否可用
2. 缺失依赖的技能：
   - 标记为 `dependency_missing`
   - 不注册到运行时
   - 选项面板显示红色警告 + 安装命令提示
3. **不自动安装**，避免供应链风险

**用户工作流**:
```bash
# 项目根目录
pip install deep_translator
# 重启 Kirara 或点击「重新加载」
```

### 3.5 安全沙箱

复用现有 `agent_shell` 模式的安全机制：

| 维度 | 策略 |
|---|---|
| **执行隔离** | `subprocess.run` 在独立进程执行，主进程不污染 |
| **超时** | 默认 10s，可在 manifest 中覆盖（上限 30s） |
| **import 白名单** | 允许标准库 + 项目已安装包；禁用 `subprocess`/`os.system`/`shutil.rmtree` 等危险 API |
| **文件访问** | 限定项目根目录（复用 `agent_workdir` 配置） |
| **网络** | 默认允许（翻译/查询类技能需要） |
| **审批** | `risk=high` 的技能首次调用时弹审批；`risk=low` 直接执行 |
| **黑名单** | 复用 `agent_shell` 的命令黑名单（rm -rf / 格式化 / 注册表等） |

### 3.6 热重载

**不引入 watchdog**，避免后端复杂度：

1. **启动扫描**：服务启动时扫描 `skills/` 目录
2. **手动刷新**：选项面板「🔄 重新加载技能」按钮，调用 `/api/kirara/skills/reload`
3. **文件变更检测**：记录每个 .py 的 mtime，刷新时仅重新加载变更文件

### 3.7 技能 API 端点

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/kirara/skills` | 列出所有技能（含状态：enabled/missing_dep/error） |
| POST | `/api/kirara/skills/reload` | 重新扫描目录并重载 |
| POST | `/api/kirara/skills/<id>/toggle` | 启用/停用某技能 |
| GET | `/api/kirara/skills/<id>/source` | 返回 .py 源码（供前端查看） |
| POST | `/api/kirara/skills/<id>/test` | 手动触发执行测试（仅 tool/prompt 类型） |

---

## 4. 自动化系统设计（图形化编程）

### 4.1 Blockly 集成

**版本**：Blockly v11+（MIT 协议）  
**打包方式**：离线打包到 `/static/blockly/`，不依赖 CDN

**前端集成**:
```html
<!-- kirara.html 中新增 -->
<script src="/static/blockly/blockly.min.js"></script>
<script src="/static/blockly/msg/zh.js"></script>
<div id="blockly-div" style="height: 480px;"></div>
```

### 4.2 块库设计（MVP）

#### 4.2.1 触发器块（Triggers）
| 块 | 参数 | 说明 |
|---|---|---|
| `当消息包含` | 关键词 | 用户消息包含指定关键词时触发 |
| `当消息匹配正则` | 正则模式 | 正则匹配时触发 |
| `每次启动` | - | 会话开始时触发 |
| `当人设切换为` | persona | 切换到指定人设时触发 |

#### 4.2.2 条件块（Conditions）
| 块 | 参数 | 说明 |
|---|---|---|
| `如果上下文包含` | 关键词 | 检查近期对话上下文 |
| `如果时间段在` | 起止时间 | 当前时间在指定区间 |
| `如果技能已启用` | 技能名 | 检查某技能状态 |

#### 4.2.3 动作块（Actions）
| 块 | 参数 | 说明 |
|---|---|---|
| `回复文本` | 文本模板 | 直接回复（不调用 LLM） |
| `注入 system 提示` | 提示文本 | 临时注入本次对话 |
| `调用技能` | 技能名 + 参数 | 调用已注册的 tool/prompt 技能 |
| `设置变量` | 变量名 + 值 | 保存到会话上下文 |
| `等待` | 秒数 | 延时动作 |

#### 4.2.4 变量块
- `获取变量` / `设置变量` / `用户输入` / `当前时间`

### 4.3 规则引擎

**编译产物**：Blockly workspace → JSON 规则数组，**不生成 Python 代码**

**规则结构**:
```json
{
  "id": "rule_<ts>",
  "name": "自动翻译英文",
  "enabled": true,
  "trigger": {
    "type": "message_contains",
    "params": {"keyword": "翻译:"}
  },
  "conditions": [
    {"type": "time_in_range", "params": {"start": "09:00", "end": "22:00"}}
  ],
  "actions": [
    {"type": "call_skill", "params": {"skill": "translator", "input": "${message.body}"}},
    {"type": "reply", "params": {"text": "${skill.output}"}}
  ]
}
```

**执行流程**:
1. 每条用户消息进入时，遍历 `enabled` 规则
2. 匹配 trigger → 检查 conditions → 依次执行 actions
3. 任一 action 返回 `reply` 则跳过 LLM 直接回复
4. 无匹配规则则正常进入 LLM 对话

**变量插值**：`${message.body}` / `${skill.output}` / `${var.xxx}` / `${time.now}`

### 4.4 存储

**单独文件**：`kirara/memories/automations.json`

```json
{
  "version": "1.0",
  "rules": [...],
  "blockly_workspace_xml": "...",  // 保留原始 workspace 以便重新编辑
  "last_modified": "2026-09-17 12:00:00"
}
```

**不存入 `options.json`**：避免 Blockly XML 污染配置文件，且自动化可独立备份/分享。

### 4.5 自动化 API 端点

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/kirara/automations` | 返回所有规则 |
| POST | `/api/kirara/automations` | 保存 workspace（含 XML + 编译后规则） |
| POST | `/api/kirara/automations/<id>/toggle` | 启用/停用单条规则 |
| POST | `/api/kirara/automations/test` | 模拟输入测试规则匹配 |

---

## 5. 前端 UI 设计

### 5.1 选项面板结构调整

```
选项
├── ⚙️ 基本设置
├── 👤 用户信息
├── 📊 用量管理
├── 🧩 技能管理         # 改造
│   ├── 📂 外部技能     # 新增子标签
│   └── 🔌 自动化       # 新增子标签（替换原"技能管理"内容）
└── ℹ️ 关于Kirara
```

### 5.2 外部技能子面板

```
┌─────────────────────────────────────────┐
│ 外部技能                    [🔄 重新加载] │
├─────────────────────────────────────────┤
│ 扫描目录: kirara/skills/                │
│                                         │
│ ┌─────────────────────────────────────┐│
│ │ 🟢 翻译助手          [tool] [low]   ││
│ │ 多语言互译，自动检测源语言           ││
│ │ 依赖: deep_translator ✓              ││
│ │ [查看源码] [测试] [启用/停用]         ││
│ └─────────────────────────────────────┘│
│ ┌─────────────────────────────────────┐│
│ │ 🔴 天气查询          [tool] [high]  ││
│ │ ⚠️ 缺失依赖: requests                ││
│ │ 运行: pip install requests           ││
│ └─────────────────────────────────────┘│
│                                         │
│ 📖 技能开发文档                         │
└─────────────────────────────────────────┘
```

### 5.3 自动化子面板

```
┌─────────────────────────────────────────┐
│ 自动化                                  │
├─────────────────────────────────────────┤
│ Blockly 工作区 (480px 高)               │
│ ┌─────────────────────────────────────┐│
│ │  [当消息包含] → [调用技能] → [回复]  ││
│ │                                     ││
│ │  工具箱: 触发器/条件/动作/变量       ││
│ └─────────────────────────────────────┘│
│ [▶ 测试] [💾 保存]                      │
│                                         │
│ 已保存规则:                             │
│ ☑ 自动翻译英文 (当消息包含"翻译:")      │
│ ☐ 夜间静音 (如果时间段在 22:00-08:00)   │
└─────────────────────────────────────────┘
```

---

## 6. 安全策略总结

| 层级 | 技能 (Skills) | 自动化 (Automations) |
|---|---|---|
| **代码执行** | 沙箱 subprocess + 超时 + import 白名单 | 无代码执行，规则引擎纯匹配 |
| **网络** | 默认允许 | 无网络操作 |
| **文件** | 限定项目根 | 无文件操作 |
| **审批** | high risk 首次审批 | 无需审批（块词汇受限） |
| **依赖** | 用户手动安装 | 无依赖 |
| **权限提升** | 禁用 sudo/os.system | N/A |

---

## 7. 实施阶段规划

### Phase 1：技能系统骨架
- [ ] `services/skill_loader.py`：目录扫描 + manifest 解析
- [ ] 沙箱执行器（复用 `agent_shell` 安全机制）
- [ ] `trigger: tool` 注册到 `jrvs.py` Agent 工具
- [ ] `/api/kirara/skills` 系列 API
- [ ] 前端「外部技能」子面板
- [ ] `skills/README.md` 开发文档

### Phase 2：技能 trigger 扩展
- [ ] `trigger: prompt` 注入 `resolve_persona_system`
- [ ] `trigger: hook` 实现 `pre_message` / `post_response` / `on_session_start`
- [ ] Hook 在 `lmbrew.py` 消息处理流程中接入

### Phase 3：自动化系统
- [ ] Blockly 离线打包到 `/static/blockly/`
- [ ] 自定义块库（触发器/条件/动作/变量）
- [ ] `services/automation_engine.py` 规则引擎
- [ ] `automations.json` 存储与 API
- [ ] 前端 Blockly 编辑器子面板
- [ ] 替换现有「技能管理」UI 为「自动化」

### Phase 4：打磨
- [ ] 技能/自动化市场分享机制（导入/导出 JSON）
- [ ] 技能调试控制台
- [ ] 自动化规则版本控制
- [ ] 性能监控与统计

---

## 8. 开放问题（待实施时决策）

1. **技能 ID 命名**：用文件名还是 manifest 中的 name 字段？倾向文件名（避免重名）
2. **Blockly 块的「调用技能」**：仅支持 `trigger=tool` 技能？还是也支持 prompt 类型？
3. **Hook 链顺序**：多个 hook 技能同时启用时如何排序？按注册顺序还是 priority 字段？
4. **自动化规则冲突**：多条规则同时匹配时，是全部执行还是首条优先？
5. **技能失败处理**：tool 调用失败时，回传错误给 LLM 还是静默降级？
6. **审计日志**：技能/自动化执行是否记录到日志文件？粒度如何？

---

## 9. 兼容性

- **现有 `options.json.skills` 字段**：迁移到 `automations.json`，旧字段保留但只读，下次启动自动迁移
- **现有 UI「技能管理」**：Phase 3 完成后整体替换为「自动化」子面板
- **现有 Agent 工具**：不受影响，技能作为新工具补充注册

---

## 10. 参考

- [Blockly 官方文档](https://developers.google.com/blockly/)
- [OpenAI Function Calling 协议](https://platform.openai.com/docs/guides/function-calling)
- 现有 `agent_shell` 安全机制：`lmbrew.py` L679-L698
- 现有 persona system prompt：`jrvs.py` `resolve_persona_system`
