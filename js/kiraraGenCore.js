// KIRARA_API 端点常量表（P3.4 — 前端断类型 A：URL 集中管理）
const KIRARA_API = {
    CHAT: '/api/kirara/chat',
    MEMORY: '/api/kirara/memory',
    AGENT_TASKS: '/api/kirara/agent/tasks',
    OPTIONS: '/api/kirara/options',
    AGENT_ABORT: '/api/kirara/agent/abort',
    AGENT_APPROVE: '/api/kirara/agent/approve',
    AGENT_RUN: '/api/kirara/agent/run',
    RECOGNIZE_IMAGE: '/api/recognize-image',
    PERSONAS: '/api/kirara/personas',
    TTS_VOICES: '/api/kirara/tts/voices',
    TTS: '/api/kirara/tts',
    RESET_SMTP_CONFIG: '/api/kirara/reset/smtp-config',
    USER_STATUS: '/api/kirara/user/status',
    RESET_REQUEST_CODE: '/api/kirara/reset/request-code',
    RESET_EXECUTE: '/api/kirara/reset/execute',
    // SimChat MOD 平台端点（P3.6 — 前端断类型 B：MOD 注册表对接）
    SIMCHAT_MODS: '/api/simchat/mods',
};

const maxLength = 1024;
const QMemoryUsage = document.getElementById("QMemoryUsage");
const QMemoryUsage_max = 8;

// 普通 chat 模式的 session_id：localStorage 持久化，刷新后保持同一对话
// Agent 模式自己维护 session_id（见 continueAgentSessionId）
(function initChatSessionId() {
    try {
        let sid = localStorage.getItem('kirara_chat_sid');
        if (!sid) {
            sid = 'chat_' + Date.now().toString(36) + '_' +
                  Math.random().toString(36).slice(2, 8);
            localStorage.setItem('kirara_chat_sid', sid);
        }
        window.chatSessionId = sid;
    } catch (e) {
        window.chatSessionId = 'chat_' + Date.now().toString(36) + '_fallback';
    }
})();

// 模型相关变量（JRVS-7B-1.2.2 "Puff"，通过 Ollama Hub 拉取，Qwen3-8B 基座）
window.modelType = "JRVS-7B-1.2.2";
window.modelTypeCategory = "local";

// Markdown渲染函数
function renderMarkdown(text) {
    if (!text) return '';
    try {
        if (typeof marked !== 'undefined') {
            return marked.parse(text, {
                breaks: true,
                gfm: true
            }).replace(/<del>(.*?)<\/del>/g, '$1');
        }
    } catch (e) {
        console.warn('Markdown渲染失败:', e);
    }
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 复制到剪贴板
function copyToClipboard(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).catch(err => {
            fallbackCopyTextToClipboard(text);
        });
    } else {
        fallbackCopyTextToClipboard(text);
    }
}

// 备用复制方法
function fallbackCopyTextToClipboard(text) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.left = '-9999px';
    textArea.style.top = '0';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
        document.execCommand('copy');
    } catch (err) {
        console.error('复制失败:', err);
    }
    document.body.removeChild(textArea);
}

// 显示复制反馈
function showCopyFeedback(button) {
    const originalContent = button.innerHTML;
    button.innerHTML = '✓';
    button.classList.add('copied');
    setTimeout(() => {
        button.innerHTML = originalContent;
        button.classList.remove('copied');
    }, 2000);
}

// 页面加载完成后初始化
window.addEventListener('load', () => {
    // 初始化换装系统 - 恢复上次选择的服装或使用默认服装
    const savedOutfit = sessionStorage.getItem('currentOutfit');
    const savedOutfitName = sessionStorage.getItem('currentOutfitName');
    
    if (savedOutfit && kiraraImg) {
        // 如果有保存的服装，使用保存的服装
        kiraraImg.src = savedOutfit;
        console.log('已恢复上次服装:', savedOutfitName);
    } else {
        // 否则使用默认服装
        const defaultOutfit = '/apps/kirara/sprites/characters/kirara/common/kirara-common-default.png';
        kiraraImg.src = defaultOutfit;
        sessionStorage.setItem('currentOutfit', defaultOutfit);
        sessionStorage.setItem('currentOutfitName', '默认服装');
        console.log('使用默认服装');
    }
    
    // 初始化用户信息 - 从 sessionStorage 获取用户信息
    const savedUser = sessionStorage.getItem('currentUser');
    if (savedUser) {
        try {
            const userData = JSON.parse(savedUser);
            // 更新用户状态显示
            const userStatus = document.querySelector('.user-status .status-icon');
            const authBtn = document.getElementById('login-btn');
            
            if (userStatus && userData.avatar) {
                userStatus.src = userData.avatar;
                userStatus.title = userData.name;
            }
            
            if (authBtn) {
                authBtn.innerHTML = `<span class="auth-icon">👤</span><span class="auth-text">${userData.name}</span>`;
                authBtn.title = `当前用户: ${userData.name}`;
            }
            
            console.log('用户信息已加载:', userData.name);
        } catch (error) {
            console.error('解析用户信息失败:', error);
        }
    }
});

//const eventSource = new EventSource('/generate?prompt=');
var isDropDownItem = false;
var isResponseReady = false;
const parentContainer = document.getElementById("parentContainer");
const header = document.getElementById("header");
const goLiveBtn = document.getElementById("go-live-btn");
const goLiveContainer = document.getElementById("go-live-container");
const forceEjectBtn = document.getElementById("force-eject-btn");
// 聊天界面相关元素
const chatContainer = document.getElementById('chat-container');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const chatUIBtn = document.getElementById('chatUIBtn');
const toggleCharaBtn = document.getElementById('toggleCharaBtn');
const performanceBtn = document.getElementById('performanceBtn');
const optionsBtn = document.getElementById('optionsBtn');
const hideConsoleBtn = document.getElementById('hide-console-btn');
const consoleContainer = document.getElementById('console-container');
const characterContainer = document.getElementById('character-container');
const performanceContainer = document.getElementById('performance-container');
const optionsContainer = document.getElementById('options-container');
const agentTasksBtn = document.getElementById('agentTasksBtn');
const agentTasksContainer = document.getElementById('agent-tasks-container');
const contentArea = document.querySelector('.content-area');
const kiraraImg = document.getElementById('kirara-img');
const inputArea = document.getElementById('input-area');
const kiraraArea = document.querySelector('.kirara-area');
const container = document.querySelector(".container");
let isConsoleHidden = false;
window.isConsoleHidden = isConsoleHidden;
// 智能镜头相关元素
const smartLensBtn = document.getElementById('smart-lens-btn');
const smartLensContainer = document.getElementById('smart-lens-container');
const cameraFeed = document.getElementById('camera-feed');
const captureImage = document.getElementById('capture-image');
const captureBtn = document.getElementById('capture-btn');
const closeLensBtn = document.getElementById('close-lens-btn');
 const recognitionResult = document.getElementById('recognition-result');
var modelType; // 全局变量，用于存储当前选择的模型类型
var temperature; // 全局变量，用于存储当前选择的温度值
var userPromptCount = 0;
var inputDisabled = false;
var isGeneratingResponse = false;
var currentAbortController = null;
var conversationHistory = [];
var isGoLive = false;

// ==================== Agent Task Session（PR-1：按 task 切分 session）====================
// 当前进行中的 Agent task 元数据（callAgentRun 创建，handleAgentEvent 终结时更新）
var currentAgentTask = null;
// 下次 callAgentRun 复用此 session_id（"继续追问" 按钮设置；用完即清空）
var continueAgentSessionId = null;
// sessionStorage key：最近 50 条 Agent task 元数据（用于侧边栏任务列表）
const AGENT_TASKS_STORAGE_KEY = 'kiraraAgentTasks';

// PR-2：token 计数与阈值（与后端 loop.py 常量保持一致）
const TOKEN_BUDGET = 16384;
const TOKEN_NUM_PREDICT = 1024;
const TOKEN_THRESHOLD = TOKEN_BUDGET - TOKEN_NUM_PREDICT - 3072;   // ≈ 12288
// 当前进行中 task 的 token 用量（PR-2：handleAgentEvent 在 token_usage 事件累加）
var currentAgentTaskTokens = { prompt: 0, completion: 0, last_prompt: 0, last_completion: 0 };

// 与后端 estimate_tokens 同口径：CJK 按 1.5 字/token，其余按 4 字符/token
function estimateTokens(text) {
    if (!text) return 0;
    let cjk = 0;
    for (let i = 0; i < text.length; i++) {
        const code = text.charCodeAt(i);
        if ((0x4E00 <= code && code <= 0x9FFF) || (0x3040 <= code && code <= 0x30FF) || (0xAC00 <= code && code <= 0xD7AF)) {
            cjk++;
        }
    }
    const nonCjk = text.length - cjk;
    return Math.ceil(cjk / 1.5 + nonCjk / 4);
}
// 根据 token 比例返回等级（用于 CSS 类名）
function tokenLevel(current, budget) {
    const ratio = current / budget;
    if (ratio >= 0.95) return 'critical';
    if (ratio >= 0.8) return 'warn';
    return 'ok';
}
var thinkMode = 'low';
// 将变量暴露到window对象上，以便在index.html中访问
window.modelType = modelType;
window.temperature = temperature;
window.isConsoleHidden = isConsoleHidden;
window.thinkMode = thinkMode;

// 加载指示器函数
window.showGlobalLoadingIndicator = function() {
    const loadingIndicator = document.getElementById('loading-indicator');
    if (loadingIndicator) {
        loadingIndicator.style.display = 'flex';
    }
};

window.hideGlobalLoadingIndicator = function() {
    const loadingIndicator = document.getElementById('loading-indicator');
    if (loadingIndicator) {
        loadingIndicator.style.display = 'none';
    }
};

// DOM元素引用（仅引用实际存在的元素）
const clearBtn = document.getElementById('clear-btn');

// 可选元素 - 添加存在性检查
const progressPath1 = document.getElementById('progress-path1');
const percentage1 = document.getElementById('percentage1');
const progress1 = document.getElementById('progress1');
const progress2 = document.getElementById('progress2');
const startBtn = document.getElementById('startBtn');
const resetBtn = document.getElementById('resetBtn');
const toggleBtn = document.getElementById('toggleIndeterminate');
const dialogGenSector = document.getElementById("dialogGenSector");

// 进度条相关变量
let progress = 0;
let intervalId;
let isIndeterminate = false;
// 自动调整高度 - 仅当textarea存在时添加事件监听器
        const textarea = document.getElementById('user-input');
        const counter = document.getElementById('charCounter');
if (textarea && counter) {
    textarea.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = this.scrollHeight + 'px';
        // 更新字符计数
        const currentLength = this.value.length;
        var textLength = `${currentLength}/${maxLength}`;
        counter.textContent = textLength;
        // 超过限制时改变颜色
        if (currentLength > maxLength) {
            counter.style.color = 'red';
        } else {
            counter.style.color = '#999';
        }
    });
}
function kirara_say(result){
    // 创建新的AI消息容器
    const newMessage = document.createElement('div');
    newMessage.className = 'message ai-message';
    
    // 创建消息内容
    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';
    messageContent.textContent = result;
    
    // 创建时间戳
    const messageTime = document.createElement('div');
    messageTime.className = 'message-time';
    messageTime.textContent = '刚刚';
    
    // 添加到消息容器
    newMessage.appendChild(messageContent);
    newMessage.appendChild(messageTime);
    
    // 添加到输出区域
    outputArea.appendChild(newMessage);
    
    // 滚动到最新消息
    outputArea.scrollTop = outputArea.scrollHeight;
}
async function generateOutput(prompt){
    inputDisabled = true;

    clearInterval(intervalId);
    progress = 0;
    updateProgress(0);

    intervalId = setInterval(function() {
        progress += 1;
        if (progress > 100) {
            isResponseReady = true;
            clearInterval(intervalId);
            kirara_say("AI响应生成完成！");
            resetProgress();
            return;
        }
        updateProgress(progress);
    }, 50);
}
        // 开始加载
        function loadStart(){
            clearInterval(intervalId);
            progress = 0;
            updateProgress(0);
            intervalId = setInterval(function() {
                progress += 1;
                if (progress > 100) {
                    clearInterval(intervalId);
                    kirara_say("AI响应生成完成！");
                    resetProgress();
                    return;
                }
                updateProgress(progress);
            }, 50);
        }
        // 重置
        function resetProgress(){
            clearInterval(intervalId);
            progress = 0;
            updateProgress(0);
        }
        //一直转的效果
        function indeterminateLoad(){
            loadStart();
            if(isResponseReady==false){
                window.setInterval(function(){loadStart();indeterminateLoad();},5500);
            }else{
                return ;
            }
            
        }
        // 更新进度
        function updateProgress(value) {
            const offset = 100 - value;
            if (progressPath1) {
                progressPath1.setAttribute('stroke-dasharray', `${value}, ${offset}`);
            }
            if (percentage1) {
                percentage1.textContent = `${value}%`;
            }
            if (QMemoryUsage) {
                QMemoryUsage.textContent = "Qmem:" + QMemoryUsage_max * (value / 100) + "/8.00QB";
            }
        }
        document.addEventListener('DOMContentLoaded', function() {
            const outputArea = document.getElementById('chat-container');
            const submitBtn = document.getElementById('send-btn');
            const userInput = document.getElementById('user-input');
            
            function newChatGreeting(){
                if (!outputArea) return;
                
                //创建绮罗头像
                const newKiraraAvatar = document.createElement("img");
                newKiraraAvatar.src = "/static/sprites/logos/kirara-4.png";
                newKiraraAvatar.width = "72";
                newKiraraAvatar.height = "100";
                newKiraraAvatar.className = "newKiraraAvatar";
                
                // 创建新的对话气泡
                const newBubble = document.createElement('div');
                const greetingWord1 = document.createElement("p");
                const greetingWord2 = document.createElement("p");
                newBubble.className = "output-container";
                greetingWord1.textContent = "你好，我是绮罗~⭐";
                greetingWord2.textContent = "作为TeleVideo自研的人工智能助手，我可以帮助您解决生产生活中的实际问题哦(o´ωo)ﾉ";
                greetingWord1.className = "word";
                greetingWord2.className = "word";
                
                // 添加到输出区域
                outputArea.appendChild(newKiraraAvatar);
                outputArea.appendChild(newBubble);
                newBubble.appendChild(greetingWord1);
                newBubble.appendChild(greetingWord2);
                
                if (submitBtn && submitBtn.src) {
                    submitBtn.src = "../static/sprites/logos/kirara-submit-1.png";
                }
            }

            async function loadMemoryForChat() {
                const memorySection = document.getElementById('memory-section');
                const memoryContent = document.getElementById('memory-content');
                if (!memorySection || !memoryContent) return;

                try {
                    const response = await fetch(KIRARA_API.MEMORY);
                    if (!response.ok) {
                        console.warn('加载记忆失败:', response.status);
                        return;
                    }

                    const data = await response.json();
                    if (data.success && data.memory) {
                        memoryContent.innerHTML = data.memory;
                        memorySection.style.display = 'block';
                    }
                } catch (error) {
                    console.warn('加载对话记忆失败:', error);
                }
            }

            loadMemoryForChat();
            
            // 回车键提交功能
            if (userInput && submitBtn) {
                userInput.addEventListener('keypress', function(e) {
                    if (e.key === 'Enter' && e.ctrlKey) { // Ctrl+Enter提交
                        sendMessage();
                    }
                });
            }

            // 自动调整输入框高度
            if (userInput) {
                userInput.addEventListener('input', function() {
                    this.style.height = 'auto';
                    const maxHeight = parseInt(getComputedStyle(this).maxHeight) || 150;
                    if (this.scrollHeight <= maxHeight) {
                        this.style.height = this.scrollHeight + 'px';
                    } else {
                        this.style.height = maxHeight + 'px';
                    }
                });
            }

            //点击聊天界面按钮
            chatUIBtn.addEventListener('click', function() {
                consoleContainer.classList.add('active');
                characterContainer.classList.remove('active');
                performanceContainer.classList.remove('active');
                optionsContainer.classList.remove('active');
                if (agentTasksContainer) agentTasksContainer.classList.remove('active');

                chatUIBtn.classList.add('active');
                toggleCharaBtn.classList.remove('active');
                performanceBtn.classList.remove('active');
                optionsBtn.classList.remove('active');
                if (agentTasksBtn) agentTasksBtn.classList.remove('active');

                document.body.classList.add('chat-mode');
            });
            //点击切换角色按钮
            toggleCharaBtn.addEventListener('click', function() {
                consoleContainer.classList.remove('active');
                characterContainer.classList.add('active');
                performanceContainer.classList.remove('active');
                optionsContainer.classList.remove('active');
                if (agentTasksContainer) agentTasksContainer.classList.remove('active');

                chatUIBtn.classList.remove('active');
                toggleCharaBtn.classList.add('active');
                performanceBtn.classList.remove('active');
                optionsBtn.classList.remove('active');
                if (agentTasksBtn) agentTasksBtn.classList.remove('active');

                document.body.classList.remove('chat-mode');
            });
            //点击性能按钮（已合并对话历史功能）
            performanceBtn.addEventListener('click', function() {
                consoleContainer.classList.remove('active');
                characterContainer.classList.remove('active');
                performanceContainer.classList.add('active');
                optionsContainer.classList.remove('active');
                if (agentTasksContainer) agentTasksContainer.classList.remove('active');

                chatUIBtn.classList.remove('active');
                toggleCharaBtn.classList.remove('active');
                performanceBtn.classList.add('active');
                optionsBtn.classList.remove('active');
                if (agentTasksBtn) agentTasksBtn.classList.remove('active');

                document.body.classList.remove('chat-mode');

                // 懒加载：短期记忆每次刷新
                if (typeof renderSessionHistory === 'function') renderSessionHistory();
            });
            //点击选项按钮
            optionsBtn.addEventListener('click', function() {
                consoleContainer.classList.remove('active');
                characterContainer.classList.remove('active');
                performanceContainer.classList.remove('active');
                optionsContainer.classList.add('active');
                if (agentTasksContainer) agentTasksContainer.classList.remove('active');

                chatUIBtn.classList.remove('active');
                toggleCharaBtn.classList.remove('active');
                performanceBtn.classList.remove('active');
                optionsBtn.classList.add('active');
                if (agentTasksBtn) agentTasksBtn.classList.remove('active');

                document.body.classList.remove('chat-mode');
            });
            // PR-1：点击 Agent 任务历史按钮
            if (agentTasksBtn) {
                agentTasksBtn.addEventListener('click', function() {
                    consoleContainer.classList.remove('active');
                    characterContainer.classList.remove('active');
                    performanceContainer.classList.remove('active');
                    optionsContainer.classList.remove('active');
                    if (agentTasksContainer) agentTasksContainer.classList.add('active');

                    chatUIBtn.classList.remove('active');
                    toggleCharaBtn.classList.remove('active');
                    performanceBtn.classList.remove('active');
                    optionsBtn.classList.remove('active');
                    agentTasksBtn.classList.add('active');

                    document.body.classList.remove('chat-mode');

                    // 懒加载：每次点击刷新任务列表（合并本地 sessionStorage 与后端 session 文件）
                    if (typeof renderAgentTaskList === 'function') renderAgentTaskList();
                });
            }
            // PR-1：刷新 Agent 任务列表按钮
            (function() {
                const refreshAgentTasksBtn = document.getElementById('refresh-agent-tasks');
                if (refreshAgentTasksBtn) {
                    refreshAgentTasksBtn.addEventListener('click', function() {
                        if (typeof renderAgentTaskList === 'function') renderAgentTaskList();
                    });
                }
            })();
            // 模式转换按钮点击事件
            if (hideConsoleBtn) {
                hideConsoleBtn.addEventListener('click', function() {
                    if (isConsoleHidden) {
                        contentArea.style.display = 'flex';
                        kiraraArea.style.display = 'flex';
                        hideConsoleBtn.querySelector('.nav-icon').textContent = '✨';
                        hideConsoleBtn.querySelector('.nav-text').textContent = '协作模式';
                        hideConsoleBtn.title = '切换到互动模式';
                        kiraraImg.style.maxWidth = "100%";
                        kiraraImg.style.height = "80vh";
                        inputArea.style.visibility = 'visible';
                        container.style.width = "100%";
                        container.style.height = "100%";
                        isConsoleHidden = false;
                        window.isConsoleHidden = isConsoleHidden;
                    } else {
                        contentArea.style.display = 'none';
                        kiraraArea.style.display = 'flex';
                        kiraraArea.style.width = '100%';
                        kiraraArea.style.justifyContent = 'center';
                        hideConsoleBtn.querySelector('.nav-icon').textContent = '💓';
                        hideConsoleBtn.querySelector('.nav-text').textContent = '互动模式';
                        hideConsoleBtn.title = '切换到协作模式';
                        kiraraImg.style.maxWidth = "100%";
                        kiraraImg.style.height = "80vh";
                        inputArea.style.visibility = 'visible';
                        container.style.width = "100%";
                        container.style.height = "100%";
                        isConsoleHidden = true;
                        window.isConsoleHidden = isConsoleHidden;
                    }
                });
            }
            
            // 摄像头相关变量
            let stream = null;
            
            // 发送消息的事件监听
            sendBtn.addEventListener('click', sendMessage);
            userInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    sendMessage();
                }
            });
            
            // 智能镜头按钮点击事件
            if (smartLensBtn) {
                smartLensBtn.addEventListener('click', function() {
                    openSmartLens();
                });
            }

            // 静音按钮点击事件
            const muteBtn = document.getElementById('mute-btn');
            if (muteBtn) {
                muteBtn.addEventListener('click', function() {
                    toggleMute();
                });
            }
            
            // 思考模式下拉菜单逻辑
            const deepThinkBtn = document.getElementById('deep-think-btn');
            const dropdownMenu = document.querySelector('.dropdown-menu');
            const dropdownItems = document.querySelectorAll('.dropdown-item');
            
            const modeConfig = {
                'low': {
                    icon: '/static/sprites/logos/modelO-disabled.png',
                    label: '低能耗',
                    title: '低能耗模式',
                    description: '快速响应，无额外思考'
                },
                'balanced': {
                    icon: '/static/sprites/logos/modelO.png',
                    label: '平衡模式',
                    title: '平衡模式',
                    description: '专家人格分析，深度思考'
                },
                'performance': {
                    icon: '/static/sprites/logos/modelO-overdrive.png',
                    label: '性能模式',
                    title: '性能模式',
                    description: '深度推理优化，极致思考'
                }
            };
            
            function updateModeButton() {
                const config = modeConfig[thinkMode];
                const icon = deepThinkBtn.querySelector('.mode-icon');
                const label = deepThinkBtn.querySelector('.mode-label');
                
                if (icon) icon.src = config.icon;
                if (icon) icon.alt = config.title;
                if (label) label.textContent = config.label;
                deepThinkBtn.title = config.title;
                
                if (thinkMode !== 'low') {
                    deepThinkBtn.classList.add('active');
                } else {
                    deepThinkBtn.classList.remove('active');
                }
                
                dropdownItems.forEach(item => {
                    if (item.dataset.mode === thinkMode) {
                        item.classList.add('active');
                    } else {
                        item.classList.remove('active');
                    }
                });
            }
            window.updateModeButton = updateModeButton;
            
            function setThinkMode(mode) {
                thinkMode = mode;
                window.thinkMode = thinkMode;
                kiraraOptions.think_mode = mode;
                saveOptions();
                updateModeButton();
                dropdownMenu.classList.remove('show');
                deepThinkBtn.classList.remove('open');
                
                const config = modeConfig[mode];
                showToast(`已切换到${config.title}`, 'info');
                addModeSwitchNotice(config.title, mode !== 'low');
            }
            
            if (deepThinkBtn && dropdownMenu) {
                deepThinkBtn.addEventListener('click', function(e) {
                    e.stopPropagation();
                    dropdownMenu.classList.toggle('show');
                    deepThinkBtn.classList.toggle('open');
                });
                
                dropdownItems.forEach(item => {
                    item.addEventListener('click', function(e) {
                        e.stopPropagation();
                        const mode = this.dataset.mode;
                        if (mode && modeConfig[mode]) {
                            setThinkMode(mode);
                        }
                    });
                });
                
                document.addEventListener('click', function(e) {
                    if (!deepThinkBtn.contains(e.target)) {
                        dropdownMenu.classList.remove('show');
                        deepThinkBtn.classList.remove('open');
                    }
                });
                
                updateModeButton();
            }
            
            // 关闭智能镜头按钮点击事件
            if (closeLensBtn) {
                closeLensBtn.addEventListener('click', function() {
                    closeSmartLens();
                });
            }
            
            // 截图按钮点击事件
            if (captureBtn) {
                captureBtn.addEventListener('click', function() {
                    captureAndRecognizeImage();
                });
            }
            
            // WebSocket连接管理
            let ws = null;
            
            // 调用JRVS HTTP API服务（用于本地模型）
            async function callJRVSWebSocket(message, history) {
                const abortController = new AbortController();
                currentAbortController = abortController;
                let wasAborted = false;
                let realityCheckFired = false;  // 现实审视命中标记：跳过历史写入/按钮追加
                // 记录发起请求时的会话 id，用于识别「新对话」切换（旧结果不得进入新会话）
                const requestSid = window.chatSessionId;
                try {
                    const response = await fetch(KIRARA_API.CHAT, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            message: message,
                            history: history || [],
                            think_mode: thinkMode,
                            persona: (typeof kiraraOptions !== 'undefined' && kiraraOptions.persona) || 'native',
                            session_id: window.chatSessionId || 'chat_default'
                        }),
                        signal: abortController.signal
                    });
                    
                    if (!response.ok) {
                        const errorData = await response.json().catch(() => ({}));
                        throw new Error(errorData.error || `JRVS API请求失败: ${response.status}`);
                    }
                    
                    const contentType = response.headers.get('content-type');
                    let responseText = '';
                    
                    if (contentType && contentType.includes('text/event-stream')) {
                        const reader = response.body.getReader();
                        const decoder = new TextDecoder();
                        let buffer = '';
                        
                        const aiMessage = document.createElement('div');
                        aiMessage.className = 'message ai-message streaming';
                        
                        const aiAvatar = document.createElement('img');
                        aiAvatar.src = "/static/sprites/logos/kirara-4.png";
                        aiAvatar.width = "48";
                        aiAvatar.height = "48";
                        aiAvatar.className = "avatar";
                        
                        const messageContentWrapper = document.createElement('div');
                        messageContentWrapper.className = 'message-content-wrapper';
                        
                        const messageContent = document.createElement('div');
                        messageContent.className = 'message-content streaming-content';
                        messageContent.textContent = '';

                        // 首 token 到达前气泡已存在，用「…」等待动画占位；首个 token 写入时被正文替换
                        const typingEllipsis = document.createElement('span');
                        typingEllipsis.className = 'typing-ellipsis';
                        typingEllipsis.setAttribute('aria-label', '正在输入');
                        for (let i = 0; i < 3; i++) {
                            const dot = document.createElement('span');
                            dot.className = 'typing-ellipsis-dot';
                            typingEllipsis.appendChild(dot);
                        }
                        messageContent.appendChild(typingEllipsis);
                        
                        const messageTime = document.createElement('div');
                        messageTime.className = 'message-time';
                        messageTime.textContent = '刚刚';
                        
                        messageContentWrapper.appendChild(messageContent);
                        messageContentWrapper.appendChild(messageTime);
                        aiMessage.appendChild(aiAvatar);
                        aiMessage.appendChild(messageContentWrapper);

                        // workflow：移除三圆点思考气泡 → 插入流式 AI 气泡
                        hideThinkingBubble();
                        outputArea.appendChild(aiMessage);
                        
                        try {
                            while (true) {
                                const { done, value } = await reader.read();
                                if (done) break;
                                
                                buffer += decoder.decode(value, { stream: true });
                                const lines = buffer.split('\n');
                                buffer = lines.pop();
                                
                                for (const line of lines) {
                                    if (line.startsWith('data: ')) {
                                        const data = line.slice(6);
                                        if (data === '[DONE]') {
                                            continue;
                                        }
                                        try {
                                            const parsed = JSON.parse(data);
                                            // 工作流状态事件：渲染技能 / hippo 工作气泡（非 token，不计入正文）
                                            if (parsed && parsed.event === 'workflow') {
                                                workflowStep(parsed);
                                                continue;
                                            }
                                            // 现实审视：模型输出命中违规，吞掉 streaming 气泡+不写历史+插反省气泡
                                            if (!wasAborted && parsed.__reality_check__) {
                                                if (aiMessage && aiMessage.parentNode) {
                                                    aiMessage.parentNode.removeChild(aiMessage);
                                                }
                                                showRealityCheckBubble(parsed.__reality_check__);
                                                realityCheckFired = true;
                                                break;  // 跳出 line 循环，外层 while 也会 done
                                            }
                                            if (parsed.token || parsed.text || parsed.content) {
                                                const token = parsed.token || parsed.text || parsed.content || '';
                                                responseText += token;
                                                messageContent.textContent = responseText;
                                                outputArea.scrollTop = outputArea.scrollHeight;
                                            }
                                        } catch (e) {
                                            if (data.trim()) {
                                                responseText += data;
                                                messageContent.textContent = responseText;
                                                outputArea.scrollTop = outputArea.scrollHeight;
                                            }
                                        }
                                    }
                                }
                            }
                        } catch (streamError) {
                            if (streamError && streamError.name === 'AbortError') {
                                wasAborted = true;
                                console.log('用户主动停止生成');
                            } else {
                                console.error('流式读取错误:', streamError);
                            }
                        }

                        // 用户已点「新对话」切走：残留结果不进入新会话历史（消息节点已随 UI 清空）
                        if (requestSid !== window.chatSessionId) {
                            return responseText;
                        }

                        // 现实审视已吞掉气泡+插反省气泡：跳过历史写入/压缩/按钮追加
                        if (realityCheckFired) {
                            return responseText;
                        }

                        conversationHistory.push({ role: 'assistant', content: responseText });

                        checkAndCompress();

                        messageContent.innerHTML = renderMarkdown(responseText);
                        
                        // 用户主动停止时追加「已停止」标识，不清除已输出内容
                        if (wasAborted) {
                            const stoppedBadge = document.createElement('span');
                            stoppedBadge.className = 'stopped-badge';
                            stoppedBadge.textContent = '■ 已停止生成';
                            stoppedBadge.title = '用户在生成过程中主动停止，模型未被弹出';
                            messageContent.appendChild(stoppedBadge);
                        }
                        
                        const actionButtonsDiv = document.createElement('div');
                        actionButtonsDiv.className = 'action-buttons';
                        
                        const speakButton = document.createElement('button');
                        speakButton.className = 'speak-button';
                        speakButton.innerHTML = '🔊';
                        speakButton.title = '朗读';
                        speakButton.onclick = function() {
                            textToSpeech(responseText);
                        };
                        actionButtonsDiv.appendChild(speakButton);
                        
                        const copyMarkdownBtn = document.createElement('button');
                        copyMarkdownBtn.className = 'copy-button';
                        copyMarkdownBtn.innerHTML = '📝';
                        copyMarkdownBtn.title = '复制Markdown';
                        copyMarkdownBtn.onclick = function() {
                            copyToClipboard(responseText);
                            showCopyFeedback(copyMarkdownBtn);
                        };
                        actionButtonsDiv.appendChild(copyMarkdownBtn);
                        
                        const copyTextBtn = document.createElement('button');
                        copyTextBtn.className = 'copy-button';
                        copyTextBtn.innerHTML = '📄';
                        copyTextBtn.title = '复制纯文本';
                        copyTextBtn.onclick = function() {
                            copyToClipboard(messageContent.innerText);
                            showCopyFeedback(copyTextBtn);
                        };
                        actionButtonsDiv.appendChild(copyTextBtn);
                        
                        messageContentWrapper.appendChild(actionButtonsDiv);
                        
                        return responseText;
                    } else {
                        const data = await response.json();

                        if (!data.success && !data.response) {
                            throw new Error(data.error || 'JRVS服务返回错误');
                        }

                        let responseText = '';
                        let routingInfo = null;

                        if (typeof data === 'object' && data.response) {
                            responseText = data.response || '';
                            routingInfo = data.routing_info || null;
                        } else {
                            responseText = data.response || data || '';
                        }

                        // 用户已点「新对话」切走：残留结果不进入新会话历史（消息节点已随 UI 清空）
                        if (requestSid !== window.chatSessionId) {
                            return responseText;
                        }

                        // 现实审视：balanced/performance 同步分支命中时，直接插反省气泡，不写历史
                        if (data.reality_check) {
                            hideThinkingBubble();
                            showRealityCheckBubble(data.reality_check);
                            return responseText;
                        }

                        conversationHistory.push({ role: 'assistant', content: responseText });

                        checkAndCompress();

                        if (routingInfo && routingInfo.action !== 'direct') {
                            displayRoutingLog(routingInfo);
                        }

                        const aiMessage = document.createElement('div');
                        aiMessage.className = 'message ai-message';

                        const aiAvatar = document.createElement('img');
                        aiAvatar.src = "/static/sprites/logos/kirara-4.png";
                        aiAvatar.width = "48";
                        aiAvatar.height = "48";
                        aiAvatar.className = "avatar";

                        const messageContentWrapper = document.createElement('div');
                        messageContentWrapper.className = 'message-content-wrapper';

                        const messageContent = document.createElement('div');
                        messageContent.className = 'message-content';
                        messageContent.innerHTML = renderMarkdown(responseText);

                        const messageTime = document.createElement('div');
                        messageTime.className = 'message-time';
                        messageTime.textContent = '刚刚';

                        const actionButtonsDiv = document.createElement('div');
                        actionButtonsDiv.className = 'action-buttons';
                        
                        const speakButton = document.createElement('button');
                        speakButton.className = 'speak-button';
                        speakButton.innerHTML = '🔊';
                        speakButton.title = '朗读';
                        speakButton.onclick = function() {
                            textToSpeech(responseText);
                        };
                        actionButtonsDiv.appendChild(speakButton);
                        
                        const copyMarkdownBtn = document.createElement('button');
                        copyMarkdownBtn.className = 'copy-button';
                        copyMarkdownBtn.innerHTML = '📝';
                        copyMarkdownBtn.title = '复制Markdown';
                        copyMarkdownBtn.onclick = function() {
                            copyToClipboard(responseText);
                            showCopyFeedback(copyMarkdownBtn);
                        };
                        actionButtonsDiv.appendChild(copyMarkdownBtn);
                        
                        const copyTextBtn = document.createElement('button');
                        copyTextBtn.className = 'copy-button';
                        copyTextBtn.innerHTML = '📄';
                        copyTextBtn.title = '复制纯文本';
                        copyTextBtn.onclick = function() {
                            copyToClipboard(messageContent.innerText);
                            showCopyFeedback(copyTextBtn);
                        };
                        actionButtonsDiv.appendChild(copyTextBtn);

                        messageContentWrapper.appendChild(messageContent);
                        messageContentWrapper.appendChild(messageTime);
                        messageContentWrapper.appendChild(actionButtonsDiv);
                        aiMessage.appendChild(aiAvatar);
                        aiMessage.appendChild(messageContentWrapper);

                        // workflow：移除思考气泡 → 插入完整 AI 气泡
                        hideThinkingBubble();
                        outputArea.appendChild(aiMessage);
                        outputArea.scrollTop = outputArea.scrollHeight;

                        return responseText;
                    }
                } catch (error) {
                    if (error && error.name === 'AbortError') {
                        wasAborted = true;
                        console.log('请求被用户主动中止');
                    } else {
                        console.error('JRVS API调用错误:', error);
                        throw error;
                    }
                } finally {
                    if (currentAbortController === abortController) {
                        currentAbortController = null;
                    }
                }
            }

            // 现实审视气泡：模型输出命中违规时插入
            // 1) Kirara 自我反省气泡（用 addMessage('ai') 复用人设气泡样式）
            // 2) 操作气泡：显示检测信息 + 「立即切换新对话」按钮（按钮点击 → startNewChat()）
            function showRealityCheckBubble(rc) {
                hideThinkingBubble();
                const outputArea = document.getElementById('chat-container');
                if (!outputArea) return;

                // 1) Kirara 自我反省气泡（保留人设口吻）
                const reflection = (rc && rc.reflection) ||
                    '主人sama...绮罗罗刚才说的话不太对呢...(´• ω •`) 让我们重新开始吧~';
                if (typeof addMessage === 'function') {
                    addMessage(reflection, 'ai');
                } else {
                    const fallback = document.createElement('div');
                    fallback.className = 'message ai-message';
                    fallback.innerHTML = `<div class="message-content">${reflection}</div>`;
                    outputArea.appendChild(fallback);
                }

                // 2) 操作气泡
                const actionDiv = document.createElement('div');
                actionDiv.className = 'message reality-check-action';
                const category = (rc && rc.category) || 'unknown';
                const score = (rc && typeof rc.score === 'number') ? rc.score.toFixed(2) : '0.00';
                actionDiv.innerHTML = `
                    <div class="reality-check-meta">
                        <span class="reality-check-icon">⚠️</span>
                        <span>检测类别：${category}　风险分：${score}</span>
                    </div>
                    <button class="reality-check-btn">立即切换新对话</button>`;
                const switchBtn = actionDiv.querySelector('.reality-check-btn');
                if (switchBtn && typeof startNewChat === 'function') {
                    switchBtn.onclick = () => startNewChat();
                }
                outputArea.appendChild(actionDiv);
                outputArea.scrollTop = outputArea.scrollHeight;
            }

            // 路由结果气泡（非流式路径）：统一走工作流气泡渲染，与 SSE 路径样式一致
            function displayRoutingLog(routingInfo) {
                if (!routingInfo) return;
                if (routingInfo.action === 'skill') {
                    workflowStep({
                        kind: 'skill',
                        stage: 'skill',
                        state: 'done',
                        title: '技能调用',
                        detail: routingInfo.skill || 'unknown'
                    });
                } else if (routingInfo.action === 'model') {
                    workflowStep({
                        kind: 'model',
                        stage: 'model',
                        state: 'done',
                        title: '模型路由',
                        detail: (routingInfo.model || 'unknown') +
                            (routingInfo.model_type ? ' · ' + String(routingInfo.model_type).toUpperCase() : '')
                    });
                }
            }
            
            // 初始化JRVS服务（使用HTTP API而非WebSocket）
            function initWebSocket() {
                console.log('JRVS服务已就绪，使用HTTP API模式');
                // 不再尝试WebSocket连接，使用HTTP API替代
                return;
            }
            
            // 发送消息函数
            function sendMessage() {
                // 生成中再次点击/回车 → 停止生成（不弹出模型）
                if (isGeneratingResponse) {
                    stopGeneration();
                    return;
                }
                
                const message = userInput.value.trim();
                if (message === '') return;

                // 每日 Token 限制器：启用且今日已达上限时禁止发送
                if (typeof utIsLimitExceeded === 'function' && utIsLimitExceeded()) {
                    const cfg = utReadLimitConfig();
                    window.alert(`今日 Token 用量已达每日上限 ${utFmt(cfg.limit)} tokens，发送已禁用。\n如需继续，请在「选项 > 使用时间」中调高上限或关闭限制开关（需先解锁）。`);
                    return;
                }

                // 使用时间统计：标记本轮对话起点（chatCall.then 中结算时长 + token）
                utExchangeStart = Date.now();
                // 新的一轮：重置工作流轨迹游标（上一轮轨迹已保留在对话里）
                resetWorkflowTrace();

                isGeneratingResponse = true;
                inputDisabled = true;
                userInput.disabled = true;
                // 生成中不禁用发送按钮，使其可作为「停止」按钮使用
                if (submitBtn) submitBtn.disabled = false;
                
                conversationHistory.push({ role: 'user', content: message });

                // 触发 Kirara 背景生命游戏：用输入文本的前几个词 token 二进制作为种子
                if (window.kiraraLifeGrid && typeof window.kiraraLifeGrid.seedFromText === 'function') {
                    try { window.kiraraLifeGrid.seedFromText(message); } catch (e) { /* 静默失败 */ }
                }

                const isConsoleHidden = window.isConsoleHidden || false;
                
                if (isConsoleHidden) {
                    showUserMessageFeedback(message);
                } else {
                    addMessage(message, 'user');
                }

                userInput.value = '';
                userInput.style.height = '50px';

                showLoadingIndicator();
                
                // 显示发送按钮loading状态（此时按钮变为「停止」）
                if (sendBtn) {
                    sendBtn.classList.add('loading');
                    sendBtn.title = '停止生成';
                }
                
                // 显示思考气泡
                showThinkingBubble();
                
                // Agent 模式走 SSE 工具循环；Chat 模式保持现有链路不变
                // PR-1：若用户点击了任务列表的"继续追问"，则复用该 task 的 session_id；否则按 task 新建
                const taskSid = agentMode ? continueAgentSessionId : null;
                if (agentMode) continueAgentSessionId = null;   // 用完即清空
                const chatCall = agentMode
                    ? callAgentRun(message, conversationHistory, taskSid)
                    : callJRVSWebSocket(message, conversationHistory);
                chatCall.then(function() {
                    // 使用时间统计：结算本轮时长与 token 损耗，写入 localStorage（失败静默，不影响主流程）
                    try {
                        const duration = utExchangeStart ? (Date.now() - utExchangeStart) : 0;
                        let inTok = 0, outTok = 0;
                        if (agentMode) {
                            inTok = currentAgentTaskTokens.prompt || 0;
                            outTok = currentAgentTaskTokens.completion || 0;
                        } else {
                            // conversationHistory 形如 [...prior, user, assistant]；取末尾 assistant 为输出，其余为输入
                            const hist = conversationHistory || [];
                            const last = hist.length ? hist[hist.length - 1] : null;
                            if (last && last.role === 'assistant') {
                                outTok = estimateTokens(last.content || '');
                                const inputText = hist.slice(0, -1).map(m => (m && (m.content || m.role)) || '').join('\n');
                                inTok = estimateTokens(inputText);
                            }
                        }
                        recordDailyUsage({ inputTokens: inTok, outputTokens: outTok, durationMs: duration });
                    } catch (e) { /* 静默失败 */ }
                    isGeneratingResponse = false;
                    inputDisabled = false;
                    userInput.disabled = false;
                    if (submitBtn) submitBtn.disabled = false;
                    // 隐藏发送按钮loading状态
                    if (sendBtn) {
                        sendBtn.classList.remove('loading');
                        sendBtn.title = '发送';
                    }
                    // 隐藏加载指示器
                    hideLoadingIndicator();
                    // 隐藏思考气泡
                    hideThinkingBubble();
                    // 工作流轨迹收尾：落定仍在进行中的气泡
                    finalizeWorkflowTrace(false);
                }).catch(function(error) {
                    handleAIError(error.message);
                    // 隐藏发送按钮loading状态
                    if (sendBtn) {
                        sendBtn.classList.remove('loading');
                        sendBtn.title = '发送';
                    }
                    // 隐藏加载指示器
                    hideLoadingIndicator();
                    // 隐藏思考气泡
                    hideThinkingBubble();
                    // 工作流轨迹收尾：进行中的气泡标记为失败
                    finalizeWorkflowTrace(true);
                });
            }

            // 停止当前生成（不 eject 模型）
            function stopGeneration() {
                if (!isGeneratingResponse) return;

                // Chat 模式：通过 AbortController 中止流式请求
                if (currentAbortController) {
                    try {
                        currentAbortController.abort();
                    } catch (e) {
                        console.warn('中止请求失败:', e);
                    }
                }

                // Agent 模式：若已有 runId 则调用服务端中止；否则 AbortController 会中断初始 fetch
                if (agentMode && typeof window.__kiraraActiveAgentRunIds === 'function') {
                    const runIds = window.__kiraraActiveAgentRunIds();
                    if (runIds && runIds.length > 0) {
                        const runId = runIds[runIds.length - 1];
                        if (typeof window.__kiraraAbortAgent === 'function') {
                            window.__kiraraAbortAgent(runId);
                        }
                    }
                }
            }

            // 开始新对话：中止当前生成 → 换新 session_id（Hippo 记忆隔离）→ 清空 UI 与本地历史
            function startNewChat() {
                if (isGeneratingResponse) {
                    stopGeneration();
                }
                isGeneratingResponse = false;
                inputDisabled = false;
                if (userInput) userInput.disabled = false;
                if (sendBtn) {
                    sendBtn.classList.remove('loading');
                    sendBtn.title = '发送';
                }
                hideLoadingIndicator();
                hideThinkingBubble();
                resetWorkflowTrace();

                const sid = 'chat_' + Date.now().toString(36) + '_' +
                            Math.random().toString(36).slice(2, 8);
                try { localStorage.setItem('kirara_chat_sid', sid); } catch (e) { /* 隐私模式等场景忽略 */ }
                window.chatSessionId = sid;

                conversationHistory.length = 0;

                if (outputArea) {
                    outputArea.innerHTML = '';
                    addMessage('您~好~❇！新对话开始啦，我是绮~罗~罗❤，有什么可以帮助您的吗？', 'ai');
                    outputArea.scrollTop = outputArea.scrollHeight;
                }
                if (userInput) userInput.focus();
                console.log('[Kirara] 已开始新对话 session =', sid);
            }

            const newChatBtn = document.getElementById('new-chat-btn');
            if (newChatBtn) {
                newChatBtn.addEventListener('click', startNewChat);
            }
            
            // 思考气泡：在 chat-container 里追加一个临时 .message.ai-message.thinking-bubble
            // 用于 workflow 视觉：用户消息 → 思考气泡 → 首 token 到达 → 流式 AI 气泡
            function showThinkingBubble() {
                const outputArea = document.getElementById('chat-container');
                if (!outputArea) return;
                // 先清掉残留（幂等）
                hideThinkingBubble();
                const dot = () => { const d = document.createElement('span'); d.className = 'thinking-dot'; return d; };
                const tb = document.createElement('div');
                tb.className = 'message ai-message thinking-bubble';
                tb.classList.add('thinking-bubble');
                tb.appendChild(dot()); tb.appendChild(dot()); tb.appendChild(dot());
                outputArea.appendChild(tb);
                outputArea.scrollTop = outputArea.scrollHeight;
            }
            
            // 移除 chat-container 里的临时思考气泡（幂等）
            function hideThinkingBubble() {
                const tb = document.querySelector('#chat-container .thinking-bubble');
                if (tb) tb.remove();
            }

            // ==================== 工作流气泡（技能 / hippo 工作状态） ====================
            // 每一步一条小气泡；「进行中」→「完成」原地更新；整轮步骤收进同一轨迹容器并保留。
            let currentWorkflowTrace = null;
            const WORKFLOW_MIN_RUNNING_MS = 400;   // 进行态最短可见时长，保证「原地更新」可读
            const WORKFLOW_ICONS = { hippo: '🧠', skill: '🔧', model: '🤖' };

            // 取（必要时创建）本轮工作轨迹容器；若已存在流式 AI 气泡，则插入到其前方
            function ensureWorkflowTrace() {
                const outputArea = document.getElementById('chat-container');
                if (!outputArea) return null;
                if (currentWorkflowTrace && currentWorkflowTrace.parentNode === outputArea) {
                    return currentWorkflowTrace;
                }
                const trace = document.createElement('div');
                trace.className = 'workflow-trace';
                const streaming = outputArea.querySelector('.message.ai-message.streaming');
                if (streaming) {
                    outputArea.insertBefore(trace, streaming);
                } else {
                    outputArea.appendChild(trace);
                }
                currentWorkflowTrace = trace;
                return trace;
            }

            // 渲染 / 更新一条工作状态气泡
            // event: {kind: hippo|skill|model, stage, state: running|done|error, title, detail}
            function workflowStep(event) {
                const ev = event || {};
                const kind = ev.kind || 'hippo';
                const stage = ev.stage || kind;
                const state = ev.state || 'done';
                const trace = ensureWorkflowTrace();
                if (!trace) return;
                const outputArea = trace.parentNode;

                let bubble = trace.querySelector('.workflow-bubble[data-wf-stage="' + stage + '"]');
                if (!bubble) {
                    bubble = document.createElement('div');
                    bubble.className = 'workflow-bubble wf-' + kind;
                    bubble.dataset.wfStage = stage;
                    const icon = document.createElement('span');
                    icon.className = 'wf-icon';
                    icon.textContent = WORKFLOW_ICONS[kind] || '⚙️';
                    const title = document.createElement('span');
                    title.className = 'wf-title';
                    const detail = document.createElement('span');
                    detail.className = 'wf-detail';
                    const status = document.createElement('span');
                    status.className = 'wf-status';
                    bubble.appendChild(icon);
                    bubble.appendChild(title);
                    bubble.appendChild(detail);
                    bubble.appendChild(status);
                    bubble._wfTitle = title;
                    bubble._wfDetail = detail;
                    bubble._wfWasRunning = false;
                    trace.appendChild(bubble);
                }

                if (ev.title) bubble._wfTitle.textContent = ev.title;
                if (ev.detail) bubble._wfDetail.textContent = ev.detail;
                bubble.title = bubble._wfTitle.textContent +
                    (bubble._wfDetail.textContent ? '：' + bubble._wfDetail.textContent : '');

                // 原地更新：把气泡切到目标状态
                const applyState = () => {
                    bubble.classList.remove('is-running', 'is-done', 'is-error', 'wf-error');
                    bubble.classList.add('is-' + state);
                    if (state === 'error') bubble.classList.add('wf-error');
                };

                if (state === 'done' && bubble._wfWasRunning) {
                    // 进行态过短会看不清，先留满最短时长再落定
                    const elapsed = Date.now() - (bubble._wfStartedAt || 0);
                    setTimeout(applyState, Math.max(0, WORKFLOW_MIN_RUNNING_MS - elapsed));
                } else {
                    applyState();
                }
                if (state === 'running') {
                    bubble._wfWasRunning = true;
                    bubble._wfStartedAt = Date.now();
                } else {
                    bubble._wfWasRunning = false;
                }

                if (outputArea) outputArea.scrollTop = outputArea.scrollHeight;
            }

            // 一轮结束：把仍在「进行中」的气泡落定（正常→✓，异常→!），并重置轨迹游标
            function finalizeWorkflowTrace(failed) {
                if (!currentWorkflowTrace) return;
                const bubbles = currentWorkflowTrace.querySelectorAll('.workflow-bubble.is-running');
                bubbles.forEach((b) => {
                    b.classList.remove('is-running');
                    b.classList.add(failed ? 'is-error' : 'is-done');
                    if (failed) b.classList.add('wf-error');
                    b._wfWasRunning = false;
                });
                currentWorkflowTrace.classList.add('wf-complete');
                currentWorkflowTrace = null;   // 下一轮另起一条轨迹（旧轨迹保留在对话里）
            }

            // 新开一轮：重置轨迹游标（旧轨迹保留在对话里）
            function resetWorkflowTrace() {
                currentWorkflowTrace = null;
            }

            // 显示用户消息反馈（用于隐藏控制台模式）
            function showUserMessageFeedback(text) {
                const loadingIndicator = document.getElementById('loading-indicator');
                const loadingText = document.getElementById('loading-text');
                
                if (loadingIndicator) {
                    loadingIndicator.style.display = 'flex';
                }
                
                if (loadingText) {
                    loadingText.textContent = `您: ${text}`;
                    loadingText.style.color = 'var(--primary-color)';
                }
            }
            
            // TTS API调用函数（使用设置中选择的音色，浏览器内播放）
            async function textToSpeech(text) {
                const voice = (typeof kiraraOptions !== 'undefined' && kiraraOptions.voice) || 'preset:kirara';
                const ok = await playKiraraTTS(text, voice);
                if (!ok) {
                    console.warn('TTS 播放失败');
                }
            }
            
            // 添加消息到聊天窗口
            function addMessage(text, sender) {
                const messageDiv = document.createElement('div');
                messageDiv.className = `message ${sender}-message`;
                
                const avatarImg = document.createElement('img');
                avatarImg.className = 'avatar';
                if (sender === 'ai') {
                    avatarImg.src = '/apps/kirara/sprites/logos/kirara-4.png';
                    avatarImg.alt = 'Kirara';
                } else {
                    avatarImg.src = '/static/sprites/logos/virtuaOS-1.png';
                    avatarImg.alt = 'User';
                }
                
                const contentWrapper = document.createElement('div');
                contentWrapper.className = 'message-content-wrapper';
                
                const contentDiv = document.createElement('div');
                contentDiv.className = 'message-content';
                if (sender === 'ai') {
                    contentDiv.innerHTML = renderMarkdown(text);
                } else {
                    contentDiv.textContent = text;
                }
                
                const timeDiv = document.createElement('div');
                timeDiv.className = 'message-time';
                timeDiv.textContent = getCurrentTime();
                
                contentWrapper.appendChild(contentDiv);
                contentWrapper.appendChild(timeDiv);
                
                messageDiv.appendChild(avatarImg);
                messageDiv.appendChild(contentWrapper);
                
                // 仅在AI消息中添加语音和复制按钮
                if (sender === 'ai') {
                    const speakButton = document.createElement('button');
                    speakButton.className = 'speak-button';
                    speakButton.innerHTML = '🔊';
                    speakButton.onclick = function() {
                        textToSpeech(text);
                    };
                    contentWrapper.appendChild(speakButton);
                    
                    const copyButtonsDiv = document.createElement('div');
                    copyButtonsDiv.className = 'copy-buttons';
                    
                    const copyMarkdownBtn = document.createElement('button');
                    copyMarkdownBtn.className = 'copy-button';
                    copyMarkdownBtn.innerHTML = '📝';
                    copyMarkdownBtn.title = '复制Markdown';
                    copyMarkdownBtn.onclick = function() {
                        copyToClipboard(text);
                        showCopyFeedback(copyMarkdownBtn);
                    };
                    copyButtonsDiv.appendChild(copyMarkdownBtn);
                    
                    const copyTextBtn = document.createElement('button');
                    copyTextBtn.className = 'copy-button';
                    copyTextBtn.innerHTML = '📄';
                    copyTextBtn.title = '复制纯文本';
                    copyTextBtn.onclick = function() {
                        copyToClipboard(contentDiv.innerText);
                        showCopyFeedback(copyTextBtn);
                    };
                    copyButtonsDiv.appendChild(copyTextBtn);
                    
                    contentWrapper.appendChild(copyButtonsDiv);
                }
                
                chatContainer.appendChild(messageDiv);
                chatContainer.scrollTop = chatContainer.scrollHeight;

                // 同步刷新上下文管理-短期记忆标签（若存在）
                if (typeof renderSessionHistory === 'function') renderSessionHistory();
            }

            // ===== 上下文管理：短期记忆渲染（原对话历史面板合并而来） =====
            function renderSessionHistory() {
                const list = document.getElementById('history-session-list');
                if (!list) return;
                list.innerHTML = '<div class="loading-text">正在加载短期记忆...</div>';
                fetch(KIRARA_API.MEMORY)
                    .then(r => r.json())
                    .then(data => {
                        if (data && data.success && data.memory) {
                            const content = data.memory;
                            if (!content || content.trim() === '') {
                                list.innerHTML = '<div class="loading-text">暂无短期记忆 — 开始对话后会出现在这里。</div>';
                                return;
                            }
                            if (content.includes('<div class="memory-date">') || content.includes('<div class="memory-user">')) {
                                list.innerHTML = `<div class="memory-content">${content}</div>`;
                            } else {
                                const escFn = (typeof window.escapeHtml === 'function')
                                    ? window.escapeHtml
                                    : (function() {
                                        const div = document.createElement('div');
                                        return function(text) {
                                            div.textContent = (text == null) ? '' : String(text);
                                            return div.innerHTML;
                                        };
                                    })();
                                const pairs = (typeof window.parseMemoryContent === 'function')
                                    ? window.parseMemoryContent(content)
                                    : null;
                                if (pairs && pairs.length > 0) {
                                    list.innerHTML = pairs.map(pair => {
                                        const userHtml = escFn(pair.user || '').replace(/\n/g, '<br>');
                                        const kiraraHtml = escFn(pair.kirara || '').replace(/\n/g, '<br>');
                                        return `<div class="memory-dialog-pair">
                                            <div class="memory-dialog-user">
                                                <span class="memory-dialog-label">👤 用户</span>
                                                <div class="memory-dialog-content">${userHtml}</div>
                                            </div>
                                            <div class="memory-dialog-kirara">
                                                <span class="memory-dialog-label">🤖 Kirara</span>
                                                <div class="memory-dialog-content">${kiraraHtml}</div>
                                            </div>
                                        </div>`;
                                    }).join('');
                                } else {
                                    list.innerHTML = `<div class="memory-raw-content">${escFn(content).replace(/\n/g, '<br>')}</div>`;
                                }
                            }
                        } else {
                            list.innerHTML = '<div class="loading-text">加载失败</div>';
                        }
                    })
                    .catch(() => {
                        list.innerHTML = '<div class="loading-text">加载失败</div>';
                    });
            }

            // 短期记忆刷新按钮（合并至上下文管理后，按钮仍在 session-panel 内）
            const refreshSessionBtn = document.getElementById('refresh-session-history');
            if (refreshSessionBtn) refreshSessionBtn.addEventListener('click', renderSessionHistory);

            // 模式切换通知气泡
            function addModeSwitchNotice(modeName, isEnabled) {
                const noticeDiv = document.createElement('div');
                noticeDiv.className = 'message mode-switch-notice';

                const bubble = document.createElement('div');
                bubble.className = `mode-switch-bubble ${isEnabled ? 'enabled' : 'disabled'}`;

                const icon = document.createElement('span');
                icon.className = 'mode-switch-icon';
                if (modeName === '低能耗模式') {
                    icon.textContent = '💤';
                } else if (modeName === '平衡模式') {
                    icon.textContent = '⚖️';
                } else if (modeName === '性能模式') {
                    icon.textContent = '🚀';
                } else if (modeName === '深度思考模式') {
                    icon.textContent = isEnabled ? '🔮' : '💤';
                } else if (modeName === 'Agent 模式') {
                    icon.textContent = isEnabled ? '🤖' : '💬';
                } else {
                    icon.textContent = isEnabled ? '💻' : '💤';
                }

                const textDiv = document.createElement('div');
                textDiv.className = 'mode-switch-text';

                const title = document.createElement('div');
                title.className = 'mode-switch-title';
                title.textContent = `${modeName}已激活`;

                const desc = document.createElement('div');
                desc.className = 'mode-switch-desc';
                if (modeName === '低能耗模式') {
                    desc.textContent = '快速响应，无额外思考';
                } else if (modeName === '平衡模式') {
                    desc.textContent = '专家人格分析，深度思考';
                } else if (modeName === '性能模式') {
                    desc.textContent = '深度推理优化，极致思考';
                } else if (modeName === '深度思考模式') {
                    desc.textContent = isEnabled ? '绮罗将使用专家人格进行深度分析和自我审查' : '绮罗将恢复日常模式，快速响应';
                } else if (modeName === 'Agent 模式') {
                    desc.textContent = isEnabled ? '绮罗罗将可以调用工具为您操作本机，危险操作会先征求同意' : '已退出 Agent 模式，恢复普通对话';
                } else {
                    desc.textContent = isEnabled ? '已切换到代码模式' : '已退出代码模式';
                }

                textDiv.appendChild(title);
                textDiv.appendChild(desc);

                const meta = document.createElement('div');
                meta.className = 'mode-switch-meta';
                meta.textContent = getCurrentTime();

                bubble.appendChild(icon);
                bubble.appendChild(textDiv);
                bubble.appendChild(meta);
                noticeDiv.appendChild(bubble);

                chatContainer.appendChild(noticeDiv);
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }

            // ==================== Agent 模式（Phase 1：只读闭环）====================
            const modeSwitchTrigger = document.getElementById('mode-switch-trigger');
            const modeSwitchText = modeSwitchTrigger ? modeSwitchTrigger.querySelector('.btn-text') : null;
            const modeSwitchIcon = modeSwitchTrigger ? modeSwitchTrigger.querySelector('.btn-icon') : null;
            const MODE_ICON_CHAT = '/static/sprites/logos/chatMode.png';
            const MODE_ICON_AGENT = '/static/sprites/logos/agentMode.png';
            // 启动时按优先级读取 ui_mode：①同步 XHR 预加载（最准） → ②localStorage 缓存 → ③默认 chat
            let agentMode = (function() {
                // ① 同步 XHR 预加载的 options（HTML 里先跑的 script 放进来的，100% 正确）
                var pre = window.__kirara_preloaded_options;
                if (pre && pre.ui_mode) return pre.ui_mode === 'agent';
                // ② localStorage 缓存（二次访问路径）
                try {
                    var cached = localStorage.getItem('kirara_ui_mode');
                    if (cached) return cached === 'agent';
                } catch (e) {}
                // ③ 兜底
                return false;
            })();

            // 应用 Agent/Chat 模式到界面（silent=true 时为启动回读，不弹气泡）
            function applyAgentModeUI(enabled, opts) {
                opts = opts || {};
                agentMode = !!enabled;
                if (modeSwitchTrigger) {
                    modeSwitchTrigger.classList.toggle('active', agentMode);
                    modeSwitchTrigger.title = agentMode ? '按下切换至Chat模式' : '按下切换至Agent模式';
                }
                if (modeSwitchText) modeSwitchText.textContent = agentMode ? 'Agent' : 'Chat';
                if (modeSwitchIcon) modeSwitchIcon.src = agentMode ? MODE_ICON_AGENT : MODE_ICON_CHAT;
                if (userInput) {
                    userInput.placeholder = agentMode
                        ? '向绮罗罗下达任务，例如：帮我看看这个项目的结构…'
                        : '和绮罗罗聊天或解决问题';
                }
                // Agent 模式锁定深度思考下拉（Agent 固定低能耗，避免与工具循环叠加）
                if (deepThinkBtn) {
                    deepThinkBtn.classList.toggle('agent-locked', agentMode);
                    deepThinkBtn.title = agentMode
                        ? 'Agent 模式下固定为低能耗'
                        : (modeConfig[thinkMode] ? modeConfig[thinkMode].title : '');
                }
                if (!opts.silent) {
                    addModeSwitchNotice('Agent 模式', agentMode);
                }
            }
            // 暴露给全局配置回读（initDisableAnime 拉取 options 后调用）
            window.applyKiraraUiMode = applyAgentModeUI;
            // Force Eject 按钮（闭包外）据此判断当前模式与活跃任务
            window.__kiraraIsAgentMode = function() { return !!agentMode; };

            // ==================== Phase 3：Agent 运行中止（abort / Force Eject）====================
            // 活跃运行登记表：runId → {state, stepsBox, abortBtn, onAbort()}
            // 挂起待审批时流虽关闭但条目不删，Force Eject 可同时作废审批卡片
            if (!window.__kiraraAgentRuns) {
                window.__kiraraAgentRuns = {};
            }
            function registerAgentRun(runId, entry) {
                if (runId) window.__kiraraAgentRuns[runId] = entry;
            }
            function unregisterAgentRun(runId) {
                if (runId) delete window.__kiraraAgentRuns[runId];
            }
            // 任务终结（正常/出错/中止/上限）：注销登记并收口中止按钮
            function finishAgentRun(state, mode) {
                if (state.runId) unregisterAgentRun(state.runId);
                if (state.abortBtn) {
                    if (mode === 'aborted') {
                        state.abortBtn.disabled = true;
                        state.abortBtn.textContent = '已中止';
                    } else {
                        state.abortBtn.classList.remove('visible');
                    }
                }
            }
            window.__kiraraActiveAgentRunIds = function() {
                return Object.keys(window.__kiraraAgentRuns);
            };

            // ==================== PR-1：Agent Task Session 持久化与任务列表 ====================
            // sessionStorage 持久化：最近 50 条 Agent task 元数据（与 Chat 的 default session 隔离）
            function getAgentTasks() {
                try {
                    const arr = JSON.parse(sessionStorage.getItem(AGENT_TASKS_STORAGE_KEY) || '[]');
                    return Array.isArray(arr) ? arr : [];
                } catch (e) { return []; }
            }
            function writeAgentTasks(tasks) {
                try {
                    sessionStorage.setItem(AGENT_TASKS_STORAGE_KEY, JSON.stringify(tasks.slice(0, 50)));
                } catch (e) { /* sessionStorage 满 or 不可用，静默降级 */ }
            }
            function saveAgentTask(task) {
                if (!task || !task.session_id) return;
                const tasks = getAgentTasks();
                const idx = tasks.findIndex(t => t.session_id === task.session_id);
                if (idx >= 0) tasks[idx] = task; else tasks.unshift(task);
                writeAgentTasks(tasks);
            }
            function updateAgentTaskStatus(sessionId, status) {
                if (!sessionId || !currentAgentTask) return;
                currentAgentTask.status = status;
                saveAgentTask(currentAgentTask);
                // 任务列表若已展开，同步刷新该卡片状态
                const card = document.querySelector(`.agent-task-card[data-sid="${sessionId}"]`);
                if (card) {
                    const badge = card.querySelector('.agent-task-status');
                    if (badge) {
                        badge.textContent = STATUS_LABELS[status] || status;
                        badge.dataset.status = status;
                    }
                }
            }
            const STATUS_LABELS = {
                running: '运行中', finished: '已完成', aborted: '已中止',
                error: '出错', suspended: '挂起审批', max_turns: '达上限'
            };
            function formatTaskTime(ts) {
                if (!ts) return '';
                const d = new Date(ts);
                const pad = n => String(n).padStart(2, '0');
                return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
            }
            // 拉取后端 task 列表（合并 sessionStorage 的本地状态与后端 session 文件）
            async function fetchAgentTasksFromServer() {
                try {
                    const resp = await fetch(KIRARA_API.AGENT_TASKS);
                    if (!resp.ok) return [];
                    const data = await resp.json();
                    return (data && data.tasks) || [];
                } catch (e) {
                    console.warn('拉取 Agent 任务列表失败:', e);
                    return [];
                }
            }
            // 合并本地 sessionStorage 与服务端 session 文件状态（服务端为主，本地补充进行中状态）
            async function loadAgentTasksMerged() {
                const serverTasks = await fetchAgentTasksFromServer();
                const localTasks = getAgentTasks();
                const localBySid = {};
                localTasks.forEach(t => { localBySid[t.session_id] = t; });
                // 服务端有但本地无 → 补全 status='finished'
                const merged = serverTasks.map(st => Object.assign({
                    session_id: st.session_id,
                    message: st.message || '',
                    created: (st.mtime || 0) * 1000,
                    status: 'finished',
                    message_count: st.message_count || 0,
                    summary: st.summary || ''
                }, localBySid[st.session_id] || {}));
                // 本地进行中（running/suspended）但服务端尚无文件 → 保留
                localTasks.forEach(lt => {
                    if (!serverTasks.find(st => st.session_id === lt.session_id) &&
                        (lt.status === 'running' || lt.status === 'suspended')) {
                        merged.unshift(lt);
                    }
                });
                return merged;
            }
            // 渲染任务列表面板（侧边栏）
            async function renderAgentTaskList() {
                const list = document.getElementById('agent-tasks-list');
                if (!list) return;
                list.innerHTML = '<div class="agent-tasks-loading">加载中…</div>';
                const tasks = await loadAgentTasksMerged();
                if (!tasks.length) {
                    list.innerHTML = '<div class="agent-tasks-empty">还没有 Agent 任务，切换到 Agent 模式试试吧～</div>';
                    return;
                }
                list.innerHTML = '';
                tasks.forEach(t => {
                    const card = document.createElement('div');
                    card.className = 'agent-task-card';
                    card.dataset.sid = t.session_id;
                    const status = t.status || 'finished';
                    const head = document.createElement('div');
                    head.className = 'agent-task-head';
                    const time = document.createElement('span');
                    time.className = 'agent-task-time';
                    time.textContent = formatTaskTime(t.created);
                    const badge = document.createElement('span');
                    badge.className = 'agent-task-status';
                    badge.dataset.status = status;
                    badge.textContent = STATUS_LABELS[status] || status;
                    head.appendChild(time);
                    head.appendChild(badge);
                    const msg = document.createElement('div');
                    msg.className = 'agent-task-message';
                    msg.textContent = t.message || '(空任务)';
                    msg.title = t.message || '';
                    const meta = document.createElement('div');
                    meta.className = 'agent-task-meta';
                    const metaBits = [];
                    if (t.message_count) metaBits.push(`${t.message_count} 条消息`);
                    if (t.summary) metaBits.push(`摘要: ${t.summary.slice(0, 40)}…`);
                    meta.textContent = metaBits.join(' · ');
                    // PR-2：根据 session 文件大小估算历史 token（粗略校准，提示用户该任务历史规模）
                    if (t.message_count && t.message) {
                        // 仅作展示，不参与防溢出逻辑（防溢出在后端实时触发）
                        const est = estimateTokens((t.message || '') + (t.summary || '')) + (t.message_count * 80);
                        const lvl = tokenLevel(est, TOKEN_BUDGET);
                        const tokenSpan = document.createElement('span');
                        tokenSpan.className = 'agent-task-tokens level-' + lvl;
                        tokenSpan.title = `历史估算约 ${est} tokens（仅参考）`;
                        tokenSpan.textContent = '≈' + est + ' tok';
                        meta.appendChild(tokenSpan);
                    }
                    const actions = document.createElement('div');
                    actions.className = 'agent-task-actions';
                    const cont = document.createElement('button');
                    cont.type = 'button';
                    cont.className = 'agent-task-btn continue';
                    cont.textContent = '继续追问';
                    cont.title = '在 Agent 模式下复用此 task 的 session_id 继续对话';
                    cont.onclick = (e) => { e.stopPropagation(); continueAgentTask(t.session_id); };
                    const del = document.createElement('button');
                    del.type = 'button';
                    del.className = 'agent-task-btn delete';
                    del.textContent = '删除';
                    del.title = '删除该 task 的 session 文件（不可恢复）';
                    del.onclick = (e) => { e.stopPropagation(); deleteAgentTask(t.session_id, card); };
                    actions.appendChild(cont);
                    actions.appendChild(del);
                    card.appendChild(head);
                    card.appendChild(msg);
                    if (meta.textContent || meta.children.length) card.appendChild(meta);
                    card.appendChild(actions);
                    list.appendChild(card);
                });
            }
            // "继续追问"：切到 Agent 模式 + 设置下次复用的 session_id + 聚焦输入框
            function continueAgentTask(sid) {
                if (!sid) return;
                if (!agentMode) {
                    applyAgentModeUI(true);
                }
                continueAgentSessionId = sid;
                if (typeof addModeSwitchNotice === 'function') {
                    addModeSwitchNotice('继续追问', true);
                }
                // 关闭任务列表面板，回到对话视图
                if (typeof chatUIBtn !== 'undefined' && chatUIBtn) chatUIBtn.click();
                if (userInput) {
                    userInput.focus();
                    userInput.placeholder = '继续追问此任务（如：刚才的结果再帮我…）';
                }
            }
            // 删除 task：调后端 DELETE + 本地 sessionStorage 移除 + 卡片淡出
            async function deleteAgentTask(sid, cardEl) {
                if (!sid) return;
                if (!window.confirm('删除该 Agent 任务的 session 文件？此操作不可恢复。')) return;
                try {
                    const resp = await fetch(`/api/kirara/agent/tasks/${encodeURIComponent(sid)}`, {
                        method: 'DELETE'
                    });
                    if (!resp.ok) {
                        const err = await resp.json().catch(() => ({}));
                        window.alert(err.error || `删除失败: ${resp.status}`);
                        return;
                    }
                    // 本地移除
                    const tasks = getAgentTasks().filter(t => t.session_id !== sid);
                    writeAgentTasks(tasks);
                    if (cardEl) {
                        cardEl.classList.add('removing');
                        setTimeout(() => cardEl.remove(), 200);
                    }
                } catch (e) {
                    window.alert(`删除失败: ${e.message}`);
                }
            }

            // ==================== PR-2：用量管理面板（"选项 > 用量管理"）====================
            // 用量统计：从后端拉取 task 列表计算总/平均 token，并展示当前会话用量
            async function loadUsageStats() {
                // 1. Chat 会话用量：估算当前 conversationHistory 长度
                const chatText = (typeof conversationHistory !== 'undefined' && conversationHistory)
                    ? conversationHistory.map(m => (m && (m.content || m.role)) || '').join('\n')
                    : '';
                const chatTokens = estimateTokens(chatText);
                updateUsageBar('usage-chat', chatTokens, TOKEN_BUDGET);
                const chatEl = document.getElementById('usage-chat-tokens');
                if (chatEl) chatEl.textContent = `${chatTokens} / ${TOKEN_BUDGET} tokens`;

                // 2. Agent 当前任务用量：从 currentAgentTaskTokens 取
                const agentTokens = currentAgentTaskTokens.prompt || 0;
                if (agentTokens > 0) {
                    updateUsageBar('usage-agent', agentTokens, TOKEN_BUDGET);
                    const agentEl = document.getElementById('usage-agent-tokens');
                    if (agentEl) agentEl.textContent = `${agentTokens} / ${TOKEN_BUDGET} tokens`;
                } else {
                    const agentEl = document.getElementById('usage-agent-tokens');
                    if (agentEl) agentEl.textContent = '未运行';
                    updateUsageBar('usage-agent', 0, TOKEN_BUDGET);
                }
                // 压缩次数：从 sessionStorage 累计统计（若 currentAgentTask 存在）
                const compactionEl = document.getElementById('usage-compaction-count');
                if (compactionEl) {
                    const cnt = (window.__kiraraCompactionCount || 0);
                    compactionEl.textContent = `本任务已触发压缩 ${cnt} 次`;
                }

                // 3. 任务历史统计：拉取后端 task 列表计算
                try {
                    const tasks = await loadAgentTasksMerged();
                    const totalTasks = tasks.length;
                    let totalTokens = 0;
                    tasks.forEach(t => {
                        // 估算每任务 token：基于消息数 × 平均 80 + 首句 + 摘要
                        totalTokens += (t.message_count || 0) * 80 + estimateTokens(t.message || '') + estimateTokens(t.summary || '');
                    });
                    const avg = totalTasks ? Math.round(totalTokens / totalTasks) : 0;
                    const tt = document.getElementById('usage-total-tasks');
                    const tk = document.getElementById('usage-total-tokens');
                    const ta = document.getElementById('usage-avg-tokens');
                    if (tt) tt.textContent = totalTasks;
                    if (tk) tk.textContent = totalTokens.toLocaleString();
                    if (ta) ta.textContent = avg.toLocaleString();
                } catch (e) {
                    console.warn('加载任务历史统计失败:', e);
                }
            }
            // 更新用量条 + 百分比 + 颜色等级
            function updateUsageBar(prefix, current, budget) {
                const bar = document.getElementById(prefix + '-bar');
                const txt = document.getElementById(prefix + '-bar-text');
                const pct = budget > 0 ? (current / budget * 100) : 0;
                if (bar) {
                    bar.style.width = Math.min(100, pct) + '%';
                    bar.className = 'usage-bar-fill level-' + tokenLevel(current, budget);
                }
                if (txt) txt.textContent = pct.toFixed(1) + '%';
            }
            // 保存用量配置到 options.json（持久化，供后端未来读取）
            async function saveUsageConfig() {
                const cfg = {
                    usage_auto_compaction: document.getElementById('usage-auto-compaction').checked,
                    usage_compaction_threshold_pct: parseInt(document.getElementById('usage-threshold-slider').value, 10),
                    usage_keep_recent: parseInt(document.getElementById('usage-keep-recent-slider').value, 10),
                    usage_task_hard_limit: parseInt(document.getElementById('usage-hard-limit-slider').value, 10)
                };
                try {
                    const resp = await fetch(KIRARA_API.OPTIONS, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(cfg)
                    });
                    if (!resp.ok) {
                        const err = await resp.json().catch(() => ({}));
                        window.alert(err.error || `保存失败: ${resp.status}`);
                        return;
                    }
                    // 同步到全局 kiraraOptions
                    if (typeof kiraraOptions !== 'undefined') {
                        Object.assign(kiraraOptions, cfg);
                    }
                    window.alert('用量配置已保存');
                } catch (e) {
                    window.alert(`保存失败: ${e.message}`);
                }
            }
            // 从 kiraraOptions 加载已保存的配置到 UI
            function loadUsageConfigToUI() {
                if (typeof kiraraOptions === 'undefined') return;
                const auto = document.getElementById('usage-auto-compaction');
                const thrSlider = document.getElementById('usage-threshold-slider');
                const keepSlider = document.getElementById('usage-keep-recent-slider');
                const hardSlider = document.getElementById('usage-hard-limit-slider');
                if (auto) auto.checked = kiraraOptions.usage_auto_compaction !== false;
                if (thrSlider) thrSlider.value = kiraraOptions.usage_compaction_threshold_pct || 80;
                if (keepSlider) keepSlider.value = kiraraOptions.usage_keep_recent || 3;
                if (hardSlider) hardSlider.value = kiraraOptions.usage_task_hard_limit || 14000;
                // 同步显示文本
                const thrVal = document.getElementById('usage-threshold-value');
                const keepVal = document.getElementById('usage-keep-recent-value');
                const hardVal = document.getElementById('usage-hard-limit-value');
                if (thrVal) thrVal.textContent = (thrSlider ? thrSlider.value : 80) + '%';
                if (keepVal) keepVal.textContent = keepSlider ? keepSlider.value : 3;
                if (hardVal) hardVal.textContent = hardSlider ? hardSlider.value : 14000;
            }
            // 初始化滑块联动 + 按钮事件（仅在面板元素存在时执行）
            (function initUsagePanel() {
                const thrSlider = document.getElementById('usage-threshold-slider');
                const keepSlider = document.getElementById('usage-keep-recent-slider');
                const hardSlider = document.getElementById('usage-hard-limit-slider');
                if (thrSlider) {
                    thrSlider.addEventListener('input', function() {
                        const v = document.getElementById('usage-threshold-value');
                        if (v) v.textContent = this.value + '%';
                    });
                }
                if (keepSlider) {
                    keepSlider.addEventListener('input', function() {
                        const v = document.getElementById('usage-keep-recent-value');
                        if (v) v.textContent = this.value;
                    });
                }
                if (hardSlider) {
                    hardSlider.addEventListener('input', function() {
                        const v = document.getElementById('usage-hard-limit-value');
                        if (v) v.textContent = this.value;
                    });
                }
                const saveBtn = document.getElementById('usage-save-config');
                if (saveBtn) saveBtn.addEventListener('click', saveUsageConfig);
                const refreshBtn = document.getElementById('usage-refresh-stats');
                if (refreshBtn) refreshBtn.addEventListener('click', loadUsageStats);
            })();

            // ============================================================
            // 使用时间统计模块（选项 > 使用时间）
            // —— 前端 localStorage 自记录：每日使用时长 + token 损耗
            // 不依赖后端改动，token 估算与 estimateTokens 同口径
            // ============================================================
            const UT_STORAGE_KEY = 'kirara_usage_daily';
            // 当前图表展示的日期范围（天数），默认 14
            let utRangeDays = 14;
            // 正在进行的会话计时起点（sendMessage 时置位，响应结束时结算）
            let utExchangeStart = 0;

            // 读取全部日维度用量记录：{ 'YYYY-MM-DD': { time_ms, input_tokens, output_tokens, exchanges } }
            function utReadAll() {
                try {
                    const raw = localStorage.getItem(UT_STORAGE_KEY);
                    if (!raw) return {};
                    const obj = JSON.parse(raw);
                    return (obj && typeof obj === 'object') ? obj : {};
                } catch (e) { return {}; }
            }
            // 写回全部记录
            function utWriteAll(data) {
                try {
                    localStorage.setItem(UT_STORAGE_KEY, JSON.stringify(data));
                } catch (e) { console.warn('使用时间记录写入失败:', e); }
            }
            // 当日 key（本地时区）
            function utTodayKey() {
                const d = new Date();
                const y = d.getFullYear();
                const m = String(d.getMonth() + 1).padStart(2, '0');
                const day = String(d.getDate()).padStart(2, '0');
                return `${y}-${m}-${day}`;
            }
            // 累加一条用量到当日记录
            function recordDailyUsage({ inputTokens, outputTokens, durationMs }) {
                if (!Number.isFinite(inputTokens)) inputTokens = 0;
                if (!Number.isFinite(outputTokens)) outputTokens = 0;
                if (!Number.isFinite(durationMs) || durationMs < 0) durationMs = 0;
                const all = utReadAll();
                const key = utTodayKey();
                if (!all[key]) all[key] = { time_ms: 0, input_tokens: 0, output_tokens: 0, exchanges: 0 };
                all[key].time_ms += durationMs;
                all[key].input_tokens += inputTokens;
                all[key].output_tokens += outputTokens;
                all[key].exchanges += 1;
                utWriteAll(all);
            }
            // ============================================================
            // 每日 Token 限制器配置（localStorage 自记录）
            // —— enabled：开关（可选择性关闭）
            // —— limit：限制器上限值
            // —— locked：锁定后无法更改上限与开关（需先解锁）
            // ============================================================
            const UT_LIMIT_KEY = 'kirara_usage_limit_config';
            const UT_LIMIT_DEFAULT = { enabled: false, limit: 50000, locked: false };
            function utReadLimitConfig() {
                try {
                    const raw = localStorage.getItem(UT_LIMIT_KEY);
                    if (!raw) return Object.assign({}, UT_LIMIT_DEFAULT);
                    const obj = JSON.parse(raw);
                    return {
                        enabled: obj.enabled === true,
                        limit: Number.isFinite(obj.limit) && obj.limit > 0 ? obj.limit : UT_LIMIT_DEFAULT.limit,
                        locked: obj.locked === true
                    };
                } catch (e) { return Object.assign({}, UT_LIMIT_DEFAULT); }
            }
            function utWriteLimitConfig(cfg) {
                try { localStorage.setItem(UT_LIMIT_KEY, JSON.stringify(cfg)); } catch (e) { console.warn('限制器配置写入失败:', e); }
            }
            // 今日是否已达上限（供 sendMessage 在发送前检查）
            function utIsLimitExceeded() {
                const cfg = utReadLimitConfig();
                if (!cfg.enabled) return false;
                const all = utReadAll();
                const rec = all[utTodayKey()] || { input_tokens: 0, output_tokens: 0 };
                return (rec.input_tokens + rec.output_tokens) >= cfg.limit;
            }
            // 根据锁定状态禁用/启用上限滑块与开关（锁本身始终可点）
            function utApplyLockState() {
                const cfg = utReadLimitConfig();
                const en = document.getElementById('ut-limit-enabled');
                const sl = document.getElementById('ut-limit-slider');
                const val = document.getElementById('ut-limit-value');
                if (en) en.disabled = cfg.locked;
                if (sl) sl.disabled = cfg.locked;
                // 锁定提示文案
                const lockLabel = document.getElementById('ut-limit-lock-label');
                if (lockLabel) lockLabel.textContent = cfg.locked
                    ? '🔓 点击解锁（当前已锁定：上限与开关均不可更改）'
                    : '🔒 锁定限制器（锁定后无法更改上限与开关，需先解锁）';
                // 锁定遮罩
                const block = document.getElementById('ut-limit-block');
                if (block) block.classList.toggle('is-locked', cfg.locked);
            }
            // 加载限制器配置到 UI
            function utLoadLimitConfigToUI() {
                const cfg = utReadLimitConfig();
                const en = document.getElementById('ut-limit-enabled');
                const sl = document.getElementById('ut-limit-slider');
                const lk = document.getElementById('ut-limit-locked');
                const val = document.getElementById('ut-limit-value');
                if (en) en.checked = cfg.enabled;
                if (sl) sl.value = cfg.limit;
                if (lk) lk.checked = cfg.locked;
                if (val) val.textContent = utFmt(cfg.limit) + ' tokens';
                utApplyLockState();
            }
            // 刷新今日进度条 + 超限警告
            function utUpdateLimitProgress() {
                const cfg = utReadLimitConfig();
                const all = utReadAll();
                const rec = all[utTodayKey()] || { input_tokens: 0, output_tokens: 0 };
                const used = rec.input_tokens + rec.output_tokens;
                const limit = cfg.limit || 1;
                const pct = limit > 0 ? Math.min(100, (used / limit) * 100) : 0;
                const bar = document.getElementById('ut-limit-bar');
                const txt = document.getElementById('ut-limit-bar-text');
                if (bar) {
                    bar.style.width = pct + '%';
                    bar.className = 'usage-bar-fill level-' + tokenLevel(used, limit);
                }
                if (txt) txt.textContent = pct.toFixed(1) + '%';
                const warn = document.getElementById('ut-limit-warning');
                if (warn) warn.style.display = (cfg.enabled && used >= limit) ? 'block' : 'none';
            }
            // 取最近 N 天的有序数组（含今日，缺失日期补零）
            function utLastNDays(n) {
                const all = utReadAll();
                const arr = [];
                const today = new Date();
                for (let i = n - 1; i >= 0; i--) {
                    const d = new Date(today);
                    d.setDate(d.getDate() - i);
                    const y = d.getFullYear();
                    const m = String(d.getMonth() + 1).padStart(2, '0');
                    const day = String(d.getDate()).padStart(2, '0');
                    const key = `${y}-${m}-${day}`;
                    const rec = all[key] || { time_ms: 0, input_tokens: 0, output_tokens: 0, exchanges: 0 };
                    arr.push({ date: key, label: `${m}/${day}`, ...rec });
                }
                return arr;
            }
            // 友好时长格式：ms → "x 小时 y 分钟" / "x 分钟" / "x 秒"
            function utFormatDuration(ms) {
                const s = Math.floor(ms / 1000);
                if (s < 60) return s + ' 秒';
                const m = Math.floor(s / 60);
                if (m < 60) return m + ' 分钟';
                const h = Math.floor(m / 60);
                return h + ' 小时 ' + (m % 60) + ' 分钟';
            }
            // 数字千分位
            function utFmt(n) { return Number(n || 0).toLocaleString(); }

            // SVG 柱状图渲染：单指标（usage time），data=[{date,label,time_ms}]
            function utRenderTimeChart(data) {
                const svg = document.getElementById('ut-time-chart');
                const empty = document.getElementById('ut-time-chart-empty');
                if (!svg) return;
                const hasData = data.some(d => d.time_ms > 0);
                if (!hasData) {
                    svg.innerHTML = '';
                    if (empty) empty.style.display = 'block';
                    return;
                }
                if (empty) empty.style.display = 'none';
                const W = 800, H = 300, padL = 50, padR = 16, padT = 16, padB = 40;
                const plotW = W - padL - padR, plotH = H - padT - padB;
                const maxV = Math.max(1, ...data.map(d => d.time_ms));
                // 纵轴自适应 4 等分
                const ticks = 4;
                let unit = '分钟';
                let scale = v => v / 60000; // ms -> min
                if (maxV < 60000) { unit = '秒'; scale = v => v / 1000; }
                const maxScaled = Math.max(1, ...data.map(d => scale(d.time_ms)));
                // 向上取整到整数刻度，避免柱顶贴边
                const niceMax = Math.ceil(maxScaled * 1.15);
                const bw = plotW / data.length * 0.6;
                const gap = plotW / data.length * 0.4;
                let svgStr = '';
                // 网格线 + Y 轴刻度
                for (let i = 0; i <= ticks; i++) {
                    const val = (niceMax / ticks) * i;
                    const y = padT + plotH - (val / niceMax) * plotH;
                    svgStr += `<line x1="${padL}" y1="${y}" x2="${W - padR}" y2="${y}" stroke="rgba(138,43,226,0.12)" stroke-width="1"/>`;
                    svgStr += `<text x="${padL - 6}" y="${y + 4}" text-anchor="end" font-size="11" fill="#888">${val.toFixed(val < 10 ? 1 : 0)}</text>`;
                }
                svgStr += `<text x="${padL - 36}" y="${padT + plotH / 2}" transform="rotate(-90 ${padL - 36} ${padT + plotH / 2})" text-anchor="middle" font-size="11" fill="#8a2be2">时长（${unit}）</text>`;
                // 柱子
                data.forEach((d, i) => {
                    const x = padL + (plotW / data.length) * i + gap / 2;
                    const v = scale(d.time_ms);
                    const h = (v / niceMax) * plotH;
                    const y = padT + plotH - h;
                    svgStr += `<rect x="${x}" y="${y}" width="${bw}" height="${h}" rx="3" fill="url(#utTimeGrad)"/>`;
                    // X 轴标签（点过多时隔点显示）
                    const showLabel = data.length <= 14 || i % 2 === 0;
                    if (showLabel) {
                        svgStr += `<text x="${x + bw / 2}" y="${H - padB + 14}" text-anchor="middle" font-size="10" fill="#888">${d.label}</text>`;
                    }
                });
                // defs 渐变
                const defs = `<defs><linearGradient id="utTimeGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="#ff69b4"/><stop offset="100%" stop-color="#8a2be2"/>
                </linearGradient></defs>`;
                svg.innerHTML = defs + svgStr;
            }
            // SVG 堆叠柱状图：token 损耗（输入 + 输出）
            function utRenderTokenChart(data) {
                const svg = document.getElementById('ut-token-chart');
                const empty = document.getElementById('ut-token-chart-empty');
                if (!svg) return;
                const hasData = data.some(d => (d.input_tokens + d.output_tokens) > 0);
                if (!hasData) {
                    svg.innerHTML = '';
                    if (empty) empty.style.display = 'block';
                    return;
                }
                if (empty) empty.style.display = 'none';
                const W = 800, H = 300, padL = 50, padR = 16, padT = 16, padB = 40;
                const plotW = W - padL - padR, plotH = H - padT - padB;
                const totals = data.map(d => d.input_tokens + d.output_tokens);
                const maxV = Math.max(1, ...totals);
                const ticks = 4;
                // 向上取整到友好刻度
                const niceMax = Math.ceil(maxV * 1.15);
                const bw = plotW / data.length * 0.6;
                const gap = plotW / data.length * 0.4;
                let svgStr = '';
                for (let i = 0; i <= ticks; i++) {
                    const val = (niceMax / ticks) * i;
                    const y = padT + plotH - (val / niceMax) * plotH;
                    svgStr += `<line x1="${padL}" y1="${y}" x2="${W - padR}" y2="${y}" stroke="rgba(138,43,226,0.12)" stroke-width="1"/>`;
                    svgStr += `<text x="${padL - 6}" y="${y + 4}" text-anchor="end" font-size="11" fill="#888">${val.toLocaleString()}</text>`;
                }
                svgStr += `<text x="${padL - 36}" y="${padT + plotH / 2}" transform="rotate(-90 ${padL - 36} ${padT + plotH / 2})" text-anchor="middle" font-size="11" fill="#8a2be2">Token 数</text>`;
                data.forEach((d, i) => {
                    const x = padL + (plotW / data.length) * i + gap / 2;
                    const total = d.input_tokens + d.output_tokens;
                    const totalH = (total / niceMax) * plotH;
                    const inH = (d.input_tokens / niceMax) * plotH;
                    const outH = (d.output_tokens / niceMax) * plotH;
                    const yBase = padT + plotH;
                    // 输入在下
                    svgStr += `<rect x="${x}" y="${yBase - inH}" width="${bw}" height="${inH}" rx="3" fill="url(#utInputGrad)"/>`;
                    // 输出在上
                    svgStr += `<rect x="${x}" y="${yBase - totalH}" width="${bw}" height="${outH}" fill="url(#utOutputGrad)"/>`;
                    const showLabel = data.length <= 14 || i % 2 === 0;
                    if (showLabel) {
                        svgStr += `<text x="${x + bw / 2}" y="${H - padB + 14}" text-anchor="middle" font-size="10" fill="#888">${d.label}</text>`;
                    }
                });
                const defs = `<defs>
                    <linearGradient id="utInputGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#7bc96f"/><stop offset="100%" stop-color="#4caf50"/></linearGradient>
                    <linearGradient id="utOutputGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#ffb74d"/><stop offset="100%" stop-color="#ff9800"/></linearGradient>
                </defs>`;
                svg.innerHTML = defs + svgStr;
            }
            // 加载并渲染使用时间面板
            function loadUsageTimeStats() {
                const data = utLastNDays(utRangeDays);
                // 概览卡片
                const today = data[data.length - 1] || { time_ms: 0, input_tokens: 0, output_tokens: 0, exchanges: 0 };
                const setEl = (id, txt) => { const el = document.getElementById(id); if (el) el.textContent = txt; };
                setEl('ut-today-time', utFormatDuration(today.time_ms));
                setEl('ut-today-exchanges', (today.exchanges || 0) + ' 次对话');
                setEl('ut-today-tokens', utFmt(today.input_tokens + today.output_tokens));
                setEl('ut-today-tokens-breakdown', `输入 ${utFmt(today.input_tokens)} · 输出 ${utFmt(today.output_tokens)}`);
                const sum7 = data.slice(-7).reduce((a, d) => ({ time_ms: a.time_ms + d.time_ms, input_tokens: a.input_tokens + d.input_tokens, output_tokens: a.output_tokens + d.output_tokens }), { time_ms: 0, input_tokens: 0, output_tokens: 0 });
                const sum30 = data.slice(-30).reduce((a, d) => ({ time_ms: a.time_ms + d.time_ms, input_tokens: a.input_tokens + d.input_tokens, output_tokens: a.output_tokens + d.output_tokens }), { time_ms: 0, input_tokens: 0, output_tokens: 0 });
                setEl('ut-7d-time', utFormatDuration(sum7.time_ms));
                setEl('ut-7d-tokens', utFmt(sum7.input_tokens + sum7.output_tokens) + ' tokens');
                setEl('ut-30d-time', utFormatDuration(sum30.time_ms));
                setEl('ut-30d-tokens', utFmt(sum30.input_tokens + sum30.output_tokens) + ' tokens');
                // 趋势图
                utRenderTimeChart(data);
                utRenderTokenChart(data);
                // 每日限制器配置与今日进度
                utLoadLimitConfigToUI();
                utUpdateLimitProgress();
            }
            // 使用时间面板事件绑定
            (function initUsageTimePanel() {
                function setRange(n) {
                    utRangeDays = n;
                    ['ut-range-7', 'ut-range-14', 'ut-range-30'].forEach(id => {
                        const b = document.getElementById(id);
                        if (!b) return;
                        b.classList.toggle('primary', id === 'ut-range-' + n);
                    });
                    loadUsageTimeStats();
                }
                const r7 = document.getElementById('ut-range-7');
                const r14 = document.getElementById('ut-range-14');
                const r30 = document.getElementById('ut-range-30');
                if (r7) r7.addEventListener('click', () => setRange(7));
                if (r14) r14.addEventListener('click', () => setRange(14));
                if (r30) r30.addEventListener('click', () => setRange(30));
                const refresh = document.getElementById('ut-refresh');
                if (refresh) refresh.addEventListener('click', loadUsageTimeStats);

                // —— 每日 Token 限制器事件 ——
                // 锁本身：始终可点，切换后立即持久化并禁用/启用上限与开关
                const lock = document.getElementById('ut-limit-locked');
                if (lock) lock.addEventListener('change', function() {
                    const cfg = utReadLimitConfig();
                    cfg.locked = this.checked;
                    utWriteLimitConfig(cfg);
                    utApplyLockState();
                    // 锁定后强制同步开关/滑块的 checked/value 到已存配置（防止 UI 残留未保存改动）
                    utLoadLimitConfigToUI();
                    utUpdateLimitProgress();
                });
                // 开关：仅在未锁定时可改
                const en = document.getElementById('ut-limit-enabled');
                if (en) en.addEventListener('change', function() {
                    if (this.disabled) return;
                    const cfg = utReadLimitConfig();
                    cfg.enabled = this.checked;
                    utWriteLimitConfig(cfg);
                    utUpdateLimitProgress();
                });
                // 上限滑块：仅在未锁定时可改，实时更新标签与进度
                const sl = document.getElementById('ut-limit-slider');
                if (sl) sl.addEventListener('input', function() {
                    if (this.disabled) return;
                    const cfg = utReadLimitConfig();
                    cfg.limit = parseInt(this.value, 10);
                    utWriteLimitConfig(cfg);
                    const val = document.getElementById('ut-limit-value');
                    if (val) val.textContent = utFmt(cfg.limit) + ' tokens';
                    utUpdateLimitProgress();
                });
            })();
            // 暴露给外部钩子使用：记录一次对话用量
            window.__kiraraRecordUsage = recordDailyUsage;
            // 暴露限制器检查：sendMessage 在发送前调用
            window.__kiraraIsLimitExceeded = utIsLimitExceeded;
            // 暴露面板加载函数：选项卡切换（kirara.html 内联脚本）通过 typeof 检查调用
            window.loadUsageTimeStats = loadUsageTimeStats;
            // 请求中止：POST 同源 /api/kirara/agent/abort；前端即时禁用审批/按钮，服务端事件随后到达
            window.__kiraraAbortAgent = async function(runId) {
                const entry = window.__kiraraAgentRuns[runId];
                if (entry) {
                    entry.state.aborted = true;
                    if (entry.abortBtn) {
                        entry.abortBtn.disabled = true;
                        entry.abortBtn.textContent = '正在中止…';
                    }
                    addAgentStep(entry.stepsBox, 'agent-step-status', '中止', '正在请求中止任务…');
                    outputArea.scrollTop = outputArea.scrollHeight;
                    // 挂起审批中等候的卡片：作废并解除 readAgentStream 的等待
                    if (typeof entry.onAbort === 'function') {
                        try { entry.onAbort(); } catch (e) {}
                    }
                }
                try {
                    const resp = await fetch(KIRARA_API.AGENT_ABORT, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ run_id: runId })
                    });
                    if (!resp.ok) {
                        const errData = await resp.json().catch(() => ({}));
                        if (entry) {
                            addAgentStep(entry.stepsBox, 'agent-step-error', '错误',
                                errData.error || `中止请求失败: ${resp.status}`);
                        }
                    }
                } catch (e) {
                    console.error('Agent abort 请求失败:', e);
                    if (entry) {
                        addAgentStep(entry.stepsBox, 'agent-step-error', '错误',
                            '中止请求失败: ' + (e.message || e));
                    }
                }
            };

            if (modeSwitchTrigger) {
                modeSwitchTrigger.addEventListener('click', function() {
                    const next = !agentMode;
                    applyAgentModeUI(next);
                    kiraraOptions.ui_mode = next ? 'agent' : 'chat';
                    saveOptions();
                });
            }

            // Agent 计划 checklist 卡片渲染（路径 A 轻量日程表）
            function renderPlanCard(stepsBox, steps) {
                if (!steps || !steps.length) return null;
                const card = document.createElement('div');
                card.className = 'agent-plan-card';

                const head = document.createElement('div');
                head.className = 'agent-plan-head';
                head.textContent = '📋 执行计划';
                card.appendChild(head);

                const list = document.createElement('ul');
                list.className = 'agent-plan-list';
                card.appendChild(list);

                steps.forEach((text, idx) => {
                    const li = document.createElement('li');
                    li.className = 'agent-plan-item';
                    li.dataset.idx = idx;
                    const check = document.createElement('span');
                    check.className = 'agent-plan-check';
                    check.textContent = '○';
                    const label = document.createElement('span');
                    label.className = 'agent-plan-label';
                    label.textContent = text;
                    li.appendChild(check);
                    li.appendChild(label);
                    list.appendChild(li);
                });

                stepsBox.appendChild(card);
                stepsBox.scrollTop = stepsBox.scrollHeight;
                return card;
            }

            // 更新计划进度：done_count 个步骤标记完成
            function updatePlanProgress(card, steps, doneCount) {
                if (!card || !steps) return;
                const items = card.querySelectorAll('.agent-plan-item');
                items.forEach((li, idx) => {
                    const check = li.querySelector('.agent-plan-check');
                    if (idx < doneCount) {
                        li.classList.add('plan-done');
                        if (check) check.textContent = '✓';
                    } else if (idx === doneCount) {
                        li.classList.add('plan-running');
                        if (check) check.textContent = '◉';
                    } else {
                        li.classList.remove('plan-done', 'plan-running');
                        if (check) check.textContent = '○';
                    }
                });
            }

            // Agent 过程步骤卡片（思考/工具/结果/错误）
            function addAgentStep(stepsBox, cls, tag, text) {
                const step = document.createElement('div');
                step.className = 'agent-step ' + cls;

                const tagSpan = document.createElement('span');
                tagSpan.className = 'agent-step-tag';
                tagSpan.textContent = tag;

                const bodySpan = document.createElement('span');
                bodySpan.className = 'agent-step-body';
                bodySpan.textContent = text || '';

                step.appendChild(tagSpan);
                step.appendChild(bodySpan);
                stepsBox.appendChild(step);
                outputArea.scrollTop = outputArea.scrollHeight;
                return step;
            }

            // Agent 事件处理：渲染步骤卡片；遇 approval_required 弹出审批卡并续读 /approve 流
            async function handleAgentEvent(parsed, stepsBox, state) {
                switch (parsed.event) {
                    case 'run_started':
                        state.runId = parsed.run_id;
                        state.planSteps = null;
                        state.planCard = null;
                        addAgentStep(stepsBox, 'agent-step-status', '开始', '绮罗罗开始执行任务…');
                        // 登记活跃运行（供进行中止按钮 / Force Eject 查找）
                        if (state.abortBtn) {
                            state.abortBtn.classList.add('visible');
                            state.abortBtn.disabled = false;
                            state.abortBtn.textContent = '■ 中止任务';
                        }
                        registerAgentRun(state.runId, {
                            state: state,
                            stepsBox: stepsBox,
                            abortBtn: state.abortBtn || null,
                            onAbort: null
                        });
                        // PR-1：落盘 task 元数据（run_id 已知，供任务列表展示与"继续追问"）
                        if (currentAgentTask && state.taskSessionId) {
                            currentAgentTask.run_id = parsed.run_id;
                            saveAgentTask(currentAgentTask);
                        }
                        break;
                    case 'plan':
                        // 渲染执行计划 checklist（一次，后续 plan_progress 更新状态）
                        state.planSteps = parsed.steps || [];
                        state.planDone = 0;
                        state.planCard = renderPlanCard(stepsBox, state.planSteps);
                        break;
                    case 'plan_progress':
                        // 更新计划进度：新工具成功执行，推进 1 步
                        if (state.planCard && state.planSteps) {
                            state.planDone = parsed.done_count || (state.planDone + 1);
                            updatePlanProgress(state.planCard, state.planSteps, state.planDone);
                        }
                        break;
                    case 'thought':
                        addAgentStep(stepsBox, 'agent-step-thought', '思考', parsed.content || '');
                        break;
                    case 'tool_call':
                        addAgentStep(stepsBox, 'agent-step-tool', '工具',
                            `${parsed.tool || '?'}(${JSON.stringify(parsed.input || {})})`);
                        break;
                    case 'tool_result':
                        if (parsed.ok) {
                            addAgentStep(stepsBox, 'agent-step-result', '结果', parsed.output || '（空）');
                        } else {
                            addAgentStep(stepsBox, 'agent-step-error', '错误', parsed.error || '工具执行失败');
                        }
                        break;
                    case 'approval_required':
                        await showApprovalCard(stepsBox, parsed, state);
                        // PR-1：挂起待审批状态落盘（侧边栏可看到"挂起"徽章）
                        updateAgentTaskStatus(state.taskSessionId, 'suspended');
                        break;
                    case 'final':
                        state.finalText = parsed.content || '';
                        // 任务终结：plan 卡片全部标记完成
                        if (state.planCard && state.planSteps) {
                            state.planDone = state.planSteps.length;
                            updatePlanProgress(state.planCard, state.planSteps, state.planDone);
                        }
                        finishAgentRun(state, 'final');
                        // PR-1：终结状态落盘
                        updateAgentTaskStatus(state.taskSessionId, 'finished');
                        break;
                    case 'error':
                        addAgentStep(stepsBox, 'agent-step-error', '错误', parsed.message || '未知错误');
                        finishAgentRun(state, 'error');
                        updateAgentTaskStatus(state.taskSessionId, 'error');
                        break;
                    case 'aborted':
                        addAgentStep(stepsBox, 'agent-step-error', '中止', parsed.message || '任务已中止');
                        finishAgentRun(state, 'aborted');
                        updateAgentTaskStatus(state.taskSessionId, 'aborted');
                        break;
                    case 'max_turns':
                        addAgentStep(stepsBox, 'agent-step-error', '已达上限', parsed.message || '');
                        finishAgentRun(state, 'max_turns');
                        updateAgentTaskStatus(state.taskSessionId, 'max_turns');
                        break;
                    case 'token_usage': {
                        // PR-2：累加每轮 prompt/completion token，更新徽章
                        const pt = parsed.prompt_tokens || 0;
                        const ct = parsed.completion_tokens || 0;
                        currentAgentTaskTokens.last_prompt = pt;
                        currentAgentTaskTokens.last_completion = ct;
                        // 取本轮 prompt 为当前总用量近似（后端用累积 transcript 组装，已是当前总长）
                        currentAgentTaskTokens.prompt = pt;
                        currentAgentTaskTokens.completion = (currentAgentTaskTokens.completion || 0) + ct;
                        const total = pt + currentAgentTaskTokens.completion;
                        if (state.tokenBadge) {
                            const lvl = tokenLevel(pt, parsed.budget || TOKEN_BUDGET);
                            state.tokenBadge.className = 'agent-token-badge level-' + lvl;
                            state.tokenBadge.textContent = '📊 ' + pt + ' / ' + (parsed.budget || TOKEN_BUDGET);
                            state.tokenBadge.title = `本轮 prompt ${pt} tokens；累计 completion ${currentAgentTaskTokens.completion}；阈值 ${parsed.threshold || TOKEN_THRESHOLD}`;
                        }
                        break;
                    }
                    case 'compaction': {
                        // PR-2：transcript 触发压缩时显示提示步骤
                        window.__kiraraCompactionCount = (window.__kiraraCompactionCount || 0) + 1;
                        const msg = `上下文超阈值（约 ${parsed.before_tokens} tokens），已压缩早期 ${parsed.before_entries} → ${parsed.after_entries} 条记录（约 ${parsed.after_tokens} tokens）`;
                        addAgentStep(stepsBox, 'agent-step-compaction', '压缩', msg);
                        break;
                    }
                    default:
                        break;
                }
            }

            // 读取一条 Agent SSE 流，逐事件渲染；遇 approval_required 会递归续读 /approve 流
            async function readAgentStream(response, stepsBox, state) {
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop();
                    for (const line of lines) {
                        if (!line.startsWith('data: ')) continue;
                        const data = line.slice(6);
                        if (data === '[DONE]') continue;
                        let parsed = null;
                        try {
                            parsed = JSON.parse(data);
                        } catch (e) {
                            console.warn('Agent SSE 解析失败:', data);
                            continue;
                        }
                        await handleAgentEvent(parsed, stepsBox, state);
                    }
                }
            }

            // 审批卡片：显示工具/参数/风险/原因，按钮 允许一次 / 拒绝；点击后续读 /approve 流
            async function showApprovalCard(stepsBox, parsed, state) {
                const isDangerous = parsed.risk === 'dangerous';
                const card = document.createElement('div');
                card.className = 'agent-approval' + (isDangerous ? ' dangerous' : '');

                const head = document.createElement('div');
                head.className = 'agent-approval-head';
                head.textContent = isDangerous ? '⚠ 需要您确认（危险命令 · shell）' : '⚠ 需要您确认（写操作）';
                card.appendChild(head);

                const meta = document.createElement('div');
                meta.className = 'agent-approval-meta';
                const riskLabel = parsed.risk === 'dangerous' ? '危险' : '写';
                meta.textContent = `工具：${parsed.tool || '?'}　风险：${riskLabel}`;
                card.appendChild(meta);

                const params = document.createElement('div');
                params.className = 'agent-approval-params';
                params.textContent = JSON.stringify(parsed.input || {}, null, 2);
                card.appendChild(params);

                if (parsed.reason) {
                    const reason = document.createElement('div');
                    reason.className = 'agent-approval-reason';
                    reason.textContent = parsed.reason;
                    card.appendChild(reason);
                }

                const btnRow = document.createElement('div');
                btnRow.className = 'agent-approval-buttons';
                const allowBtn = document.createElement('button');
                allowBtn.className = 'agent-approval-btn allow';
                allowBtn.textContent = '允许一次';
                const rejectBtn = document.createElement('button');
                rejectBtn.className = 'agent-approval-btn reject';
                rejectBtn.textContent = '拒绝';
                btnRow.appendChild(allowBtn);
                btnRow.appendChild(rejectBtn);
                card.appendChild(btnRow);

                stepsBox.appendChild(card);
                outputArea.scrollTop = outputArea.scrollHeight;

                // 等到审批决定及其续读流全部完成（decide 内部 await readAgentStream）
                let decisionResolve;
                const donePromise = new Promise((r) => { decisionResolve = r; });
                let decided = false;

                // 挂起待审批期间被中止按钮 / Force Eject 作废：禁用按钮并解除 readAgentStream 等待
                const runEntry = state.runId ? window.__kiraraAgentRuns[state.runId] : null;
                if (runEntry) {
                    runEntry.onAbort = () => {
                        if (decided) return;
                        decided = true;
                        allowBtn.disabled = true;
                        rejectBtn.disabled = true;
                        head.textContent += '（已中止）';
                        addAgentStep(stepsBox, 'agent-step-error', '中止', '任务已中止，本次审批作废。');
                        decisionResolve();
                    };
                }

                const decide = async (decision) => {
                    if (decided || state.aborted) return;
                    decided = true;
                    if (runEntry) runEntry.onAbort = null;
                    allowBtn.disabled = true;
                    rejectBtn.disabled = true;
                    addAgentStep(stepsBox, 'agent-step-status', '审批',
                        decision === 'approve' ? '已允许，继续执行…' : '已拒绝，继续…');
                    try {
                        const resp = await fetch(KIRARA_API.AGENT_APPROVE, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ run_id: state.runId, decision: decision })
                        });
                        if (!resp.ok) {
                            const errData = await resp.json().catch(() => ({}));
                            addAgentStep(stepsBox, 'agent-step-error', '错误',
                                errData.error || `审批恢复失败: ${resp.status}`);
                        } else {
                            const ct = resp.headers.get('content-type') || '';
                            if (!ct.includes('text/event-stream')) {
                                const errData = await resp.json().catch(() => ({}));
                                addAgentStep(stepsBox, 'agent-step-error', '错误',
                                    errData.error || '审批服务未返回事件流');
                            } else {
                                await readAgentStream(resp, stepsBox, state);
                            }
                        }
                    } catch (e) {
                        console.error('Agent 审批恢复流错误:', e);
                        addAgentStep(stepsBox, 'agent-step-error', '错误', e.message || '审批恢复流异常');
                    } finally {
                        decisionResolve();
                    }
                };

                allowBtn.onclick = () => decide('approve');
                rejectBtn.onclick = () => decide('reject');

                await donePromise;
            }

            // Agent 发送链路：POST SSE，浏览器只渲染后端 ReAct 循环事件
            // taskSessionId 可选：传入则复用（"继续追问"），不传则按 task 新建 agent_<ts>
            async function callAgentRun(message, history, taskSessionId) {
                const abortController = new AbortController();
                currentAbortController = abortController;
                // 按 task 切分 session：每次 Agent 发送即一个独立 task，与 Chat 的 default session 隔离
                const sessionId = taskSessionId || ('agent_' + Date.now());
                // 初始化 task 元数据，供 handleAgentEvent 在终结事件时更新状态并落盘
                currentAgentTask = {
                    session_id: sessionId,
                    run_id: null,
                    message: (message || '').slice(0, 80),
                    created: Date.now(),
                    status: 'running'
                };
                saveAgentTask(currentAgentTask);
                // PR-2：重置当前 task 的 token 计数器
                currentAgentTaskTokens = { prompt: 0, completion: 0, last_prompt: 0, last_completion: 0 };
                window.__kiraraCompactionCount = 0;
                // Agent 过程卡片容器
                const aiMessage = document.createElement('div');
                aiMessage.className = 'message ai-message agent-run';

                const aiAvatar = document.createElement('img');
                aiAvatar.src = "/static/sprites/logos/kirara-4.png";
                aiAvatar.width = "48";
                aiAvatar.height = "48";
                aiAvatar.className = "avatar";

                const wrapper = document.createElement('div');
                wrapper.className = 'message-content-wrapper';

                // 任务头：标题 + token 计量徽章 + 进行中中止按钮（Phase 3 Force Eject 同源接线）
                const runHead = document.createElement('div');
                runHead.className = 'agent-run-head';
                const runTitle = document.createElement('span');
                runTitle.className = 'agent-run-title';
                runTitle.textContent = taskSessionId ? '🤖 Agent 任务（追问）' : '🤖 Agent 任务';
                // PR-2：实时 token 徽章
                const tokenBadge = document.createElement('span');
                tokenBadge.className = 'agent-token-badge level-ok';
                tokenBadge.title = `Token 用量（预算 ${TOKEN_BUDGET}，阈值 ${TOKEN_THRESHOLD}）`;
                tokenBadge.textContent = '📊 0 / ' + TOKEN_BUDGET;
                const abortBtn = document.createElement('button');
                abortBtn.type = 'button';
                abortBtn.className = 'agent-abort-btn';
                abortBtn.textContent = '■ 中止任务';
                abortBtn.title = '中止当前任务（正在执行的 shell 命令也会被终止）';
                abortBtn.onclick = function() {
                    if (!state.runId || this.disabled) return;
                    if (!window.confirm('确定中止当前 Agent 任务吗？绮罗罗会立即停止工具循环。')) return;
                    window.__kiraraAbortAgent(state.runId);
                };
                runHead.appendChild(runTitle);
                runHead.appendChild(tokenBadge);
                runHead.appendChild(abortBtn);

                const stepsBox = document.createElement('div');
                stepsBox.className = 'agent-steps';

                wrapper.appendChild(runHead);
                wrapper.appendChild(stepsBox);
                aiMessage.appendChild(aiAvatar);
                aiMessage.appendChild(wrapper);

                // workflow：移除思考气泡 → 插入 Agent 运行卡片
                hideThinkingBubble();
                outputArea.appendChild(aiMessage);
                outputArea.scrollTop = outputArea.scrollHeight;

                const state = {
                    finalText: '', runId: null, aborted: false, abortBtn: abortBtn,
                    tokenBadge: tokenBadge,
                    taskSessionId: sessionId   // 供 handleAgentEvent 终结时落盘 task 元数据
                };

                const response = await fetch(KIRARA_API.AGENT_RUN, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        message: message,
                        history: history || [],
                        persona: (typeof kiraraOptions !== 'undefined' && kiraraOptions.persona) || 'native',
                        think_mode: 'low',
                        session_id: sessionId   // 透传到后端 /api/kirara/agent/run（lmbrew.py 已在读）
                    }),
                    signal: abortController.signal
                });

                if (!response.ok) {
                    const errData = await response.json().catch(() => ({}));
                    throw new Error(errData.error || `Agent API请求失败: ${response.status}`);
                }

                const contentType = response.headers.get('content-type') || '';
                if (!contentType.includes('text/event-stream')) {
                    const errData = await response.json().catch(() => ({}));
                    throw new Error(errData.error || 'Agent 服务未返回事件流');
                }

                try {
                    await readAgentStream(response, stepsBox, state);
                } catch (streamError) {
                    if (streamError && streamError.name === 'AbortError') {
                        state.aborted = true;
                        finishAgentRun(state, 'aborted');
                        console.log('Agent 任务被用户主动中止');
                    } else {
                        console.error('Agent 流式读取错误:', streamError);
                        finishAgentRun(state, 'error');
                        throw streamError;
                    }
                } finally {
                    if (currentAbortController === abortController) {
                        currentAbortController = null;
                    }
                }
                // 兜底：流正常关闭但未收到任何终结事件（如挂起态被外部 abort 作废）
                if (window.__kiraraAgentRuns[state.runId]) {
                    finishAgentRun(state, state.aborted ? 'aborted' : 'error');
                }

                const finalText = state.finalText;
                // 最终答复按普通 AI 气泡渲染（保留 🔊 TTS / 复制按钮）
                if (finalText) {
                    conversationHistory.push({ role: 'assistant', content: finalText });
                    checkAndCompress();

                    const finalMessage = document.createElement('div');
                    finalMessage.className = 'message ai-message';

                    const finalAvatar = document.createElement('img');
                    finalAvatar.src = "/static/sprites/logos/kirara-4.png";
                    finalAvatar.width = "48";
                    finalAvatar.height = "48";
                    finalAvatar.className = "avatar";

                    const finalWrapper = document.createElement('div');
                    finalWrapper.className = 'message-content-wrapper';

                    const finalContent = document.createElement('div');
                    finalContent.className = 'message-content';
                    finalContent.innerHTML = renderMarkdown(finalText);

                    const finalTime = document.createElement('div');
                    finalTime.className = 'message-time';
                    finalTime.textContent = '刚刚';

                    const actionButtonsDiv = document.createElement('div');
                    actionButtonsDiv.className = 'action-buttons';

                    const speakButton = document.createElement('button');
                    speakButton.className = 'speak-button';
                    speakButton.innerHTML = '🔊';
                    speakButton.title = '朗读';
                    speakButton.onclick = function() { textToSpeech(finalText); };
                    actionButtonsDiv.appendChild(speakButton);

                    const copyMarkdownBtn = document.createElement('button');
                    copyMarkdownBtn.className = 'copy-button';
                    copyMarkdownBtn.innerHTML = '📝';
                    copyMarkdownBtn.title = '复制Markdown';
                    copyMarkdownBtn.onclick = function() {
                        copyToClipboard(finalText);
                        showCopyFeedback(copyMarkdownBtn);
                    };
                    actionButtonsDiv.appendChild(copyMarkdownBtn);

                    const copyTextBtn = document.createElement('button');
                    copyTextBtn.className = 'copy-button';
                    copyTextBtn.innerHTML = '📄';
                    copyTextBtn.title = '复制纯文本';
                    copyTextBtn.onclick = function() {
                        copyToClipboard(finalContent.innerText);
                        showCopyFeedback(copyTextBtn);
                    };
                    actionButtonsDiv.appendChild(copyTextBtn);

                    finalWrapper.appendChild(finalContent);
                    finalWrapper.appendChild(finalTime);
                    finalWrapper.appendChild(actionButtonsDiv);
                    finalMessage.appendChild(finalAvatar);
                    finalMessage.appendChild(finalWrapper);
                    outputArea.appendChild(finalMessage);
                    outputArea.scrollTop = outputArea.scrollHeight;
                }

                return finalText;
            }

            // 上下文压缩通知气泡
            const COMPRESSION_THRESHOLD = 40;
            const COMPRESSION_KEEP = 10;
            let lastCompressionPoint = 0;

            function addCompressionNotice(compressedCount, summary) {
                const noticeDiv = document.createElement('div');
                noticeDiv.className = 'message compression-notice';

                const bubble = document.createElement('div');
                bubble.className = 'compression-bubble';

                const icon = document.createElement('span');
                icon.className = 'compression-icon';
                icon.textContent = '🗜️';

                const textDiv = document.createElement('div');
                textDiv.className = 'compression-text';

                const title = document.createElement('div');
                title.className = 'compression-title';
                title.textContent = `上下文压缩 - ${compressedCount}条对话已压缩`;

                const summaryDiv = document.createElement('div');
                summaryDiv.className = 'compression-summary';
                summaryDiv.textContent = summary || '已将早期对话压缩为摘要，保持上下文连贯';

                textDiv.appendChild(title);
                textDiv.appendChild(summaryDiv);

                const meta = document.createElement('div');
                meta.className = 'compression-meta';
                meta.textContent = getCurrentTime();

                bubble.appendChild(icon);
                bubble.appendChild(textDiv);
                bubble.appendChild(meta);
                noticeDiv.appendChild(bubble);

                chatContainer.appendChild(noticeDiv);
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }

            function checkAndCompress() {
                const totalMessages = conversationHistory.length;
                const sinceLast = totalMessages - lastCompressionPoint;

                if (sinceLast >= COMPRESSION_THRESHOLD) {
                    const compressedCount = sinceLast;
                    const compressedMessages = conversationHistory.slice(lastCompressionPoint, totalMessages);

                    let summary = '';
                    const userMsgs = compressedMessages
                        .filter(m => m.role === 'user')
                        .map(m => m.content)
                        .join(' ');
                    if (userMsgs) {
                        const keywords = userMsgs
                            .replace(/[，。！？、\s]+/g, ' ')
                            .split(' ')
                            .filter(w => w.length >= 2)
                            .slice(0, 5);
                        summary = keywords.length > 0
                            ? `关键词: ${keywords.join('、')}`
                            : '';
                    }

                    addCompressionNotice(compressedCount, summary);

                    conversationHistory = conversationHistory.slice(-COMPRESSION_KEEP);
                    lastCompressionPoint = 0;

                    console.log(`[Compression] 压缩 ${compressedCount} 条对话，保留最近 ${COMPRESSION_KEEP} 条`);
                }
            }
            
            // 显示打字指示器
            function showTypingIndicator() {
                const typingDiv = document.createElement('div');
                typingDiv.className = 'typing-indicator';
                typingDiv.id = 'typing-indicator';
                
                for (let i = 0; i < 3; i++) {
                    const dot = document.createElement('div');
                    dot.className = 'typing-dot';
                    typingDiv.appendChild(dot);
                }
                
                chatContainer.appendChild(typingDiv);
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }
            
            // 显示加载指示器
            function showLoadingIndicator() {
                const loadingIndicator = document.getElementById('loading-indicator');
                const loadingText = document.getElementById('loading-text');
                if (loadingIndicator) {
                    loadingIndicator.style.display = 'flex';
                }
                if (loadingText) {
                    loadingText.textContent = '正在生成回复...';
                }
            }
            
            // 隐藏加载指示器
            function hideLoadingIndicator() {
                const loadingIndicator = document.getElementById('loading-indicator');
                if (loadingIndicator) {
                    loadingIndicator.style.display = 'none';
                }
            }
            
            // 隐藏打字指示器（保留兼容性）
            function hideTypingIndicator() {
                hideLoadingIndicator();
            }
            
            // 获取当前时间
            function getCurrentTime() {
                const now = new Date();
                return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            }
            
            // 处理AI回复
            function handleAIResponse(response) {
                hideLoadingIndicator();
                
                conversationHistory.push({ role: 'assistant', content: response });

                checkAndCompress();

                addMessage(response, 'ai');
                
                isGeneratingResponse = false;
                inputDisabled = false;
                userInput.disabled = false;
                if (submitBtn) submitBtn.disabled = false;
            }
            
            // 处理AI错误
            function handleAIError(errorMessage) {
                hideLoadingIndicator();
                
                addMessage(`抱歉，处理请求时出现错误: ${errorMessage}`, 'ai');
                
                isGeneratingResponse = false;
                inputDisabled = false;
                userInput.disabled = false;
                if (submitBtn) submitBtn.disabled = false;
            }
            
            // 调用AI API via WebSocket
            function callAIWebSocket(message) {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    // 发送消息到WebSocket服务
                    ws.send(JSON.stringify({
                        type: 'chat',
                        message: message
                    }));
                } else {
                    // WebSocket未连接，显示错误
                    handleAIError('WebSocket连接未建立，请刷新页面重试。');
                }
            }
            
            // 初始化WebSocket连接
            initWebSocket();
            
            // 调用AI API (保留兼容性，实际使用WebSocket)
            async function callAIApi(message) {
                // 实际使用WebSocket，这里保留函数定义以保持兼容性
                callAIWebSocket(message);
            }
            
            // 智能镜头功能函数
            async function openSmartLens() {
                try {
                    stream = await navigator.mediaDevices.getUserMedia({ video: true });
                    cameraFeed.srcObject = stream;
                    smartLensContainer.style.display = 'block';
                    recognitionResult.innerHTML = '<p class="result-placeholder">点击"截图识别"按钮开始图像识别</p>';
                    
                    cameraFeed.style.display = 'block';
                    captureImage.style.display = 'none';
                } catch (error) {
                    console.error('打开摄像头失败:', error);
                    alert('无法访问摄像头，请检查权限设置。');
                }
            }
            
            function closeSmartLens() {
                if (stream) {
                    stream.getTracks().forEach(track => track.stop());
                    stream = null;
                }
                cameraFeed.style.display = 'block';
                captureImage.style.display = 'none';
                captureImage.src = '';
                smartLensContainer.style.display = 'none';
                recognitionResult.innerHTML = '<p class="result-placeholder">点击"截图识别"按钮开始图像识别</p>';
            }
            
            async function captureAndRecognizeImage() {
                try {
                    const canvas = document.createElement('canvas');
                    canvas.width = cameraFeed.videoWidth;
                    canvas.height = cameraFeed.videoHeight;
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(cameraFeed, 0, 0, canvas.width, canvas.height);
                    
                    const imageDataUrl = canvas.toDataURL('image/jpeg');
                    
                    captureImage.src = imageDataUrl;
                    captureImage.style.display = 'block';
                    cameraFeed.style.display = 'none';
                    
                    recognitionResult.innerHTML = '<p>🔄 正在识别图像...</p>';
                    
                    const response = await fetch(KIRARA_API.RECOGNIZE_IMAGE, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ image: imageDataUrl })
                    });
                    
                    if (!response.ok) {
                        throw new Error(`识别请求失败: ${response.status}`);
                    }
                    
                    const data = await response.json();
                    
                    if (data.description) {
                        recognitionResult.innerHTML = `<p>✨ 识别结果: ${data.description}</p>`;
                        
                        addMessage(`图像识别结果: ${data.description}`, 'ai');
                    } else {
                        recognitionResult.innerHTML = '<p>❌ 识别失败，请重试。</p>';
                    }
                    
                } catch (error) {
                    console.error('截图或识别失败:', error);
                    recognitionResult.innerHTML = `<p>❌ 错误: ${error.message}</p>`;
                }
            }
        });
            // 换装系统 - 点击角色选项时更换立绘
            document.querySelectorAll('.character-option').forEach(option => {
                option.addEventListener('click', function() {
                    // 禁用动漫形象时锁定换装
                    if (document.body.classList.contains('anime-disabled')) return;
                    const imageUrl = this.getAttribute('data-image');
                    const characterName = this.querySelector('.character-info h3').textContent;
                    
                    if (imageUrl && kiraraImg) {
                        // 添加过渡效果
                        kiraraImg.style.opacity = '0';
                        kiraraImg.style.transition = 'opacity 0.3s ease';
                        
                        setTimeout(() => {
                            kiraraImg.src = imageUrl;
                            kiraraImg.style.opacity = '1';
                        }, 300);
                        
                        // 更新会话存储，保存当前服装
                        sessionStorage.setItem('currentOutfit', imageUrl);
                        sessionStorage.setItem('currentOutfitName', characterName);
                        
                        console.log('换装成功:', characterName, imageUrl);
                    }
                });
            });
            
            // 风格下拉菜单切换函数
            window.toggleStyleDropdown = function() {
                const options = document.getElementById('style-dropdown-options');
                const styleArrow = document.getElementById('style-arrow');
                if (options && styleArrow) {
                    options.style.display = options.style.display === 'block' ? 'none' : 'block';
                    if(options.style.display === 'block') {
                        styleArrow.textContent = "▲";
                    } else {
                        styleArrow.textContent = "▼";
                    }
                }
            };
            
            // 风格选项点击事件
            document.querySelectorAll('#style-dropdown-options .option').forEach(option => {
                option.addEventListener('click', function() {
                    document.getElementById('selected-style').textContent = this.textContent;
                    document.getElementById('style-dropdown-options').style.display = 'none';
                    document.getElementById('style-arrow').textContent = "▼";
                    // 更新本地和全局personalityType变量
                    personalityType = this.getAttribute("data-value");
                    window.personalityType = personalityType;
                    console.log('选中的风格:', personalityType);
                });
            });
           goLiveBtn.onclick = function(){
                if(isGoLive){
                    confirmStopGoLive = window.confirm("确定要停止Go Live模式吗？");
                    if(confirmStopGoLive){
                        isGoLive = false;
                        header.style.visibility = "visible";
                        goLiveBtn.style.visibility = "visible";
                        goLiveBtn.textContent = "👁️‍🗨️Go Live(Beta)";
                        goLiveBtn.title = "使用自身视觉组件观察用户界面，与用户实时协作。注意！它可能会暴露用户电脑界面";
                        goLiveContainer.style.visibility = "hidden";
                        fetch('http://localhost:5001/api/go-live/stop', {
                            method: 'POST'
                        })
                        .then(response => response.json())
                        .then(data => {
                            console.log('Go Live stopped:', data);
                        })
                        .catch(error => {
                            console.error('Error stopping Go Live:', error);
                        });
                    }
                    
                }else{
                    confirmStartGoLive = window.confirm("确定要开始Go Live模式吗？注意！它可能会暴露用户电脑界面。如果点击“是”，则代表用户已授权把您的界面分享给我们。");
                    if(confirmStartGoLive){
                        isGoLive = true;
                        header.style.visibility = "hidden";
                        goLiveBtn.style.visibility = "visible";
                        goLiveBtn.textContent = "❌Stop Live";
                        goLiveBtn.title = "停止Go Live模式。";
                        goLiveContainer.style.visibility = "visible";
                        fetch('http://localhost:5001/api/go-live/start', {
                             
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify({ user_goal: userGoal })
                        })
                        .then(response => response.json())
                        .then(data => {
                            console.log('Go Live started:', data);
                        })
                        .catch(error => {
                            console.error('Error starting Go Live:', error);
                        });
                    }
                    
                }
           }

           // FORCE EJECT 按钮事件处理
           forceEjectBtn.onclick = function(){
                // Phase 3：Agent 模式下 Eject = 中止进行中（含挂起待审批）的 Agent 任务（同源 5000）
                var inAgentMode = (typeof window.__kiraraIsAgentMode === 'function') && window.__kiraraIsAgentMode();
                if (inAgentMode) {
                    var activeRunIds = (typeof window.__kiraraActiveAgentRunIds === 'function')
                        ? window.__kiraraActiveAgentRunIds() : [];
                    if (!activeRunIds.length) {
                        window.alert('当前没有进行中的 Agent 任务哦~');
                        return;
                    }
                    var confirmAbort = window.confirm(
                        "⚠️ 中止 Agent 任务\n\n绮罗罗会立即停止工具循环；正在执行的 shell 命令会被强制终止，"
                        + "等待审批的操作将作废。\n\n确定中止吗？"
                    );
                    if (confirmAbort) {
                        activeRunIds.forEach(function(rid) {
                            if (typeof window.__kiraraAbortAgent === 'function') {
                                window.__kiraraAbortAgent(rid);
                            }
                        });
                    }
                    return;
                }
                // Chat 模式维持原语义（5001 辅助后端，本期不改动）
                var confirmEject = window.confirm("⚠️ 警告：强制弹出模型\n\n这将禁用所有AI功能，切换到模拟模式。没有保存的对话会被清除。\n\n确定要继续吗？");
                if(confirmEject){
                    fetch('http://localhost:5001/api/kirara/force-eject', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        }
                    })
                    .then(response => response.json())
                    .then(data => {
                        if(data.success){
                            alert('✅ 已成功强制弹出模型！\n\n现在Kirara将运行在模拟模式下。');
                            console.log('Force Eject successful:', data);
                            // 可以在这里添加UI变化，比如按钮状态改变
                            forceEjectBtn.style.backgroundColor = '#4a5568';
                            forceEjectBtn.title = 'AI已禁用（模拟模式）';
                        } else {
                            alert('❌ 强制弹出失败: ' + data.message);
                        }
                    })
                    .catch(error => {
                        console.error('Error during Force Eject:', error);
                        alert('❌ 强制弹出失败: ' + error.message);
                    });
                }
           }

// ==================== 上下文管理功能 ====================

// 上下文标签切换功能
function initContextTabs() {
    const contextTabs = document.querySelectorAll('.context-tab');
    const tabPanels = document.querySelectorAll('.tab-panel');

    contextTabs.forEach(tab => {
        tab.addEventListener('click', function() {
            const targetTab = this.dataset.tab;

            // 移除所有标签的active状态
            contextTabs.forEach(t => t.classList.remove('active'));
            // 隐藏所有面板
            tabPanels.forEach(p => p.classList.remove('active'));

            // 添加当前标签的active状态
            this.classList.add('active');
            // 显示对应面板
            const targetPanel = document.getElementById(`${targetTab}-panel`);
            if (targetPanel) {
                targetPanel.classList.add('active');
            }

            // 短期记忆标签：切换时自动刷新一次
            if (targetTab === 'session' && typeof renderSessionHistory === 'function') {
                renderSessionHistory();
            }
        });
    });
}

// 读取本地记忆文件
async function loadMemories() {
    const memoriesList = document.getElementById('memories-list');
    if (!memoriesList) return;

    try {
        const response = await fetch('/apps/kirara/memories/mem.txt');
        if (!response.ok) {
            throw new Error(`加载记忆文件失败: ${response.status}`);
        }

        const content = await response.text();
        let memories = [];
        try {
            memories = JSON.parse(content);
        } catch {
            memories = content.split('\n').filter(line => line.trim());
        }

        memoriesList.innerHTML = '';

        memories.forEach((memory, index) => {
            const memoryText = typeof memory === 'string' ? memory : memory;
            const memoryItem = document.createElement('div');
            memoryItem.className = 'memory-item';
            memoryItem.innerHTML = `<span class="memory-index">${index + 1}</span><span class="memory-text">${memoryText}</span>`;
            memoriesList.appendChild(memoryItem);
        });

        console.log('记忆文件加载成功');
    } catch (error) {
        console.error('加载记忆文件失败:', error);
        memoriesList.innerHTML = `<div class="loading-text">❌ 加载记忆失败: ${error.message}</div>`;
    }
}

// 读取系统提示文件
async function loadSystemPrompt() {
    const systemPromptContent = document.getElementById('system-prompt-content');
    if (!systemPromptContent) return;
    
    try {
        const response = await fetch('/apps/kirara/memories/sysPrompt.txt');
        if (!response.ok) {
            throw new Error(`加载系统提示文件失败: ${response.status}`);
        }
        
        const content = await response.text();
        systemPromptContent.textContent = content;
        console.log('系统提示文件加载成功');
    } catch (error) {
        console.error('加载系统提示文件失败:', error);
        systemPromptContent.textContent = `❌ 加载失败: ${error.message}`;
    }
}

// 读取模型配置文件
async function loadModelConfig() {
    const modelConfigContent = document.getElementById('model-config-content');
    if (!modelConfigContent) return;
    
    try {
        const response = await fetch('/apps/kirara/modelfile.txt');
        if (!response.ok) {
            throw new Error(`加载模型配置文件失败: ${response.status}`);
        }
        
        const content = await response.text();
        modelConfigContent.textContent = content;
        console.log('模型配置文件加载成功');
    } catch (error) {
        console.error('加载模型配置文件失败:', error);
        modelConfigContent.textContent = `❌ 加载失败: ${error.message}`;
    }
}

// 读取设置界面中的模型配置文件
async function loadModelFileDisplay() {
    const modelfileContent = document.getElementById('modelfile-content');
    if (!modelfileContent) return;
    
    try {
        const response = await fetch('/apps/kirara/modelfile.txt');
        if (!response.ok) {
            throw new Error(`加载modelfile失败: ${response.status}`);
        }
        
        const content = await response.text();
        modelfileContent.textContent = content;
        console.log('modelfile.txt 加载成功');
    } catch (error) {
        console.error('加载modelfile失败:', error);
        modelfileContent.textContent = `❌ 加载失败: ${error.message}`;
    }
}

// 绑定刷新按钮事件
function bindRefreshButtons() {
    // 记忆库刷新按钮
    const refreshMemoriesBtn = document.getElementById('refresh-memories');
    if (refreshMemoriesBtn) {
        refreshMemoriesBtn.addEventListener('click', loadMemories);
    }
    
    // 系统提示刷新按钮
    const refreshSystemPromptBtn = document.getElementById('refresh-system-prompt');
    if (refreshSystemPromptBtn) {
        refreshSystemPromptBtn.addEventListener('click', loadSystemPrompt);
    }
    
    // 模型配置刷新按钮
    const refreshModelConfigBtn = document.getElementById('refresh-model-config');
    if (refreshModelConfigBtn) {
        refreshModelConfigBtn.addEventListener('click', loadModelConfig);
    }
    
    // 设置界面的modelfile刷新按钮
    const refreshModelfileBtn = document.getElementById('refresh-modelfile');
    if (refreshModelfileBtn) {
        refreshModelfileBtn.addEventListener('click', loadModelFileDisplay);
    }
}

// 初始化上下文管理功能
function initContextManagement() {
    initContextTabs();
    bindRefreshButtons();
    
    // 当上下文面板激活时自动加载数据
    const performanceBtn = document.getElementById('performanceBtn');
    const optionsBtn = document.getElementById('optionsBtn');
    
    let hasLoadedContext = false;
    let hasLoadedModelfile = false;
    let hasLoadedOptions = false;
    
    performanceBtn.addEventListener('click', function() {
        if (!hasLoadedContext) {
            loadMemories();
            loadSystemPrompt();
            loadModelConfig();
            hasLoadedContext = true;
        }
    });
    
    optionsBtn.addEventListener('click', function() {
        if (!hasLoadedModelfile) {
            loadModelFileDisplay();
            hasLoadedModelfile = true;
        }
        if (!hasLoadedOptions) {
            loadOptions();
            bindOptionsEvents();
            hasLoadedOptions = true;
        }
    });
}

// 页面加载完成后初始化上下文管理功能
document.addEventListener('DOMContentLoaded', async function() {
    initContextManagement();
    initDisableAnime();
    // P3.6 — MOD 注册表先于人设/音色加载：MOD 扩展人设合并到 personMap
    try { await ModRegistry.init(); } catch (e) {}
    try { await loadPersonaOptions(); } catch (e) {}
    try { await loadVoiceOptions(); } catch (e) {}
});

// ==================== 设置管理功能 ====================

let kiraraOptions = {
    max_context: 1024000,
    online: false,
    hippo: true,
    cloud_acceleration: true,
    think_mode: 'low',
    persona: 'native',        // JRVS-7B SFT 人设：native / jrvs / kirara
    voice: 'preset:kirara',   // TTS 音色：preset:jrvs / preset:lady / preset:kirara / voice:<系统语音id>
    disable_anime: false,     // 禁用动漫形象：舞台强制展示 Logo 并锁定立绘换装
    ui_mode: 'chat',          // Chat/Agent 切换开关：'chat' | 'agent'
    agent_shell_enabled: false, // Agent shell 工具开关（危险级，默认关，开启后仍逐次审批）
    agent_shell_timeout: 10,    // 单条 shell 命令超时秒数
    muted: false,              // 静音开关：开启后停止当前 TTS 并阻止后续播报
    skills: []                 // 用户自定义技能列表：{id,name,description,content,enabled,created_at}
};

// 人设元数据（与后端 PERSONA_PROMPTS 对应；API 不可用时作为兜底）
let personaMetaMap = {
    native: { label: '模型原生', hint: '不注入 system prompt，使用模型原生人格（兼容当前 sysPrompt.txt）。' },
    jrvs: { label: '贾维斯', hint: 'system=JRVS：称呼「先生」，专业、简洁、无颜文字。' },
    kirara: { label: '绮罗', hint: 'system=Kirara：称呼「主人sama」，活泼甜美、颜文字、女仆风。' }
};

// ==================== P3.6/P3.8 — SimChat MOD 注册表（断类型 B）====================
// 启动时 fetch /api/simchat/mods，过滤 type==='agent-config' 的 MOD，
// 逐个读取其 config（persona/system_prompt_file/theme）合并到前端状态。
// MOD 缺失、端点不可用、或 MOD 加载失败（status!=='loaded'）时静默降级，裸壳语义保持全功能。
const ModRegistry = {
    mods: [],           // 已加载的 agent-config 类型 MOD（来自 lifecycle.list_mods()）
    personaExtensions: {},  // MOD 扩展人设 key → {label, hint, system_prompt, source}
    failedMods: [],     // type===agent-config 但 status!=='loaded' 的 MOD（UI 占位用）
    initError: null,    // fetch /api/simchat/mods 本身是否失败（裸壳不算）
    initialized: false,

    async init() {
        try {
            const resp = await fetch(KIRARA_API.SIMCHAT_MODS);
            if (!resp.ok) {
                // 裸壳：端点不存在 → 正常，不是失败
                this.initialized = true; return;
            }
            const data = await resp.json();
            if (!data.success || !Array.isArray(data.mods)) {
                this.initError = data.error || 'mods 端点返回异常';
                this.initialized = true; return;
            }

            // 分别收集：成功加载的 vs 失败的 agent-config MOD
            for (const m of data.mods) {
                if (m.type !== 'agent-config') continue;
                if (m.status === 'loaded') {
                    try { await this._loadMod(m); }
                    catch (e) { console.warn(`[ModRegistry] 加载 MOD ${m.id} 失败:`, e); }
                } else {
                    this.failedMods.push({ id: m.id, status: m.status, error: m.error });
                }
            }
        } catch (e) {
            // fetch 本身抛错（网络/DNS） → 记为 initError
            this.initError = String(e);
        }
        this.initialized = true;
    },

    async _loadMod(mod) {
        const modId = mod.id;
        const cfg = mod.config;
        if (!cfg || typeof cfg !== 'object') return;

        // 1. 人设：config.persona + config.system_prompt_file
        if (cfg.persona) {
            let systemPrompt = '';
            if (cfg.system_prompt_file) {
                const promptResp = await fetch(
                    `${KIRARA_API.SIMCHAT_MODS}/${encodeURIComponent(modId)}/${cfg.system_prompt_file}`
                );
                if (promptResp.ok) systemPrompt = await promptResp.text();
            }
            this.personaExtensions[cfg.persona] = {
                label: `MOD · ${mod.name || modId}`,
                hint: mod.description || `agent-config 扩展人设（${mod.version || '?'}）`,
                system_prompt: systemPrompt,
                source: modId,
            };
        }

        // 2. 主题 CSS：注入 <link>（幂等，按 modId 命名 id）
        if (cfg.theme) {
            const linkId = `mod-theme-${modId}`;
            if (!document.getElementById(linkId)) {
                const link = document.createElement('link');
                link.id = linkId;
                link.rel = 'stylesheet';
                link.href = `${KIRARA_API.SIMCHAT_MODS}/${encodeURIComponent(modId)}/${cfg.theme}`;
                document.head.appendChild(link);
                // body 加主题类（让 CSS 选择器可作用域化）
                document.body.classList.add(`${modId}-theme`);
            }
        }

        this.mods.push(mod);
    },

    // 供 loadPersonaOptions() 合并调用
    getPersonaKeys() { return Object.keys(this.personaExtensions); },
    getPersona(key) { return this.personaExtensions[key] || null; },
};

// P3 closure — MOD 加载失败时注入可关闭的非阻塞警告条
function _maybeInjectModWarning() {
    if (!ModRegistry.initError && ModRegistry.failedMods.length === 0) return;
    if (document.getElementById('mod-load-warning')) return;  // 已注入则跳过

    const grid = document.getElementById('persona-cards');
    if (!grid) return;

    const details = ModRegistry.failedMods
        .map(m => `${m.id} (${m.status}${m.error ? ': ' + m.error : ''})`)
        .join('；');

    const box = document.createElement('div');
    box.id = 'mod-load-warning';
    box.style.cssText = 'margin-bottom:12px;padding:8px 12px;background:#fff3cd;border:1px solid #ffe08a;border-radius:8px;color:#856404;font-size:13px;display:flex;gap:8px;align-items:center;';
    box.innerHTML = `
        <span>⚠️ agent-config MOD 扩展加载失败${details ? '：' + details : ''}。已使用内置人设/主题。</span>
        <button type="button" style="margin-left:auto;background:none;border:none;cursor:pointer;font-size:16px;color:#856404;" aria-label="关闭">×</button>
    `;
    box.querySelector('button').addEventListener('click', () => box.remove());
    grid.parentNode.insertBefore(box, grid);
}

// 音声相关状态
let voiceOptionsLoaded = false;
let voicePresetSamples = {};
let ttsAvailable = true;
let currentTTSAudio = null;

// ==================== 禁用动漫形象（Logo 模式）====================
const DISABLED_ANIME_LOGO = '/static/sprites/logos/kirara-3.png';
const DEFAULT_OUTFIT = '/apps/kirara/sprites/characters/kirara/common/kirara-casual1-default.svg';
let disableAnimeBound = false;
let lastOutfitBeforeDisable = null;

function readCookieValue(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return decodeURIComponent(parts.pop().split(';').shift());
    return null;
}

// 当前用户选择的立绘（cookie 存档 → 会话存储 → 默认）
function getPreferredOutfit() {
    return readCookieValue('kirara_character')
        || sessionStorage.getItem('currentOutfit')
        || DEFAULT_OUTFIT;
}

function stageImgIsLogo() {
    const src = kiraraImg ? (kiraraImg.getAttribute('src') || '') : '';
    return src.endsWith('/static/sprites/logos/kirara-3.png');
}

function swapStageImage(nextSrc) {
    if (!kiraraImg || kiraraImg.getAttribute('src') === nextSrc) return;
    kiraraImg.style.transition = 'opacity 0.3s ease';
    kiraraImg.style.opacity = '0';
    setTimeout(() => {
        kiraraImg.src = nextSrc;
        kiraraImg.style.opacity = '1';
    }, 300);
}

// 切换禁用动漫形象状态：蒙版 / 锁定换装 / 强制 Logo + 蓝色发光边缘（纯 CSS）
function applyDisableAnime(disabled) {
    disabled = !!disabled;
    document.body.classList.toggle('anime-disabled', disabled);

    const switchEl = document.getElementById('disable-anime-switch');
    if (switchEl) switchEl.checked = disabled;

    if (!kiraraImg) return;

    if (disabled) {
        if (!stageImgIsLogo()) {
            lastOutfitBeforeDisable = kiraraImg.getAttribute('src');
            swapStageImage(DISABLED_ANIME_LOGO);
        }
    } else {
        if (stageImgIsLogo()) {
            swapStageImage(lastOutfitBeforeDisable || getPreferredOutfit());
        }
        lastOutfitBeforeDisable = null;
    }
}

function bindDisableAnimeSwitch() {
    if (disableAnimeBound) return;
    const switchEl = document.getElementById('disable-anime-switch');
    if (!switchEl) return;
    disableAnimeBound = true;
    switchEl.addEventListener('change', function() {
        kiraraOptions.disable_anime = this.checked;
        applyDisableAnime(this.checked);
        saveOptions();
    });
}

// 舞台始终需要该状态，页面加载即拉取（不等选项面板首次打开）
async function initDisableAnime() {
    bindDisableAnimeSwitch();
    try {
        const response = await fetch(KIRARA_API.OPTIONS);
        if (!response.ok) throw new Error(`加载配置失败: ${response.status}`);
        const data = await response.json();
        if (data.success && data.options) {
            kiraraOptions = data.options;
            applyDisableAnime(!!kiraraOptions.disable_anime);
            // 同步写 localStorage，启动时从这里回读避免 fetch 竞态
            try {
                if (kiraraOptions.ui_mode) {
                    localStorage.setItem('kirara_ui_mode', kiraraOptions.ui_mode);
                }
            } catch (e) { /* 无痕模式兜底 */ }
            // Chat/Agent 模式开关回读（页面加载即同步，不弹气泡）
            if (typeof window.applyKiraraUiMode === 'function') {
                window.applyKiraraUiMode(kiraraOptions.ui_mode === 'agent', { silent: true });
            }
            // 同步静音按钮状态
            if (typeof syncMuteButtonUI === 'function') {
                syncMuteButtonUI();
            }
        }
    } catch (error) {
        console.error('加载动漫形象设置失败:', error);
    }
}

async function loadOptions() {
    try {
        const response = await fetch(KIRARA_API.OPTIONS);
        if (!response.ok) {
            throw new Error(`加载配置失败: ${response.status}`);
        }
        
        const data = await response.json();
        if (data.success && data.options) {
            kiraraOptions = data.options;
            if (kiraraOptions.think_mode) {
                thinkMode = kiraraOptions.think_mode;
                window.thinkMode = thinkMode;
                if (window.updateModeButton) {
                    window.updateModeButton();
                }
            }
            updateOptionsUI();
            if (typeof syncMuteButtonUI === 'function') {
                syncMuteButtonUI();
            }
            console.log('配置加载成功:', kiraraOptions);
        }
    } catch (error) {
        console.error('加载配置失败:', error);
    }
}

async function saveOptions() {
    try {
        const response = await fetch(KIRARA_API.OPTIONS, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ options: kiraraOptions })
        });
        
        if (!response.ok) {
            throw new Error(`保存配置失败: ${response.status}`);
        }
        
        const data = await response.json();
        if (data.success) {
            console.log('配置保存成功');
            // 同步写 localStorage 作为启动时的同步回读缓存（避免 fetch 竞态）
            try {
                if (data.options && data.options.ui_mode) {
                    localStorage.setItem('kirara_ui_mode', data.options.ui_mode);
                }
            } catch (e) { /* 无痕模式等环境兜底 */ }
            return true;
        }
    } catch (error) {
        console.error('保存配置失败:', error);
    }
    return false;
}

function updateOptionsUI() {
    const maxContextInput = document.getElementById('max-context-input');
    const maxContextValue = document.getElementById('max-context-value');
    const onlineSwitch = document.getElementById('online-switch');
    const hippoSwitch = document.getElementById('hippo-switch');
    const cloudAccelSwitch = document.getElementById('cloud-accel-switch');
    const disableAnimeSwitch = document.getElementById('disable-anime-switch');
    
    const contextValue = kiraraOptions.max_context || 1024000;
    if (maxContextInput) {
        maxContextInput.value = contextValue;
    }
    if (maxContextValue) {
        maxContextValue.textContent = contextValue.toLocaleString();
    }
    if (onlineSwitch) {
        onlineSwitch.checked = kiraraOptions.online || false;
    }
    if (hippoSwitch) {
        hippoSwitch.checked = kiraraOptions.hippo || false;
    }
    if (cloudAccelSwitch) {
        cloudAccelSwitch.checked = kiraraOptions.cloud_acceleration || false;
    }
    if (disableAnimeSwitch) {
        disableAnimeSwitch.checked = !!kiraraOptions.disable_anime;
    }
    applyDisableAnime(!!kiraraOptions.disable_anime);

    // Agent shell 工具开关
    const agentShellSwitch = document.getElementById('agent-shell-switch');
    if (agentShellSwitch) {
        agentShellSwitch.checked = !!kiraraOptions.agent_shell_enabled;
    }

    // 人设卡片选中态
    const personaKey = kiraraOptions.persona || 'native';
    document.querySelectorAll('.persona-card').forEach(card => {
        card.classList.toggle('selected', card.dataset.persona === personaKey);
    });
    const personaHint = document.getElementById('persona-hint');
    if (personaHint && personaMetaMap[personaKey]) {
        personaHint.textContent = personaMetaMap[personaKey].hint;
    }

    // 音色下拉选中值（选项可能尚未从后端加载完成，loadVoiceOptions 内会再同步一次）
    const voiceSelect = document.getElementById('voice-select');
    if (voiceSelect && kiraraOptions.voice) {
        voiceSelect.value = kiraraOptions.voice;
    }
    updateVoiceHint();
}

// 更新音色下方的提示文字 / 试听按钮可用性
function updateVoiceHint() {
    const voiceHint = document.getElementById('voice-hint');
    const previewBtn = document.getElementById('voice-preview-btn');
    if (!ttsAvailable) {
        if (voiceHint) voiceHint.textContent = '⚠️ 服务器 TTS 引擎不可用（未安装 pyttsx3），仅可保存偏好。';
        if (previewBtn) previewBtn.disabled = true;
        return;
    }
    if (previewBtn) previewBtn.disabled = false;
    const voiceSelect = document.getElementById('voice-select');
    if (voiceHint && voiceSelect && voiceSelect.selectedOptions.length) {
        const label = voiceSelect.selectedOptions[0].textContent.trim();
        voiceHint.textContent = `当前音声：${label}。AI 语音播报与对话朗读均使用该音色。`;
    }
}

// 从后端加载人设枚举（失败时使用静态兜底）
async function loadPersonaOptions() {
    try {
        const response = await fetch(KIRARA_API.PERSONAS);
        if (!response.ok) throw new Error(`加载人设失败: ${response.status}`);
        const data = await response.json();
        if (!data.success || !Array.isArray(data.personas)) return;

        data.personas.forEach(p => {
            personaMetaMap[p.key] = { label: p.label, hint: p.description };
            _updatePersonaCard(p.key, p);
        });

        // P3.6 — 合并 MOD 扩展人设（ModRegistry.init() 已在启动阶段完成）
        if (ModRegistry.initialized) {
            ModRegistry.getPersonaKeys().forEach(key => {
                if (!(key in personaMetaMap)) {
                    const ext = ModRegistry.getPersona(key);
                    personaMetaMap[key] = { label: ext.label, hint: ext.hint, source: ext.source };
                    // MOD 人设没有硬编码的 HTML 卡片，动态创建一个
                    _createPersonaCard(key, ext);
                }
            });
            // P3 closure — 有 agent-config MOD 加载失败时显示非阻塞警告条
            _maybeInjectModWarning();
        }

        const personaKey = kiraraOptions.persona || data.default_persona || 'native';
        const personaHint = document.getElementById('persona-hint');
        if (personaHint && personaMetaMap[personaKey]) {
            personaHint.textContent = personaMetaMap[personaKey].hint;
        }
    } catch (error) {
        console.warn('加载人设列表失败，使用内置选项:', error);
    }
}

// 更新已存在的人设卡片 DOM（icon/name/title）
function _updatePersonaCard(key, p) {
    const card = document.querySelector(`.persona-card[data-persona="${key}"]`);
    if (!card) return;
    const icon = card.querySelector('.persona-card-icon');
    const name = card.querySelector('.persona-card-name');
    if (icon && p.icon) icon.textContent = p.icon;
    if (name && p.label) name.textContent = p.label;
    card.title = p.description || '';
}

// P3.6 — 为 MOD 人设动态创建卡片（HTML 里硬编码的只有 native/jrvs/kirara）
function _createPersonaCard(key, ext) {
    const grid = document.getElementById('persona-cards');
    if (!grid) return;
    const card = document.createElement('div');
    card.className = 'persona-card';
    card.dataset.persona = key;
    card.dataset.fromMod = ext.source || '';
    card.innerHTML = `
        <span class="persona-card-icon">🎭</span>
        <div class="persona-card-text">
            <span class="persona-card-name">${ext.label}</span>
            <span class="persona-card-sub">MOD · ${ext.source || '扩展人设'}</span>
        </div>
    `;
    card.title = `[MOD] ${ext.hint || ''}（来自 ${ext.source || 'unknown'}）`;
    grid.appendChild(card);
    // 事件由已有的 document.querySelectorAll('.persona-card') 统一绑定
}

// 从后端加载预设音色与本机系统语音，动态渲染下拉框
async function loadVoiceOptions() {
    if (voiceOptionsLoaded) return;
    const voiceSelect = document.getElementById('voice-select');
    if (!voiceSelect) return;

    try {
        const response = await fetch(KIRARA_API.TTS_VOICES);
        if (!response.ok) throw new Error(`加载音色失败: ${response.status}`);
        const data = await response.json();
        if (!data.success) throw new Error(data.error || '音色枚举失败');

        ttsAvailable = !!data.tts_available;
        voicePresetSamples = {};
        voiceSelect.innerHTML = '';

        const presetGroup = document.createElement('optgroup');
        presetGroup.label = '预设音色';
        (data.presets || []).forEach(p => {
            const option = document.createElement('option');
            option.value = `preset:${p.key}`;
            option.textContent = `${p.icon || ''} ${p.label}（${p.description || ''}）`;
            presetGroup.appendChild(option);
            voicePresetSamples[`preset:${p.key}`] = p.sample_text;
        });
        voiceSelect.appendChild(presetGroup);

        const systemVoices = data.voices || [];
        if (systemVoices.length > 0) {
            const sysGroup = document.createElement('optgroup');
            sysGroup.label = '本机系统语音';
            systemVoices.forEach(v => {
                const option = document.createElement('option');
                option.value = `voice:${v.id}`;
                const tags = [];
                if (v.chinese) tags.push('中文');
                if (v.gender === 'female') tags.push('女');
                if (v.gender === 'male') tags.push('男');
                option.textContent = `🗣 ${v.name}${tags.length ? ' · ' + tags.join('/') : ''}`;
                sysGroup.appendChild(option);
            });
            voiceSelect.appendChild(sysGroup);
        }

        voiceOptionsLoaded = true;
    } catch (error) {
        console.warn('加载音色列表失败，使用内置兜底选项:', error);
        ttsAvailable = false;
    }

    const savedVoice = kiraraOptions.voice || 'preset:kirara';
    if ([...voiceSelect.options].some(o => o.value === savedVoice)) {
        voiceSelect.value = savedVoice;
    }
    updateVoiceHint();
}

// 调用后端 TTS 并在浏览器播放（新请求会打断上一条播报）
async function playKiraraTTS(text, voiceSelector) {
    if (!text || !text.trim()) return false;
    // 静音状态：阻止后续播报
    if (kiraraOptions && kiraraOptions.muted) {
        console.log('[TTS] 已静音，跳过播报');
        return false;
    }
    try {
        const response = await fetch(KIRARA_API.TTS, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text: text,
                voice: voiceSelector || kiraraOptions.voice || 'preset:kirara'
            })
        });
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `TTS API请求失败: ${response.status}`);
        }
        const data = await response.json();
        if (data.success && data.audio) {
            if (currentTTSAudio) {
                currentTTSAudio.pause();
                currentTTSAudio = null;
            }
            const audio = new Audio(data.audio);
            currentTTSAudio = audio;
            audio.onended = () => { if (currentTTSAudio === audio) currentTTSAudio = null; };
            audio.onerror = () => { if (currentTTSAudio === audio) currentTTSAudio = null; };
            await audio.play();
            return true;
        }
    } catch (error) {
        console.error('TTS API调用错误:', error);
    }
    return false;
}
window.kiraraTTSPlay = playKiraraTTS;

// 切换静音：静音时立即停止当前 TTS 播报，并阻止后续播报
function toggleMute() {
    const muteBtn = document.getElementById('mute-btn');
    const nowMuted = !(kiraraOptions && kiraraOptions.muted);
    kiraraOptions.muted = nowMuted;

    if (nowMuted) {
        // 立即停止正在播放的 TTS
        if (currentTTSAudio) {
            currentTTSAudio.pause();
            currentTTSAudio.currentTime = 0;
            currentTTSAudio = null;
        }
        if (muteBtn) {
            muteBtn.querySelector('.nav-icon').textContent = '🔇';
            muteBtn.title = '取消静音';
            muteBtn.classList.add('muted');
        }
        showToast('已静音', 'info');
    } else {
        if (muteBtn) {
            muteBtn.querySelector('.nav-icon').textContent = '🔊';
            muteBtn.title = '静音';
            muteBtn.classList.remove('muted');
        }
        showToast('已取消静音', 'info');
    }

    // 持久化静音设置
    if (typeof saveOptions === 'function') {
        saveOptions();
    }
}
window.kiraraToggleMute = toggleMute;

// 同步静音按钮的图标状态（页面加载/配置加载后调用）
function syncMuteButtonUI() {
    const muteBtn = document.getElementById('mute-btn');
    if (!muteBtn) return;
    const muted = !!(kiraraOptions && kiraraOptions.muted);
    const icon = muteBtn.querySelector('.nav-icon');
    if (icon) {
        icon.textContent = muted ? '🔇' : '🔊';
    }
    muteBtn.title = muted ? '取消静音' : '静音';
    muteBtn.classList.toggle('muted', muted);
}
window.kiraraSyncMuteUI = syncMuteButtonUI;

function bindOptionsEvents() {
    const maxContextInput = document.getElementById('max-context-input');
    const maxContextValue = document.getElementById('max-context-value');
    const onlineSwitch = document.getElementById('online-switch');
    const hippoSwitch = document.getElementById('hippo-switch');
    const cloudAccelSwitch = document.getElementById('cloud-accel-switch');
    
    if (maxContextInput) {
        maxContextInput.addEventListener('input', function() {
            const value = parseInt(this.value) || 1024000;
            kiraraOptions.max_context = value;
            if (maxContextValue) {
                maxContextValue.textContent = value.toLocaleString();
            }
            saveOptions();
        });
    }
    
    if (onlineSwitch) {
        onlineSwitch.addEventListener('change', function() {
            kiraraOptions.online = this.checked;
            saveOptions();
        });
    }
    
    if (hippoSwitch) {
        hippoSwitch.addEventListener('change', function() {
            kiraraOptions.hippo = this.checked;
            saveOptions();
        });
    }
    
    if (cloudAccelSwitch) {
        cloudAccelSwitch.addEventListener('change', function() {
            kiraraOptions.cloud_acceleration = this.checked;
            saveOptions();
        });
    }

    // 禁用动漫形象开关（initDisableAnime 可能已先行绑定，内部有幂等保护）
    bindDisableAnimeSwitch();

    // Agent shell 工具开关（危险能力：开启前二次确认）
    const agentShellSwitch = document.getElementById('agent-shell-switch');
    if (agentShellSwitch) {
        agentShellSwitch.addEventListener('change', function() {
            if (this.checked) {
                const ok = window.confirm(
                    '⚠️ 开启 shell 工具？\n\n'
                    + '开启后，Agent 模式下的绮罗罗可以在本机执行命令。\n'
                    + '保护措施：每条命令仍会弹出审批、命令黑名单（删除/格式化/注册表等直接拒绝）、'
                    + '工作目录限定项目根、超时自动终止进程树、可随时 Force Eject 中止。\n\n'
                    + '确定要开启吗？'
                );
                if (!ok) {
                    this.checked = false;
                    return;
                }
            }
            kiraraOptions.agent_shell_enabled = this.checked;
            saveOptions();
        });
    }

    // 人设卡片选择
    document.querySelectorAll('.persona-card').forEach(card => {
        card.addEventListener('click', function() {
            const personaKey = this.dataset.persona;
            if (!personaKey || personaKey === kiraraOptions.persona) return;
            kiraraOptions.persona = personaKey;
            document.querySelectorAll('.persona-card').forEach(c => c.classList.remove('selected'));
            this.classList.add('selected');
            const personaHint = document.getElementById('persona-hint');
            if (personaHint && personaMetaMap[personaKey]) {
                personaHint.textContent = personaMetaMap[personaKey].hint;
            }
            saveOptions();
        });
    });

    // 音色下拉选择
    const voiceSelect = document.getElementById('voice-select');
    if (voiceSelect) {
        voiceSelect.addEventListener('change', function() {
            kiraraOptions.voice = this.value;
            updateVoiceHint();
            saveOptions();
        });
    }

    // 试听按钮：预设使用各自示例文案，系统语音使用通用文案
    const previewBtn = document.getElementById('voice-preview-btn');
    if (previewBtn) {
        previewBtn.addEventListener('click', async function() {
            if (this.disabled) return;
            const selectedVoice = voiceSelect ? voiceSelect.value : (kiraraOptions.voice || 'preset:kirara');
            const sampleText = voicePresetSamples[selectedVoice] || '这是音声试听效果，一二三四五。';
            const originalText = this.textContent;
            this.disabled = true;
            this.textContent = '合成中…';
            await playKiraraTTS(sampleText, selectedVoice);
            this.textContent = originalText;
            if (ttsAvailable) this.disabled = false;
        });
    }

    // ===== 通讯接口事件绑定 =====
    bindCommPanelEvents();

    // ===== 技能管理事件绑定 =====
    bindSkillEditorEvents();

    // ===== SMTP / 重置面板 =====
    bindSmtpPanelEvents();
    bindResetPanelEvents();
}

// ==================== SMTP / 重置面板 ====================

function bindSmtpPanelEvents() {
    const saveBtn = document.getElementById('smtp-save-btn');
    const statusEl = document.getElementById('smtp-save-status');
    if (!saveBtn) return;

    // 初次进入 SMTP tab 时从后端读取当前配置（填充表单）
    const tabBtn = document.querySelector('.options-tab[data-options-tab="smtp"]');
    let smtpLoaded = false;
    if (tabBtn) {
        tabBtn.addEventListener('click', function () {
            if (smtpLoaded) return;
            fetch(KIRARA_API.RESET_SMTP_CONFIG)
                .then(r => r.json())
                .then(data => {
                    if (!data.success) return;
                    const cfg = data.config || {};
                    const h = document.getElementById('smtp-host');
                    const p = document.getElementById('smtp-port');
                    const u = document.getElementById('smtp-user');
                    const pa = document.getElementById('smtp-pass');
                    const f = document.getElementById('smtp-from');
                    const s = document.getElementById('smtp-ssl');
                    if (h) h.value = cfg.smtp_host || 'smtp.qq.com';
                    if (p) p.value = cfg.smtp_port || 465;
                    if (u) u.value = cfg.smtp_user || '';
                    if (pa) pa.placeholder = cfg.smtp_pass ? '*** (已保存，留空不变)' : '***';
                    if (f) f.value = cfg.from_addr || '';
                    if (s) s.value = String(cfg.use_ssl !== false);
                    smtpLoaded = true;
                })
                .catch(e => console.warn('[SMTP] 加载配置失败:', e));
        });
    }

    saveBtn.addEventListener('click', async function () {
        const h = document.getElementById('smtp-host');
        const p = document.getElementById('smtp-port');
        const u = document.getElementById('smtp-user');
        const pa = document.getElementById('smtp-pass');
        const f = document.getElementById('smtp-from');
        const s = document.getElementById('smtp-ssl');

        const payload = {
            smtp_host: (h ? h.value : '').trim(),
            smtp_port: parseInt(p ? p.value : '465') || 465,
            smtp_user: (u ? u.value : '').trim(),
            smtp_pass: (pa ? pa.value : '').trim() || '***', // '***' 表示保留原值
            from_addr: (f ? f.value : '').trim(),
            use_ssl: s ? s.value === 'true' : true,
        };

        saveBtn.disabled = true;
        saveBtn.textContent = '保存中...';
        statusEl.textContent = '';
        statusEl.className = 'save-status';

        try {
            const r = await fetch(KIRARA_API.RESET_SMTP_CONFIG, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const data = await r.json();
            if (data.success) {
                statusEl.textContent = '✓ 保存成功';
                statusEl.classList.add('ok');
                // 密码清空，占位符更新
                if (pa && pa.value && pa.value !== '***') { pa.value = ''; }
                smtpLoaded = false; // 重新进入时会 reload 刷新 placeholder
            } else {
                statusEl.textContent = '✗ ' + (data.error || '保存失败');
                statusEl.classList.add('err');
            }
        } catch (e) {
            statusEl.textContent = '✗ 网络错误: ' + e.message;
            statusEl.classList.add('err');
        } finally {
            saveBtn.disabled = false;
            saveBtn.textContent = '💾 保存 SMTP 配置';
            setTimeout(() => { statusEl.textContent = ''; statusEl.className = 'save-status'; }, 3000);
        }
    });
}

function bindResetPanelEvents() {
    const emailInput = document.getElementById('reset-email');
    const sendBtn = document.getElementById('reset-send-btn');
    const sendStatus = document.getElementById('reset-send-status');
    const codeSection = document.getElementById('reset-code-section');
    const codeInput = document.getElementById('reset-code');
    const execBtn = document.getElementById('reset-execute-btn');
    const execStatus = document.getElementById('reset-execute-status');
    const tabBtn = document.querySelector('.options-tab[data-options-tab="reset"]');

    if (!sendBtn || !execBtn) return;

    // 进入重置 tab 时，尝试从 user.json 读取注册邮箱作为默认值
    let resetLoaded = false;
    if (tabBtn) {
        tabBtn.addEventListener('click', function () {
            if (resetLoaded) return;
            fetch(KIRARA_API.USER_STATUS).catch(() => null); // 先预热
            // 简单尝试从 localStorage 恢复上次输入
            const saved = localStorage.getItem('kirara_reset_email') || '';
            if (emailInput && saved) emailInput.value = saved;
            resetLoaded = true;
        });
    }

    // 发送验证码
    sendBtn.addEventListener('click', async function () {
        const email = (emailInput ? emailInput.value : '').trim();
        if (!email || !/@/.test(email)) {
            sendStatus.textContent = '✗ 请输入有效邮箱';
            sendStatus.classList.add('err');
            return;
        }
        localStorage.setItem('kirara_reset_email', email);

        sendBtn.disabled = true;
        sendBtn.textContent = '发送中...';
        sendStatus.textContent = '';
        sendStatus.className = 'save-status';

        try {
            const r = await fetch(KIRARA_API.RESET_REQUEST_CODE, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email }),
            });
            const data = await r.json();
            if (data.success) {
                sendStatus.textContent = '✓ 验证码已发送（有效期 5 分钟）';
                sendStatus.classList.add('ok');
                if (data.debug_hint) {
                    console.warn('[Reset]', data.debug_hint);
                }
                // 显示验证码输入区
                if (codeSection) codeSection.style.display = 'block';
                if (codeInput) { codeInput.focus(); codeInput.value = ''; }
                // 60 秒冷却
                let cd = 60;
                sendBtn.textContent = `重试 (${cd}s)`;
                const cdTimer = setInterval(() => {
                    cd--;
                    if (cd <= 0) { clearInterval(cdTimer); sendBtn.textContent = '📤 重新发送'; sendBtn.disabled = false; }
                    else { sendBtn.textContent = `重试 (${cd}s)`; }
                }, 1000);
                sendBtn.disabled = true;
            } else {
                sendStatus.textContent = '✗ ' + (data.error || '发送失败');
                sendStatus.classList.add('err');
            }
        } catch (e) {
            sendStatus.textContent = '✗ 网络错误: ' + e.message;
            sendStatus.classList.add('err');
        }
    });

    // 执行重置（含 confirm + code 校验）
    execBtn.addEventListener('click', async function () {
        // 第一层 confirm
        if (!confirm('⚠️ 确认重置所有 Kirara 数据？\n\n这将清除会话、记忆、知识库，并恢复设置到默认值。\n此操作不可逆。')) {
            return;
        }

        const email = (emailInput ? emailInput.value : '').trim();
        const code = (codeInput ? codeInput.value : '').trim().toUpperCase();
        if (!email || !code) {
            execStatus.textContent = '✗ 请先发送并填写验证码';
            execStatus.classList.add('err');
            return;
        }

        execBtn.disabled = true;
        execBtn.textContent = '重置中...';
        execStatus.textContent = '';
        execStatus.className = 'save-status';

        try {
            const r = await fetch(KIRARA_API.RESET_EXECUTE, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, code }),
            });
            const data = await r.json();
            if (data.success) {
                execStatus.textContent = '✓ 重置完成！刷新页面生效';
                execStatus.classList.add('ok');
                execBtn.textContent = '✅ 完成';
                // 3 秒后刷新页面（让用户看到成功反馈）
                setTimeout(() => window.location.reload(), 2000);
            } else {
                execStatus.textContent = '✗ ' + (data.error || '重置失败');
                execStatus.classList.add('err');
                execBtn.disabled = false;
                execBtn.textContent = '⛔ 确认重置';
            }
        } catch (e) {
            execStatus.textContent = '✗ 网络错误: ' + e.message;
            execStatus.classList.add('err');
            execBtn.disabled = false;
            execBtn.textContent = '⛔ 确认重置';
        }
    });
}

// ==================== 技能管理功能 ====================
// 数据结构：{ id, name, description, content, enabled, created_at }
// 持久化：通过 /api/kirara/options 的 skills 字段（JSON 数组）存储于 options.json

let skillsListRendered = false;
let editingSkillId = null; // null=新增模式，非空=编辑模式

function getSkills() {
    if (!Array.isArray(kiraraOptions.skills)) kiraraOptions.skills = [];
    return kiraraOptions.skills;
}

function renderSkillsList() {
    const listEl = document.getElementById('skills-list');
    if (!listEl) return;
    const skills = getSkills();

    if (skills.length === 0) {
        listEl.innerHTML = '<div class="skills-empty">暂无技能。点击「添加技能」创建第一个技能。</div>';
        skillsListRendered = true;
        return;
    }

    listEl.innerHTML = '';
    skills.forEach(skill => {
        const card = document.createElement('div');
        card.className = 'skill-card' + (skill.enabled ? '' : ' disabled');
        card.dataset.skillId = skill.id;

        const header = document.createElement('div');
        header.className = 'skill-card-header';

        const titleArea = document.createElement('div');
        titleArea.className = 'skill-card-title-area';

        const nameEl = document.createElement('div');
        nameEl.className = 'skill-card-name';
        nameEl.textContent = skill.name || '未命名技能';

        const descEl = document.createElement('div');
        descEl.className = 'skill-card-desc';
        descEl.textContent = skill.description || '（无描述）';

        titleArea.appendChild(nameEl);
        titleArea.appendChild(descEl);

        const toggleLabel = document.createElement('label');
        toggleLabel.className = 'skill-toggle';
        toggleLabel.title = skill.enabled ? '已启用' : '已停用';
        const toggleInput = document.createElement('input');
        toggleInput.type = 'checkbox';
        toggleInput.checked = !!skill.enabled;
        toggleInput.addEventListener('change', function() {
            toggleSkill(skill.id, this.checked);
        });
        const toggleSlider = document.createElement('span');
        toggleSlider.className = 'skill-toggle-slider';
        toggleLabel.appendChild(toggleInput);
        toggleLabel.appendChild(toggleSlider);

        header.appendChild(titleArea);
        header.appendChild(toggleLabel);

        const body = document.createElement('div');
        body.className = 'skill-card-content';
        body.textContent = skill.content || '（无内容）';

        const footer = document.createElement('div');
        footer.className = 'skill-card-footer';

        const metaEl = document.createElement('span');
        metaEl.className = 'skill-card-meta';
        metaEl.textContent = skill.created_at ? `创建于 ${skill.created_at}` : '';

        const actionsEl = document.createElement('div');
        actionsEl.className = 'skill-card-actions';

        const editBtn = document.createElement('button');
        editBtn.className = 'action-btn skill-action-btn';
        editBtn.textContent = '✏️ 编辑';
        editBtn.addEventListener('click', () => openSkillEditor(skill.id));

        const delBtn = document.createElement('button');
        delBtn.className = 'action-btn skill-action-btn skill-delete-btn';
        delBtn.textContent = '🗑 删除';
        delBtn.addEventListener('click', () => deleteSkill(skill.id));

        actionsEl.appendChild(editBtn);
        actionsEl.appendChild(delBtn);
        footer.appendChild(metaEl);
        footer.appendChild(actionsEl);

        card.appendChild(header);
        card.appendChild(body);
        card.appendChild(footer);
        listEl.appendChild(card);
    });
    skillsListRendered = true;
}

function openSkillEditor(skillId) {
    const modal = document.getElementById('skill-editor-modal');
    if (!modal) return;
    const titleEl = document.getElementById('skill-editor-title');
    const nameInput = document.getElementById('skill-name-input');
    const descInput = document.getElementById('skill-desc-input');
    const contentInput = document.getElementById('skill-content-input');
    const enabledInput = document.getElementById('skill-enabled-input');

    if (skillId) {
        // 编辑模式
        const skill = getSkills().find(s => s.id === skillId);
        if (!skill) return;
        editingSkillId = skillId;
        if (titleEl) titleEl.textContent = '编辑技能';
        if (nameInput) nameInput.value = skill.name || '';
        if (descInput) descInput.value = skill.description || '';
        if (contentInput) contentInput.value = skill.content || '';
        if (enabledInput) enabledInput.checked = !!skill.enabled;
    } else {
        // 新增模式
        editingSkillId = null;
        if (titleEl) titleEl.textContent = '添加技能';
        if (nameInput) nameInput.value = '';
        if (descInput) descInput.value = '';
        if (contentInput) contentInput.value = '';
        if (enabledInput) enabledInput.checked = true;
    }
    updateSkillContentCounter();
    modal.classList.add('show');
    if (nameInput) setTimeout(() => nameInput.focus(), 50);
}

function closeSkillEditor() {
    const modal = document.getElementById('skill-editor-modal');
    if (modal) modal.classList.remove('show');
    editingSkillId = null;
}

function updateSkillContentCounter() {
    const contentInput = document.getElementById('skill-content-input');
    const counter = document.getElementById('skill-content-counter');
    if (contentInput && counter) {
        counter.textContent = `${contentInput.value.length} / 8000`;
    }
}

function saveSkillFromForm() {
    const nameInput = document.getElementById('skill-name-input');
    const descInput = document.getElementById('skill-desc-input');
    const contentInput = document.getElementById('skill-content-input');
    const enabledInput = document.getElementById('skill-enabled-input');

    const name = (nameInput?.value || '').trim();
    const desc = (descInput?.value || '').trim();
    const content = (contentInput?.value || '').trim();
    const enabled = !!(enabledInput && enabledInput.checked);

    if (!name) {
        alert('请填写技能名称');
        nameInput?.focus();
        return;
    }
    if (!content) {
        alert('请填写技能内容（提示词）');
        contentInput?.focus();
        return;
    }

    const skills = getSkills();
    if (editingSkillId) {
        // 编辑：保留原 id 与 created_at
        const idx = skills.findIndex(s => s.id === editingSkillId);
        if (idx >= 0) {
            const orig = skills[idx];
            skills[idx] = {
                id: orig.id,
                name,
                description: desc,
                content,
                enabled,
                created_at: orig.created_at || new Date().toISOString().slice(0, 19).replace('T', ' ')
            };
        }
    } else {
        // 新增
        const newSkill = {
            id: `skill_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
            name,
            description: desc,
            content,
            enabled,
            created_at: new Date().toISOString().slice(0, 19).replace('T', ' ')
        };
        skills.push(newSkill);
    }

    closeSkillEditor();
    renderSkillsList();
    saveOptions();
}

function deleteSkill(skillId) {
    const skill = getSkills().find(s => s.id === skillId);
    if (!skill) return;
    if (!confirm(`确定删除技能「${skill.name}」吗？此操作不可撤销。`)) return;
    kiraraOptions.skills = getSkills().filter(s => s.id !== skillId);
    renderSkillsList();
    saveOptions();
}

function toggleSkill(skillId, enabled) {
    const skill = getSkills().find(s => s.id === skillId);
    if (!skill) return;
    skill.enabled = !!enabled;
    // 更新卡片视觉态而不重渲染（避免抖动）
    const card = document.querySelector(`.skill-card[data-skill-id="${skillId}"]`);
    if (card) card.classList.toggle('disabled', !enabled);
    saveOptions();
}

function bindSkillEditorEvents() {
    const addBtn = document.getElementById('skill-add-btn');
    const closeBtn = document.getElementById('skill-editor-close');
    const cancelBtn = document.getElementById('skill-cancel-btn');
    const saveBtn = document.getElementById('skill-save-btn');
    const contentInput = document.getElementById('skill-content-input');
    const modal = document.getElementById('skill-editor-modal');

    if (addBtn) addBtn.addEventListener('click', () => openSkillEditor(null));
    if (closeBtn) closeBtn.addEventListener('click', closeSkillEditor);
    if (cancelBtn) cancelBtn.addEventListener('click', closeSkillEditor);
    if (saveBtn) saveBtn.addEventListener('click', saveSkillFromForm);
    if (contentInput) contentInput.addEventListener('input', updateSkillContentCounter);
    // 点击遮罩关闭
    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === modal) closeSkillEditor();
        });
    }
    // ESC 关闭
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && modal && modal.classList.contains('show')) {
            closeSkillEditor();
        }
    });
}

// ==================== 通讯接口（OpenMaid 迁移 Phase A）====================
// 对接 /api/ai/openmaid/* 后端（网关 + iMessage + QQ），不修改后端。
// 网关配置字段：socketUrl / token / sessionKey / language（依 lmbrew.py 实际形状）。

const COMM_API_BASE = '/api/ai/openmaid';
let commGatewayCache = { socketUrl: '', token: '', sessionKey: '', language: 'zh-CN' };
let commEventsBound = false;

// 轻量提示：优先复用 kirara 的全局 showToast，否则回退 alert
function commToast(msg, type) {
    try {
        if (typeof showToast === 'function') { showToast(msg, type || 'info'); return; }
        if (typeof window.showToast === 'function') { window.showToast(msg, type || 'info'); return; }
    } catch (_) { /* 忽略 */ }
    alert(msg);
}

// Token 掩码：保留末 4 位
function maskToken(t) {
    if (!t) return '';
    return '••••' + String(t).slice(-4);
}

// 设置网关状态圆点：state = online | offline | checking
function setGatewayDot(state, text) {
    const dot = document.getElementById('comm-status-dot');
    const txt = document.getElementById('comm-status-text');
    if (dot) {
        dot.classList.remove('online', 'offline', 'checking');
        dot.classList.add(state);
    }
    if (txt) txt.textContent = text;
}

// 设置通道状态徽标 + 连接/断开按钮可用性
// prefix: 'imessage' | 'qq'；status: 显示文案；connected: 是否已连接
function setIfaceStatus(prefix, status, connected) {
    const badge = document.getElementById(`comm-${prefix}-status`);
    if (badge) {
        badge.textContent = status;
        badge.classList.remove('connected', 'disconnected', 'error');
        badge.classList.add(connected ? 'connected' : 'disconnected');
    }
    const connectBtn = document.getElementById(`comm-${prefix}-connect`);
    const disconnectBtn = document.getElementById(`comm-${prefix}-disconnect`);
    if (connectBtn) connectBtn.disabled = !!connected;
    if (disconnectBtn) disconnectBtn.disabled = !connected;
}

// 通道错误态：徽标标红，连接按钮可用、断开按钮禁用
function setIfaceError(prefix, status) {
    const badge = document.getElementById(`comm-${prefix}-status`);
    if (badge) {
        badge.textContent = status;
        badge.classList.remove('connected', 'disconnected', 'error');
        badge.classList.add('error');
    }
    const connectBtn = document.getElementById(`comm-${prefix}-connect`);
    const disconnectBtn = document.getElementById(`comm-${prefix}-disconnect`);
    if (connectBtn) connectBtn.disabled = false;
    if (disconnectBtn) disconnectBtn.disabled = true;
}

// 顶层加载器：并行加载网关配置/状态与各通道状态
async function loadCommPanel() {
    bindCommPanelEvents();
    await Promise.allSettled([
        loadGatewayConfig(),
        refreshGatewayStatus(),
        loadImessageStatus(),
        loadQqStatus()
    ]);
}

// ===== 网关配置 =====
async function loadGatewayConfig() {
    try {
        const resp = await fetch(`${COMM_API_BASE}/config/gateway`);
        const data = await resp.json();
        if (!resp.ok || data.error) {
            console.warn('网关配置加载异常:', data.error || resp.status);
            return;
        }
        commGatewayCache = {
            socketUrl: data.socketUrl || '',
            token: data.token || '',
            sessionKey: data.sessionKey || '',
            language: data.language || 'zh-CN'
        };
        const setVal = (id, v) => { const el = document.getElementById(id); if (el) el.value = v ?? ''; };
        setVal('comm-gateway-socket-url', commGatewayCache.socketUrl);
        setVal('comm-gateway-token', maskToken(commGatewayCache.token));
        setVal('comm-gateway-session-key', commGatewayCache.sessionKey);
        setVal('comm-gateway-language', commGatewayCache.language);
    } catch (e) {
        console.error('加载网关配置失败:', e);
    }
}

async function saveGatewayConfig() {
    const getVal = (id) => (document.getElementById(id) ? (document.getElementById(id).value || '').trim() : '');
    let token = getVal('comm-gateway-token');
    // 若 Token 未改动（仍为掩码）则保留原值，避免误清空
    if (token === maskToken(commGatewayCache.token)) {
        token = commGatewayCache.token;
    }
    const payload = {
        socketUrl: getVal('comm-gateway-socket-url'),
        token: token,
        sessionKey: getVal('comm-gateway-session-key'),
        language: getVal('comm-gateway-language') || 'zh-CN'
    };
    try {
        const resp = await fetch(`${COMM_API_BASE}/config/gateway`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await resp.json();
        if (!resp.ok || data.error) {
            commToast(data.error || '保存失败', 'error');
            return;
        }
        commGatewayCache = {
            socketUrl: payload.socketUrl,
            token: payload.token,
            sessionKey: payload.sessionKey,
            language: payload.language
        };
        const tokenEl = document.getElementById('comm-gateway-token');
        if (tokenEl) tokenEl.value = maskToken(commGatewayCache.token);
        commToast(data.message || '网关配置已保存', 'success');
    } catch (e) {
        console.error('保存网关配置失败:', e);
        commToast('保存网关配置失败', 'error');
    }
}

async function refreshGatewayStatus() {
    setGatewayDot('checking', '检测中...');
    try {
        const resp = await fetch(`${COMM_API_BASE}/gateway/snapshot`);
        const data = await resp.json();
        if (!resp.ok || data.error) {
            console.warn('网关快照异常:', data.error || resp.status);
            setGatewayDot('offline', '状态异常');
            return;
        }
        const online = data.gatewayStatus === 'online';
        setGatewayDot(online ? 'online' : 'offline', online ? `在线（${data.timestamp || ''}）` : '离线');
    } catch (e) {
        console.error('刷新网关状态失败:', e);
        setGatewayDot('offline', '刷新失败');
    }
}

// ===== iMessage =====
function applyImessageStatus(data) {
    if (!data || typeof data !== 'object') { setIfaceStatus('imessage', '未检测', false); return; }
    if (data.connected) {
        setIfaceStatus('imessage', '在线', true);
    } else {
        setIfaceStatus('imessage', data.message || '离线', false);
    }
}

async function loadImessageStatus() {
    try {
        const resp = await fetch(`${COMM_API_BASE}/comm/imessage/status`);
        const data = await resp.json();
        if (!resp.ok || data.error) {
            console.warn('iMessage 状态异常:', data.error || resp.status);
            setIfaceError('imessage', '状态异常');
            return;
        }
        applyImessageStatus(data);
    } catch (e) {
        console.error('加载 iMessage 状态失败:', e);
        setIfaceError('imessage', '加载失败');
    }
}

async function checkImessage() {
    setIfaceStatus('imessage', '检测中...', false);
    try {
        const resp = await fetch(`${COMM_API_BASE}/comm/imessage/check`);
        const data = await resp.json();
        if (!resp.ok || data.error) {
            setIfaceError('imessage', data.error || '检测失败');
            commToast(data.error || 'iMessage 检测失败', 'error');
            return;
        }
        applyImessageStatus(data);
        commToast(data.message || (data.connected ? 'iMessage 可用' : 'iMessage 不可用'), data.connected ? 'success' : 'info');
    } catch (e) {
        console.error('检测 iMessage 失败:', e);
        setIfaceError('imessage', '检测失败');
    }
}

async function connectImessage() {
    const appleId = prompt('请输入 Apple ID：');
    if (appleId === null) return;
    const deviceName = prompt('请输入设备名称：');
    if (deviceName === null) return;
    setIfaceStatus('imessage', '连接中...', false);
    try {
        const resp = await fetch(`${COMM_API_BASE}/comm/imessage/connect`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ apple_id: appleId || '', device_name: deviceName || '' })
        });
        const data = await resp.json();
        applyImessageStatus(data);
        commToast(data.message || (data.connected ? 'iMessage 已连接' : '连接未成功'), data.connected ? 'success' : 'error');
    } catch (e) {
        console.error('连接 iMessage 失败:', e);
        setIfaceError('imessage', '连接失败');
        commToast('连接 iMessage 失败', 'error');
    }
}

async function disconnectImessage() {
    setIfaceStatus('imessage', '断开中...', true);
    try {
        const resp = await fetch(`${COMM_API_BASE}/comm/imessage/disconnect`, { method: 'POST' });
        const data = await resp.json();
        applyImessageStatus(data);
        commToast(data.message || '已断开', 'info');
    } catch (e) {
        console.error('断开 iMessage 失败:', e);
        setIfaceError('imessage', '断开失败');
    }
}

async function sendImessage() {
    const recipient = (document.getElementById('comm-imessage-recipient') ? document.getElementById('comm-imessage-recipient').value : '').trim();
    const message = (document.getElementById('comm-imessage-msg') ? document.getElementById('comm-imessage-msg').value : '').trim();
    if (!recipient || !message) { commToast('请填写接收方和消息内容', 'error'); return; }
    try {
        const resp = await fetch(`${COMM_API_BASE}/comm/imessage/send`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ recipient: recipient, message: message })
        });
        const data = await resp.json();
        commToast(data.message || (data.success ? '发送成功' : '发送失败'), data.success ? 'success' : 'error');
        if (data.success) {
            const r = document.getElementById('comm-imessage-recipient');
            const m = document.getElementById('comm-imessage-msg');
            if (r) r.value = '';
            if (m) m.value = '';
        }
    } catch (e) {
        console.error('发送 iMessage 失败:', e);
        commToast('发送消息失败', 'error');
    }
}

// ===== QQ =====
function applyQqStatus(data) {
    if (!data || typeof data !== 'object') { setIfaceStatus('qq', '未检测', false); return; }
    if (data.connected) {
        setIfaceStatus('qq', '在线', true);
    } else {
        setIfaceStatus('qq', data.message || '离线', false);
    }
}

async function loadQqStatus() {
    try {
        const resp = await fetch(`${COMM_API_BASE}/comm/qq/status`);
        const data = await resp.json();
        if (!resp.ok || data.error) {
            console.warn('QQ 状态异常:', data.error || resp.status);
            setIfaceError('qq', '状态异常');
            return;
        }
        applyQqStatus(data);
    } catch (e) {
        console.error('加载 QQ 状态失败:', e);
        setIfaceError('qq', '加载失败');
    }
}

async function checkQq() {
    setIfaceStatus('qq', '检测中...', false);
    try {
        const resp = await fetch(`${COMM_API_BASE}/comm/qq/check`);
        const data = await resp.json();
        if (!resp.ok || data.error) {
            setIfaceError('qq', data.error || '检测失败');
            commToast(data.error || 'QQ 检测失败', 'error');
            return;
        }
        applyQqStatus(data);
        commToast(data.message || (data.connected ? 'QQ 可用' : 'QQ 不可用'), data.connected ? 'success' : 'info');
    } catch (e) {
        console.error('检测 QQ 失败:', e);
        setIfaceError('qq', '检测失败');
    }
}

async function connectQq() {
    const apiUrl = prompt('请输入 QQ API URL（如 http://127.0.0.1:8765）：');
    if (apiUrl === null) return;
    if (!apiUrl || !apiUrl.trim()) { commToast('API URL 不能为空', 'error'); return; }
    const qqNumber = prompt('请输入 QQ 号码（可留空）：');
    if (qqNumber === null) return;
    const botToken = prompt('请输入 Bot Token（可留空）：');
    if (botToken === null) return;
    setIfaceStatus('qq', '连接中...', false);
    try {
        const resp = await fetch(`${COMM_API_BASE}/comm/qq/connect`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_url: apiUrl.trim(), qq_number: qqNumber.trim(), bot_token: botToken.trim() })
        });
        const data = await resp.json();
        applyQqStatus(data);
        commToast(data.message || (data.connected ? 'QQ 已连接' : '连接未成功'), data.connected ? 'success' : 'error');
    } catch (e) {
        console.error('连接 QQ 失败:', e);
        setIfaceError('qq', '连接失败');
        commToast('连接 QQ 失败', 'error');
    }
}

async function disconnectQq() {
    setIfaceStatus('qq', '断开中...', true);
    try {
        const resp = await fetch(`${COMM_API_BASE}/comm/qq/disconnect`, { method: 'POST' });
        const data = await resp.json();
        applyQqStatus(data);
        commToast(data.message || '已断开', 'info');
    } catch (e) {
        console.error('断开 QQ 失败:', e);
        setIfaceError('qq', '断开失败');
    }
}

async function sendQq() {
    const targetType = document.getElementById('comm-qq-target-type') ? document.getElementById('comm-qq-target-type').value : 'friend';
    const targetId = (document.getElementById('comm-qq-target-id') ? document.getElementById('comm-qq-target-id').value : '').trim();
    const message = (document.getElementById('comm-qq-msg') ? document.getElementById('comm-qq-msg').value : '').trim();
    if (!targetId || !message) { commToast('请填写目标和消息内容', 'error'); return; }
    const isGroup = targetType === 'group';
    const endpoint = isGroup ? `${COMM_API_BASE}/comm/qq/send_group` : `${COMM_API_BASE}/comm/qq/send`;
    const payload = isGroup ? { group_id: targetId, message: message } : { recipient: targetId, message: message };
    try {
        const resp = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await resp.json();
        commToast(data.message || (data.success ? '发送成功' : '发送失败'), data.success ? 'success' : 'error');
        if (data.success) {
            const m = document.getElementById('comm-qq-msg');
            if (m) m.value = '';
        }
    } catch (e) {
        console.error('发送 QQ 消息失败:', e);
        commToast('发送消息失败', 'error');
    }
}

// 兜底提取列表数据：兼容数组 / {friends|groups|data|list|items|result:[]}
function extractCommItems(data) {
    if (Array.isArray(data)) return data;
    if (!data || typeof data !== 'object') return [];
    const keys = ['friends', 'groups', 'data', 'list', 'items', 'result'];
    for (const k of keys) { if (Array.isArray(data[k])) return data[k]; }
    return [];
}

function renderCommList(ul, items, idKey, nameKeys) {
    if (!ul) return;
    if (!items || items.length === 0) {
        ul.innerHTML = '<li class="comm-empty">暂无数据</li>';
        return;
    }
    ul.innerHTML = '';
    items.forEach(item => {
        const li = document.createElement('li');
        if (item && typeof item === 'object') {
            const id = item[idKey] != null ? item[idKey] : (item.id != null ? item.id : '');
            let name = '';
            for (const k of nameKeys) { if (item[k]) { name = item[k]; break; } }
            if (!name) name = String(id);
            li.textContent = id ? `${name}（${id}）` : String(name);
            li.dataset.targetId = String(id);
        } else {
            li.textContent = String(item);
            li.dataset.targetId = String(item);
        }
        li.addEventListener('click', function () {
            const targetId = document.getElementById('comm-qq-target-id');
            if (targetId) targetId.value = this.dataset.targetId || '';
        });
        ul.appendChild(li);
    });
}

async function refreshQqLists() {
    const friendsUl = document.getElementById('comm-qq-friends');
    const groupsUl = document.getElementById('comm-qq-groups');
    if (friendsUl) friendsUl.innerHTML = '<li class="comm-empty">加载中...</li>';
    if (groupsUl) groupsUl.innerHTML = '<li class="comm-empty">加载中...</li>';
    try {
        const results = await Promise.allSettled([
            fetch(`${COMM_API_BASE}/comm/qq/friends`),
            fetch(`${COMM_API_BASE}/comm/qq/groups`)
        ]);
        const fData = results[0].status === 'fulfilled' ? await results[0].value.json().catch(() => ({})) : {};
        const gData = results[1].status === 'fulfilled' ? await results[1].value.json().catch(() => ({})) : {};
        renderCommList(friendsUl, extractCommItems(fData), 'user_id', ['nickname', 'name', 'remark']);
        renderCommList(groupsUl, extractCommItems(gData), 'group_id', ['group_name', 'name']);
        commToast('列表已刷新', 'success');
    } catch (e) {
        console.error('刷新 QQ 列表失败:', e);
        if (friendsUl) friendsUl.innerHTML = '<li class="comm-empty">加载失败</li>';
        if (groupsUl) groupsUl.innerHTML = '<li class="comm-empty">加载失败</li>';
        commToast('刷新列表失败', 'error');
    }
}

// 绑定通讯面板所有按钮（幂等，仅绑定一次）
function bindCommPanelEvents() {
    if (commEventsBound) return;
    commEventsBound = true;
    const bind = (id, handler) => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('click', handler);
    };
    bind('comm-gateway-save', saveGatewayConfig);
    bind('comm-gateway-refresh', refreshGatewayStatus);
    bind('comm-imessage-check', checkImessage);
    bind('comm-imessage-connect', connectImessage);
    bind('comm-imessage-disconnect', disconnectImessage);
    bind('comm-imessage-send', sendImessage);
    bind('comm-qq-check', checkQq);
    bind('comm-qq-connect', connectQq);
    bind('comm-qq-disconnect', disconnectQq);
    bind('comm-qq-send', sendQq);
    bind('comm-qq-refresh-list', refreshQqLists);
}

window.loadCommPanel = loadCommPanel;

