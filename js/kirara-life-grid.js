// Kirara 立绘背景：100×100 隐藏网格 + 康威生命游戏（Moore 邻域）
// 当用户输入文字时，提取前几个词的 token 值（哈希近似），二进制化后作为种子点亮灯泡
// 生命游戏迭代直至稳定或达到上限，结束后所有灯泡熄灭（静息状态）
// 灯泡颜色：金色 (#FFD700)

/*

很多人问我为什么最近在玩元胞自动机。事实上，想想看《三体》里的人列计算机，本身具有图灵完备性。

从《复杂》这本书的角度来说，一种复杂模型其实往往具有简单的规则。我是相信“人类的意识来源于神经元的共同活动”一说的。

最近我在YouTube上看到了一个影片，大概的内容就是外国一个团队把transformer架构的代码翻译为了游戏《Minecraft》的地图文件，使得红石电路可以进行完整的推理操作。（当然还需要他们写的MOD文件的加持）

其实我们最近有一个秘密研究项目，那就是借助生命游戏的原理训练词嵌入系统，甚至可以用于文本生成。最关键的是，这种模型在特定的数据环境下可以自己长大，于是我们不需要特意去训练它。

按照游戏《特战精英最终章：神的惩罚》里面一个类似的系统的描述，我们希望这个系统像是下文中写的一样：

“巴里和他的学生威尔·奥斯本基于星穹主机里面的意识体，制造出了新的人工智能架构“Quasar”。这是一种和Transformer截然不同的，结合了元胞自动机、进化算法、密宗和一点点讽刺的新的AI架构。

“Quasar模型最大的特点就是，只需要极其微小的模型体量，结合基于元胞自动机的“神经矩阵”算法，使得原本的胚胎程序在特定的网络环境下就可以实现自动演化。（全程的训练均为自动进行。）

”根据巴里的实验，Quasar模型在10分钟（Epoch 30992）以后学会了使用网络语言骂人（“理解了词组‘我铥’的双关含义”）；30分钟(Epoch 102346)以后进化出了ReAct循环；1个小时(Epoch 219388)以后学会了使用MCP服务器。”

*/ 

(function () {
    'use strict';

    // ---------- 配置 ----------
    const GRID_SIZE = 100;              // 100×100 隐藏网格
    const CELL_PX = 5;                  // 每格 5 像素 → 画布 500×500
    const CANVAS_PX = GRID_SIZE * CELL_PX;
    const BULB_COLOR = '#FFD700';       // 金色灯泡本体
    const GLOW_COLOR = 'rgba(255, 215, 0, 0.35)';  // 灯泡柔光
    const TICK_MS = 80;                 // 每代间隔（≈12 fps）
    const MAX_GENERATIONS = 300;        // 安全上限
    const NUM_WORDS = 5;                // 提取前 5 个词
    const STABLE_LIMIT = 3;            // 连续 N 代活细胞数不变 → 视为稳定

    // ---------- 状态 ----------
    let canvas = null;
    let ctx = null;
    let grid = null;          // Uint8Array[GRID_SIZE][GRID_SIZE]，0/1
    let nextGrid = null;      // 双缓冲
    let timer = null;
    let generation = 0;
    let lastLiveCount = -1;
    let stableCount = 0;

    // ---------- 网格工具 ----------
    function makeGrid() {
        const g = new Array(GRID_SIZE);
        for (let y = 0; y < GRID_SIZE; y++) {
            g[y] = new Uint8Array(GRID_SIZE);
        }
        return g;
    }

    function clearGrid() {
        if (!grid) return;
        for (let y = 0; y < GRID_SIZE; y++) {
            grid[y].fill(0);
        }
    }

    function countLive() {
        let n = 0;
        for (let y = 0; y < GRID_SIZE; y++) {
            const row = grid[y];
            for (let x = 0; x < GRID_SIZE; x++) {
                if (row[x]) n++;
            }
        }
        return n;
    }

    // ---------- 渲染 ----------
    function draw() {
        if (!ctx) return;
        ctx.clearRect(0, 0, CANVAS_PX, CANVAS_PX);

        // 柔光层
        ctx.fillStyle = GLOW_COLOR;
        for (let y = 0; y < GRID_SIZE; y++) {
            const row = grid[y];
            for (let x = 0; x < GRID_SIZE; x++) {
                if (row[x]) {
                    ctx.beginPath();
                    ctx.arc(x * CELL_PX + CELL_PX / 2, y * CELL_PX + CELL_PX / 2, CELL_PX, 0, Math.PI * 2);
                    ctx.fill();
                }
            }
        }
        // 金色灯泡本体
        ctx.fillStyle = BULB_COLOR;
        for (let y = 0; y < GRID_SIZE; y++) {
            const row = grid[y];
            for (let x = 0; x < GRID_SIZE; x++) {
                if (row[x]) {
                    ctx.beginPath();
                    ctx.arc(x * CELL_PX + CELL_PX / 2, y * CELL_PX + CELL_PX / 2, CELL_PX / 2, 0, Math.PI * 2);
                    ctx.fill();
                }
            }
        }
    }

    // ---------- 康威生命游戏 ----------
    // Moore 邻域（8 邻居），环面（toroidal）边界
    function step() {
        for (let y = 0; y < GRID_SIZE; y++) {
            const ym = (y - 1 + GRID_SIZE) % GRID_SIZE;
            const yp = (y + 1) % GRID_SIZE;
            const row = grid[y];
            const rowM = grid[ym];
            const rowP = grid[yp];
            const nextRow = nextGrid[y];
            for (let x = 0; x < GRID_SIZE; x++) {
                const xm = (x - 1 + GRID_SIZE) % GRID_SIZE;
                const xp = (x + 1) % GRID_SIZE;
                let n = 0;
                if (rowM[xm]) n++;
                if (rowM[x]) n++;
                if (rowM[xp]) n++;
                if (row[xm]) n++;
                if (row[xp]) n++;
                if (rowP[xm]) n++;
                if (rowP[x]) n++;
                if (rowP[xp]) n++;

                const alive = row[x];
                // 标准规则：活细胞 2/3 邻居存活；死细胞恰好 3 邻居复活
                if (alive) {
                    nextRow[x] = (n === 2 || n === 3) ? 1 : 0;
                } else {
                    nextRow[x] = (n === 3) ? 1 : 0;
                }
            }
        }
        // 交换双缓冲
        const tmp = grid;
        grid = nextGrid;
        nextGrid = tmp;
    }

    function tick() {
        step();
        generation++;
        draw();

        const live = countLive();

        // 终止条件 1：所有灯泡熄灭
        if (live === 0) {
            stopAndRest();
            return;
        }
        // 终止条件 2：连续多代活细胞数不变 → 稳定
        if (live === lastLiveCount) {
            stableCount++;
            if (stableCount >= STABLE_LIMIT) {
                stopAndRest();
                return;
            }
        } else {
            stableCount = 0;
        }
        lastLiveCount = live;

        // 终止条件 3：超过代数上限
        if (generation >= MAX_GENERATIONS) {
            stopAndRest();
            return;
        }

        timer = setTimeout(tick, TICK_MS);
    }

    // 结束动画并回到静息状态（全部熄灭）
    function stopAndRest() {
        if (timer) {
            clearTimeout(timer);
            timer = null;
        }
        clearGrid();
        draw();
        generation = 0;
        lastLiveCount = -1;
        stableCount = 0;
    }

    // ---------- 文本 → 二进制种子 ----------
    // 简易分词：按空白与中英文标点切分
    function tokenizeWords(text) {
        if (!text) return [];
        return text.trim()
            .split(/[\s,.;:!?,。；：！？、（）()「」【】\[\]{}"'`\-—~～\n\r\t]+/)
            .filter(w => w.length > 0);
    }

    // DJB2 哈希：把词语映射到 32 位无符号整数（近似 token 值）
    function hashDJB2(s) {
        let h = 5381;
        for (let i = 0; i < s.length; i++) {
            h = (((h << 5) + h) + s.charCodeAt(i)) | 0;
        }
        return h >>> 0;  // 转为无符号 32 位
    }

    // 32 位整数 → 32 位二进制数组（高位在前）
    function toBits(num) {
        const bits = new Uint8Array(32);
        for (let i = 0; i < 32; i++) {
            bits[i] = (num >>> (31 - i)) & 1;
        }
        return bits;
    }

    // 公开 API：根据输入文本点亮初始种子并启动生命游戏
    function seedFromText(text) {
        if (!canvas) return;
        stopAndRest();           // 先清空之前的状态
        clearGrid();

        const words = tokenizeWords(text).slice(0, NUM_WORDS);
        if (words.length === 0) {
            draw();
            return;
        }

        // 每个词的 32 位二进制按行铺设到网格中央一带
        // 行范围：把 N 行均匀分布在网格中央 ± 区域，行间距 4
        const colStart = Math.floor((GRID_SIZE - 32) / 2);  // 32 位居中
        const rowStart = Math.floor(GRID_SIZE / 2) - Math.floor(words.length / 2) * 4;

        words.forEach((w, i) => {
            const hash = hashDJB2(w);
            const bits = toBits(hash);
            const y = rowStart + i * 4;
            if (y < 0 || y >= GRID_SIZE) return;
            const row = grid[y];
            for (let b = 0; b < 32; b++) {
                const x = colStart + b;
                if (x >= 0 && x < GRID_SIZE) {
                    row[x] = bits[b];
                }
            }
        });

        draw();
        generation = 0;
        lastLiveCount = countLive();
        stableCount = 0;
        if (timer) { clearTimeout(timer); timer = null; }
        timer = setTimeout(tick, 200);  // 200ms 后开始迭代
    }

    // ---------- 初始化 ----------
    function init() {
        canvas = document.getElementById('kirara-bg-canvas');
        if (!canvas) return;
        canvas.width = CANVAS_PX;
        canvas.height = CANVAS_PX;
        ctx = canvas.getContext('2d');
        grid = makeGrid();
        nextGrid = makeGrid();
        draw();
    }

    // 暴露 API
    window.kiraraLifeGrid = {
        init: init,
        seedFromText: seedFromText,
        stop: stopAndRest
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
