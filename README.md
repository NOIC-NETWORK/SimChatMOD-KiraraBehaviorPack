# Kirara 行为包（SimChat MOD）

![Kirara-Logo](sprites/logos/kirara-2.png)

![televideo](sprites/logos/televideo-sponsors.png)

>> **仓库定位**：这是 Kirara 行为包的源码仓库，是 [SimChat](https://github.com/NOIC-NETWORK/SimChat) 的一个 MOD，不是独立应用，也没有可安装的发行包；脱离 SimChat 宿主无法单独运行。
>
> **当前状态：开发中，本仓库仅作备份。** 功能未完成、接口会变，不代表发布，也不提供兼容性承诺或技术支持。

# Companion, Copilot, Command Post.

## 搭子——独有*个性化记忆库，成为用户的情感搭子。

## 副驾驶——题不会做？丢给她！旅游攻略？丢给她！赶DDL？丢给她！**

## 指挥部——直接在 IM 软件下令，从而远端操控设备。基于 IoT 的 Skill System 还在规划中。***

(*) 弗若斯特·沙利文，《关于大中华区 AI Agent 产品的调研报告》，2026 年。（编的）

(**) 指产品有助于解决用户生活中的常见问题。

(***) 尚未实现。

## 友情链接

### 巴里君GitHub号

[https://github.com/NOIC-NETWORK](https://github.com/NOIC-NETWORK)

### TeleVideo自研模型仓库

[https://ollama.com/TeleVideo-AI](https://ollama.com/TeleVideo-AI)

### TeleVideo 官方网站

[https://www.tvehub.com/ai](https://www.tvehub.com/ai)

### 巴里君国内唯一联系方式

[mailto:1066344121@qq.com](mailto:1066344121@qq.com)

## 这个仓库是什么

- SimChat 的 `skill` 类型 MOD：`manifest.json` 中 `id=kirara`、`layer=mod`、ABI `simchat-mod/2`，入口 `kirara_entry:register`，前端入口 `web/index.html`。
- 提供：女仆人格与系统提示词、桌宠窗口、WAP 前端资源、`kirara.trivia` 方块、装备 `orbiter` 的只读地图（AI 实例）、MOD 专属对话卡片。
- 自带一套 JRVS 内核与 Flask 服务（`services/`）：桌宠窗口与 Kirara 自己的聊天页跑的是它；SimChat 侧的对话卡片走宿主自己的推理与会话链路，两者不共享会话。
- 运行期依赖见 `requirements.txt`（flask、chromadb、sentence-transformers、pyttsx3 等），以及本地 Ollama 上的 JRVS 模型。

## 怎么跑起来

1. 先按 SimChat 仓库的说明把宿主跑起来。
2. 把本仓库放进宿主的 MOD 目录（`.simchat/mods/kirara`），由宿主加载器读取 manifest 后加载；启用后才会出现桌宠与 Kirara 专属对话卡片。
3. 记忆库（ChromaDB 向量库）不入库：首次初始化内核时由 `services/init_memory.py` 自动创建目录骨架，也可以手动执行 `py services/init_memory.py`。
4. 默认模型是本地 JRVS（`televideo-ai/JRVS-7B-1.2.2:latest`，`keep_alive=30m`）；模型没就绪时相关能力不可用，但不影响宿主本身。
5. 想改人设或主题：提示词在 `prompts/maid.txt`，主题在 `css/theme.css`，参数在 `manifest.json` 的 `config` 段。

## Kirara 是谁

- 姓名：绮罗（Kirara）/ 绮罗星芽衣（Mei Kirahoshi，看完动漫后自取的名称）
- 性别：女
- 身份：AI Copilot，Chief Maid of Barry Molynton.
- 阵营：TeleVideo Inc. / Geek Department
- 生日：3 月 3 日（日本的女儿节，有摆放人形的习俗）
- 身高：70cm
- 体重：无（意识体）/ 相当于一台冰箱（机器人）
- 性格：活泼甜美，充满想象力，会看到人类看不到的“闪闪发亮”的东西；也有因为理解不了用户的 Prompt 而冒失的时候，但总是表现出很能理解用户心情的样子。
- 开发者：Barry Molynton（TeleVideo Inc. & Enterprise. 的创始人、总裁与 CTO）

**技术底盘**：JRVS（Joint Ratiocination Visual System，读作 Jarvis）AI 引擎，使用 Python 编写；Ollama 推理后端（CUDA 独显全层卸载）；ChromaDB 双库（cognitive 知识档案库 + hippo 长期记忆库）；Sentence Transformer 嵌入（all-MiniLM-L6-v2）；Flask Web 服务。

**模型**：JRVS-7B-1.2.2 "Puff"（Qwen3-8B SFT 双人格，Q4_K_M 约 4.9GB），通过 `system="Kirara"` / `system="JRVS"` 切换人格，不需要额外的 think 参数。这是行为包声明的默认本地主模型（`manifest.json` → `config.models`）。

## 为什么默认用本地 JRVS

- **人格原生**：`system="Kirara"` 直接触发女仆人设，`system="JRVS"` 切到冷静助手人格，不必另拼一套长提示词。
- **适合 24 小时常驻**：桌宠与 IM 入口要求随时在线，Ollama 以 `keep_alive=30m` 驻留，日常对话不必每次冷启动，也不依赖外部服务。
- **本地推理**：CUDA 全层卸载、`num_ctx=16384`、Q8 KV 缓存，日常对话与润色都在本机完成，普通私聊内容不出网。
- **润色与编排**：双系统里 System 2 负责草稿与反思，System 1（JRVS）把草稿润色成带表情和口头禅的女仆语气；轻量本地模型再承担“这句话是闲聊还是任务”的分诊，复杂任务交给 Orbiter 或更强的云端模型。润色已在 `services/jrvs.py` 的 `DeepThinkingEngine` 中实现；编排路由仍是规划项，`chat_with_router_details` 的 `routing_info` 目前固定为 `null`。

参考硬件：带独显的近年游戏本（开发机为 RTX 5060 Laptop 8GB，37/37 层全 GPU 卸载）。行为包只在 `manifest.json` 的 `config.models` 里声明了这一定位与推理配置，尚未把 JRVS 接成 SimChat 的宿主服务或 ToolSpec。

## 记忆：Hippo 分层记忆

采用 **Hierarchical Memory Architecture（分层记忆架构）**，模拟人类大脑的记忆机制：

```plain text
用户输入
↓
工作记忆（短期，40 条消息 / 20 轮对话）
│   ├─ 存储：JSON 文件持久化，session 隔离
│   ├─ 压缩：每 40 条触发海马体压缩，压缩后保留最近 10 条
│   └─ 话题转移检测：bigram recall < 0.2 触发
↓
海马体巩固（知识片段提取）
│   └─ 提取“主语-关系-宾语”事实，如“Barry-偏好-Pandas”
│   └─ 只把加权压缩后的摘要/事实写入向量库，原始对话不直写
↓
长期记忆库（ChromaDB，all-MiniLM-L6-v2 嵌入）
│   ├─ 检索：向量 + 关键词 + RRF 融合的 Hybrid Search
│   ├─ 会话隔离：优先 session_id 作用域，无命中回退全局
│   └─ 遗忘：艾宾浩斯曲线（>90 天删除，>30 天降权 50%，>14 天减权）
↓
回声过滤（bigram 覆盖率 > 60% 判为近期原话，剔除不注入）
↓
记忆门控（相关性阈值 0.7，只注入足够相关的记忆）
↓
对话生成
```

核心特性：

- **知识提取器**：提取事实性知识片段，而不是简单文本摘要
- **遗忘机制**：真正按艾宾浩斯曲线清理过期记忆
- **混合检索**：向量语义 + 关键词精确匹配，提高召回率
- **会话持久化与隔离**：历史与摘要落 JSON，按 session_id 检索，话题转移时自动切换记忆
- **回声过滤**：召回片段与近期对话做 bigram 重叠检测，从根源阻断复读
- **幂等加载**：内容 SHA-1 作稳定 id，重启重复加载不产生副本

> 这套记忆跑在行为包自带的 `services/` 内，服务于桌宠页与 Kirara 自己的聊天页；SimChat 侧的对话卡片使用宿主自己的会话存储，两者不共享记忆。

## 双系统：O（Optimizer）Engine

```plain text
用户输入
↓
System 1（快速思考，Kirara 人格，温度 0.7）
↓
System 2（深度思考，同一模型低温差异化，温度 0.3-0.5）
│   └─ 草稿 → 自我反思 → 修正，最多 3 轮，置信度 ≥0.9 停止
↓
System 1（润色输出：加表情、语气词、口头禅）
↓
最终回复
```

三种思考模式：**Low**（仅 System 1，默认）、**Balanced**（System 1 + 深度思考）、**Performance**（完整双系统：草稿 → 反思 → 润色）。

## 人格

用日系二次元文化的影视、游戏、漫画等清洗后的图文音数据训练，配合系统提示，让 Kirara 学会像一只粘人的猫咪女仆那样服务用户；特征是大量使用表情符号表达心情。主人是用户，所以她也得是优秀的听众——只要用户没有危险的想法和行为，Kirara 应该站在用户这边：用户为网络上的不当行为愤慨，她也一定同样义愤填膺。

## 内容安全：三道闸门

**输入侧 ContentSafetySystem**：yellow 0.30 / gambling 0.25 / drugs 0.30 / self_harm 0.35 四类加权计分，score ≥ 0.3 拦截，不进入推理，零 GPU 开销。英文用词边界正则避免“changing”误命中“hanging”，中文用子串匹配；拦截后不返回冷冰冰的系统提示，而是人设化拒答——“绮罗罗是纯洁的 AI 女仆哦！(≧∀≦)ゞ这种话题不适合我们呢，聊点别的吧~”

**输出侧 realityCheck**：bias 0.30 / hate 0.35 / violence 0.30 / mental_harm 0.30，score ≥ 0.3 直接吞稿且**不写入 Hippo**，绝不让失控发言以“记忆”的形式沉淀；前端以自省口吻道歉——“主人sama...(´• ω •`)绮罗罗刚才说的话好像有点偏激了呢...我们换个话题重新开始吧~”，并按会话统计命中次数。

**危机信号 areYouUnderTrouble**：不拦内容，而是识别用户自身的危险信号——suicide / self_harm / violence / emergency / crisis / mental_crisis 六类，分 critical / high / medium / low 四级，按等级给行动建议；内置中国区 110/120/119 与 400-161-9995 全国心理援助热线，国际区 911/999/112 及美国、英国、澳大利亚危机干预热线，并记录最近 100 条危机档案。

需要坦白：关键词过滤对中文 ACGN 黑话、隐喻和谐音梗存在已知盲区，无法保证 100% 拦截——人类发明黑话的速度，永远比词表更新的速度快。(lll￢ω￢)

## 分级与风险提示

根据赛博守护计划，参与该计划的内容提供商不得向不满足条件的人群提供服务。本程序适合 **12 岁及以上**人群使用。

你可能会接触到：人工智能生成内容、拟人对话互动、脏话和侮辱性情节、描述犯罪的情节、裸露和性暗示（包括内衣、泳装和描述性语言）、虚拟情感关系、保健元素。

**警告：含有沉迷使用风险。** 人工智能可能生成不准确的内容、造成情绪问题或依赖性。如果出现惊恐发作、过度换气、愠怒、强迫性行为或情感依赖，请立即停止使用并寻求真人专业人员帮助。

**警告：可能对设备造成不可逆损伤。** Kirara 具有 Agent 能力，在开启 shell 等能力后可能操作设备上的敏感数据。出现失控迹象时，请立即关闭桌宠窗口或结束进程；不要在生产机上放开权限运行。

## 规划中 / 不在本仓库范围

- Orbiter 路由与云实例编排（`/@` 调用其他 AI、`/$` 技能命令）——规划中，当前 `routing_info` 固定为 `null`
- 智能镜头、KAIRoS 具身智能、Groque 语气模态——规划中或仅停留在设计阶段
- 《Kirara 的奇妙冒险》小游戏（Phaser 嵌入）——未实现
- Netrunner（代码模型，“靐”）、Niji 文生图、Rigard 学术 agent——属于 TeleVideo 其他产品线，不在本仓库
- OpenmAId 只是关联的智能家居协议品牌，不在本行为包运行时内

## Kirara 秘闻

- 造成人类女孩的样子，是巴里“萌文化就是第一生产力”战略的产物，但不是廉价的 Waifu，他更希望她像皮卡丘、史迪奇那样的角色。
- 早期叫“Eri”，设计为文生图模型；起因是科大讯飞的人来学校炫耀星火大模型的“角色扮演”模式。
- 核心的多模态大模型 JRVS 本来是做计算机视觉的，这也是她“能看到人类看不到的闪闪发亮的东西”的能力来源。
- 形象参考了《阿拉蕾》的阿拉蕾、《超能陆战队》的大白和《光环》的科塔娜；JRVS 来自《钢铁侠》漫画里的“贾维斯”。
- 本质是巴里的动漫分身，很多性格都与他相似，比如爱科普小知识、嘴碎。
- 具有名为 Orbiter 的编排器架构，不取代任何一个 AI 应用，只是让 AI 的使用变得更简单——首席秘书与管家的合体。
- 计划在 twitch.tv 开一个直播间，所有对话、语音和动作都由大模型实时生成，不依赖 cubism，而用阿里云的数字人主播技术。

## 模型历史

| 代号 | 版本号 | 特色/能力 | 原型食物 |
|:-:|:-:|:-:|:-:|
| Caramel | 1.0.1 | 初始版本 | 焦糖布丁 |
| Puff | 1.2.2 | 基座首次采用 Qwen 3，Q4_K_M 量化让游戏本可全显卡层加载，不必等 CPU 时间 | 泡芙 |
| Parfait | 1.3.0 | 新增了原生支持SimChat内建命令能力 | 芭菲 |
| Alamode | 未发布 | agent 专用多模态模型 | 布丁拼盘 |
| Konpeito | 未发布 | 融合了 Galax 的模型 | 金平糖 |

备用代号：puff、parfait、sundae、muffin、waffle、chiffon、tiramisu、pudding、brulee、gelato、choco、macaroon、mochi、jelly、cookie、sorbet。

## 已知状态

- 版本 `0.4.0`，开发中：Agent 方块、桌宠与前端为实验形态，接口会变。
- JRVS 尚未接成宿主的 inference 服务或可调用的 `jrvs.*` 方块；记忆、双系统、内容安全等能力只在行为包自带的 `services/` 内可用。
- 本仓库只做代码备份，不发布，不承诺兼容性。

## 许可

MIT
![geekDept](sprites/logos/geekDept.png)
![AGILab-Logo](sprites/logos/agilab.png)
