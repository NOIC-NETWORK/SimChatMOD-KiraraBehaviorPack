"""Kirara 桌宠 · Win32 分层窗口（Layered Window，逐像素 alpha）实现。

加载 MOD 里的立绘 PNG，用 UpdateLayeredWindow 把预乘 alpha 的位图交给 DWM，
桌面内容从透明像素里透出来，不做任何 WebView 合成。

能力：
    · 无边框、置顶（WS_EX_TOPMOST）、不进任务栏（WS_EX_TOOLWINDOW）
    · 左键拖动移动窗口；透明像素命中测试返回 HTTRANSPARENT，不挡后面的窗口
    · 点立绘展开／收起扁平八色圆形按钮阵列（旋转展开动画）
    · 按钮（左上角起逆时针）：语音 / 提示词 / Go Live / 插件 / 设置 / 退出 / 上下文 / 服装
    · 「服装」打开独立的皮肤选择窗口（扫描 common/ 下实际存在的 PNG）
    · 右键弹出菜单：归位 / 退出

单独运行（只看桌宠）：
    py .simchat/mods/kirara/python/pet_window.py
"""

import ctypes
import json
import math
import os
import threading
import time
import urllib.error
import urllib.request

import win32api
import win32con
import win32gui
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

_PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_COMMON_DIR = os.path.join(_PACKAGE_DIR, "sprites", "characters", "kirara", "common")
_DEFAULT_SPRITE = os.path.join(_COMMON_DIR, "kirara-common-default.png")

# 皮肤显示名：以 kirara.html「切换装扮」里的 h3 为准，键是磁盘上真实存在的文件名。
# 与旧代码/旧网页对不上的地方见 README 式的注释，不改文件、不猜文件名。
_SKIN_LABELS = {
    "kirara-common-default.png": "绮罗罗机甲 Mk.1",        # kirara.html: 绮罗罗机甲 Mk.1
    "kirara-casual1-default.png": "默认服装",              # kirara.html: 默认服装
    "kirara-sightseeing-default.png": "郊游服装",          # kirara.html: 郊游服装（内容与 catPajama 完全相同）
    "kirara-xmas-default.png": "圣诞节服装",               # kirara.html: 圣诞节服装
    "kirara-catPajama-default.png": "猫咪睡衣",            # kirara.html: 猫咪睡衣
    "kirara-swimsuit-default.png": "海洋装扮",             # kirara.html: 海洋装扮
    "kirara-qipao-default.png": "旗袍",                    # kirara.html: 旗袍
    "kirara-ebina-default.png": "海老名绮罗（小★龙★虾）",  # 对应 kirara.html 的 kirara-claw-default.png（磁盘无此文件；网页写 ⭐，雅黑无此字形，改用 ★）
    "kirara-netrunner1-default.png": "网络行者",           # 旧代码写 netrunner（磁盘为 netrunner1）；kirara.html 未列出
}

# 禁用名单：文件还在磁盘、也仍然列出，但卡片不可选。
# 以后美术画完素体，把对应文件名从这里删掉即可恢复，不需要改别处。
_SKIN_DISABLED = {
    "kirara-catPajama-default.png",   # 素体阶段，未完成
    "kirara-sightseeing-default.png",  # 素体阶段，未完成（与 catPajama 同一份图）
}

# 卡片悬停说明：原文逐条取自 kirara.html「切换装扮」每个 .character-option 的 <p>，不改写。
# 只做 HTML 渲染时的空白折叠（换行/缩进合并成一个空格）。
# kirara-netrunner1-default.png（网络行者）在 kirara.html 里没有对应条目，故意不收录，宁可无说明也不编。
_SKIN_DESCRIPTIONS = {
    "kirara-casual1-default.png": "Kirara的默认服装，设计得休闲而不失优雅，是绮罗日常出街时穿的衣服。不仔细看根本无法发现是个ai",
    "kirara-sightseeing-default.png": "为什么不带着绮罗出去旅行呢？女朋友的眼睛肯定会盯着不放的！（“绮罗是谁！！”）",
    "kirara-xmas-default.png": "不得把绮罗挂在圣诞树上作为发光体。",
    "kirara-catPajama-default.png": "哈基米~🐱",
    "kirara-swimsuit-default.png": "夏天~和绮罗去游泳吧！说到夏天果然泳装最棒了呢~！(●ˇ∀ˇ●)",
    "kirara-qipao-default.png": "我恭喜你发财，我恭喜你精彩……最好的请过来，不好的请走开……哦礼多人不怪",
    "kirara-common-default.png": "绮罗的“战斗服”，亦在本社的《Special Ops》系列游戏中登场过。 （忘了天选姬吧，我当智能体养你……(*/ω＼*)）",
    "kirara-ebina-default.png": "一种claw-like agent, 她可以管理你的日程，自动回复电子邮件，查出你欠了花呗多少钱，还会威风堂堂地部署烂代码。",
}

_CLASS_NAME = "SimChatKiraraLayeredPet"
# 通用弹窗容器的窗口类名；后缀用进程内递增序号，避免 id() 复用导致重开时 RegisterClass 报 1410
_POPUP_CLASS_NAME = "SimChatKiraraPopup"
_POPUP_CLASS_SEQ = 0

# 皮肤选择窗口：白底 / 粉边 / 紫字 / 金选中，无阴影、无渐变、无高光
_UI_WHITE = (255, 255, 255)
_UI_PINK = (255, 105, 180)       # #ff69b4
_UI_PURPLE = (138, 43, 226)      # #8a2be2
_UI_GOLD = (255, 215, 0)         # #ffd700
_UI_GOLD_FILL = (255, 232, 163)  # #ffe8a3
_UI_MUTED = (156, 130, 176)      # 次要文字（占位卡提示）
_UI_DISABLED = (176, 176, 180)   # 禁用卡灰边
_DISABLED_CONTENT_ALPHA = 0.45   # 禁用卡内容整体透明度

_PICKER_COLS = 3
_PICKER_CARD_W = 156
_PICKER_CARD_H = 150
_PICKER_GAP = 14
_PICKER_PAD = 22
_PICKER_TITLE_H = 46
_PICKER_THUMB = 80
_PICKER_CARD_RADIUS = 10
_PICKER_WIN_RADIUS = 16

_UI_TEXT = (64, 64, 70)          # 只读正文（中性深灰，避免整段紫色）

# 会话存储：宿主写在 .simchat/data/sessions/<sid>.json，与 GET /api/sessions 同一份数据
_SIMCHAT_DIR = os.path.dirname(os.path.dirname(_PACKAGE_DIR))  # .simchat/
_SESSIONS_DIR = os.path.join(_SIMCHAT_DIR, "data", "sessions")

# Kirara 的唯一会话：由宿主 /api/mods/chat-cards/kirara/ensure 以固定 id 创建，
# origin 标记归属、is_deleteable=false。桌宠端只读写这一段会话。
_KIRARA_MOD_ID = "kirara"
_KIRARA_SESSION_ID = "mod-kirara"

# 桌宠 chat 面板尺寸与节奏（设备无关像素）
_CHAT_WIDTH = 380
_CHAT_HEIGHT = 500
_CHAT_INPUT_H = 40
_CHAT_SEND_W = 54
_CHAT_MSG_GAP = 9
_CHAT_MSGS = 8
_CHAT_LINES_PER_MSG = 3
_CHAT_POLL_MS = 2000
_CHAT_TIMER_ID = 1
_CHAT_CARD_RADIUS = 10
_CHAT_ASYNC_MSG = win32con.WM_APP + 21

_THUMB_CACHE = {}

_BASE_HEIGHT = 480          # 立绘基准高度（设备无关像素）
_BTN_DIAMETER = 56          # 与 web/index.html 的 .orb-btn 一致
_BTN_RENDER_RADIUS = 60.0   # 按钮预渲染半径（px）

# 八个按钮：左上角起、逆时针排列。角度为屏幕坐标系（0°=右，顺时针为正）
_RING_ANGLES = (225, 180, 135, 90, 45, 0, -45, -90)
# 贾维斯环：立绘矩形的外接圆，按钮像珠子穿在环上
_RING_STROKE = 10.0            # 环线宽（逻辑像素）
_RING_COLOR = (253, 236, 166)  # #FDECA6
_RING_GLOW_BLUR = 11.0         # 弥散辉光的高斯模糊半径（逻辑像素）
_RING_SUPERSAMPLE = 4          # 环主体超采样倍数，保证 10px 细环不锯齿、不断裂
_BTN_SPECS = (
    ("voice", "语音", (74, 171, 214), (52, 150, 196)),
    ("prompt", "提示词", (86, 120, 220), (64, 98, 202)),
    ("live", "Go Live", (236, 92, 122), (222, 66, 100)),
    ("plugin", "插件", (150, 204, 92), (128, 188, 68)),
    ("settings", "设置", (112, 120, 134), (96, 104, 118)),
    ("exit", "退出", (214, 74, 74), (196, 50, 50)),
    ("context", "上下文", (166, 118, 226), (148, 96, 212)),
    ("outfit", "服装", (246, 154, 78), (236, 132, 52)),
)
_LINES = (
    "欢迎回来。今天想听点星屑级的小知识吗？",
    "唔……你刚才戳到我的光环了。不过，没关系。",
    "占卜结果：你今天会喝到一杯温度刚好的水。",
    "这颗星说别熬夜了。是它说的，不是我说的。",
    "房间的温度我已经记住了，下次直接问我。",
    "无聊的话，把我拖到屏幕角落就好——我不会乱跑的。",
)

_TIMER_ANIM = 1
_TIMER_BUBBLE = 2
_ANIM_FRAME_MS = 16
_ANIM_OPEN_S = 0.62
_ANIM_CLOSE_S = 0.38
_WM_MOUSELEAVE = 0x02A3
_TME_LEAVE = 0x00000002

# ---- 系统原生 tooltip（tooltips_class32）----
_TTS_ALWAYSTIP = 0x01
_TTS_NOPREFIX = 0x02
_TTF_SUBCLASS = 0x0010   # 由 tooltip 控件自己接管鼠标跟踪、悬停计时与显隐
_TTM_SETMAXTIPWIDTH = 0x0400 + 24
_TTM_ADDTOOLW = 0x0400 + 50
_TIP_MAX_WIDTH = 420  # 超长说明自动换行

_FONT_CANDIDATES = (
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
)
_FONT_CACHE = {}

# ---- gdi32 / user32 声明（UpdateLayeredWindow 只有 ctypes 这条路）----


class _BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_ubyte),
        ("BlendFlags", ctypes.c_ubyte),
        ("SourceConstantAlpha", ctypes.c_ubyte),
        ("AlphaFormat", ctypes.c_ubyte),
    ]


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.c_uint32),
        ("biWidth", ctypes.c_int32),
        ("biHeight", ctypes.c_int32),
        ("biPlanes", ctypes.c_uint16),
        ("biBitCount", ctypes.c_uint16),
        ("biCompression", ctypes.c_uint32),
        ("biSizeImage", ctypes.c_uint32),
        ("biXPelsPerMeter", ctypes.c_int32),
        ("biYPelsPerMeter", ctypes.c_int32),
        ("biClrUsed", ctypes.c_uint32),
        ("biClrImportant", ctypes.c_uint32),
    ]


class _BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", _BITMAPINFOHEADER), ("bmiColors", ctypes.c_uint32 * 3)]


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class _TRACKMOUSEEVENT(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint32),
        ("dwFlags", ctypes.c_uint32),
        ("hwndTrack", ctypes.c_void_p),
        ("dwHoverTime", ctypes.c_uint32),
    ]


class _TOOLINFO(ctypes.Structure):
    """comctl32 TOOLINFO（x64 下 cbSize=72）；lpReserved 是 6.x 的保留字段。"""

    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("uFlags", ctypes.c_uint),
        ("hwnd", ctypes.c_void_p),
        ("uId", ctypes.c_size_t),
        ("rect", _RECT),
        ("hinst", ctypes.c_void_p),
        ("lpszText", ctypes.c_wchar_p),
        ("lParam", ctypes.c_ssize_t),
        ("lpReserved", ctypes.c_void_p),
    ]


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _COMPOSITIONFORM(ctypes.Structure):
    """IME 组合窗口定位（imm32!COMPOSITIONFORM）。"""

    _fields_ = [
        ("dwStyle", ctypes.c_ulong),
        ("ptCurrentPos", _POINT),
        ("rcArea", _RECT),
    ]


class _CANDIDATEFORM(ctypes.Structure):
    """IME 候选窗定位（imm32!CANDIDATEFORM）。"""

    _fields_ = [
        ("dwIndex", ctypes.c_ulong),
        ("dwStyle", ctypes.c_ulong),
        ("ptCurrentPos", _POINT),
        ("rcArea", _RECT),
    ]


_gdi32 = ctypes.windll.gdi32
_user32 = ctypes.windll.user32
_gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
_gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
_gdi32.CreateDIBSection.restype = ctypes.c_void_p
_gdi32.CreateDIBSection.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(_BITMAPINFO),
    ctypes.c_uint,
    ctypes.POINTER(ctypes.c_void_p),
    ctypes.c_void_p,
    ctypes.c_uint32,
]
_gdi32.SelectObject.restype = ctypes.c_void_p
_gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
_gdi32.DeleteDC.argtypes = [ctypes.c_void_p]
_gdi32.GetDeviceCaps.argtypes = [ctypes.c_void_p, ctypes.c_int]
_gdi32.GetDeviceCaps.restype = ctypes.c_int
_user32.GetDC.restype = ctypes.c_void_p
_user32.GetDC.argtypes = [ctypes.c_void_p]
_user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_user32.UpdateLayeredWindow.argtypes = [
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_int),
    ctypes.POINTER(ctypes.c_int),
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_int),
    ctypes.c_uint32,
    ctypes.POINTER(_BLENDFUNCTION),
    ctypes.c_uint32,
]
_user32.SetTimer.restype = ctypes.c_void_p
_user32.SetTimer.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p]
_user32.KillTimer.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_user32.KillTimer.restype = ctypes.c_int
_user32.CreateWindowExW.restype = ctypes.c_void_p
_user32.CreateWindowExW.argtypes = [
    ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
]
_user32.SendMessageW.restype = ctypes.c_ssize_t
_user32.SendMessageW.argtypes = [
    ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t,
]

# ---- imm32：自绘输入框的中文输入（组合串 + 候选框定位）----
_WM_IME_STARTCOMPOSITION = 0x010D
_WM_IME_ENDCOMPOSITION = 0x010E
_WM_IME_COMPOSITION = 0x010F
_GCS_COMPSTR = 0x0008
_GCS_RESULTSTR = 0x0800
_CFS_POINT = 0x0002
_CFS_CANDIDATEPOS = 0x0040
_NI_COMPOSITIONSTR = 0x0015
_CPS_CANCEL = 0x0004

_imm32 = ctypes.windll.imm32
_imm32.ImmGetContext.restype = ctypes.c_void_p
_imm32.ImmGetContext.argtypes = [ctypes.c_void_p]
_imm32.ImmReleaseContext.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_imm32.ImmGetCompositionStringW.restype = ctypes.c_long
_imm32.ImmGetCompositionStringW.argtypes = [
    ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint,
]
_imm32.ImmSetCompositionWindow.argtypes = [
    ctypes.c_void_p, ctypes.POINTER(_COMPOSITIONFORM),
]
_imm32.ImmSetCandidateWindow.argtypes = [
    ctypes.c_void_p, ctypes.POINTER(_CANDIDATEFORM),
]
_imm32.ImmNotifyIME.argtypes = [
    ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint,
]


def enable_dpi_awareness():
    """声明 DPI 感知；否则分层位图会被系统按缩放比例拉伸变糊。"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _dpi_scale():
    hdc = _user32.GetDC(None)
    try:
        dpi = _gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
    finally:
        _user32.ReleaseDC(None, hdc)
    return (dpi / 96.0) if dpi else 1.0


def _work_area():
    """主屏工作区（排除任务栏）。"""
    rect = _RECT()
    if _user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
        return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
    return 0, 0, 1280, 800


def _load_sprite_image(path, target_height):
    """读 PNG → 预乘 alpha 缩放 → 普通 RGBA（便于整幅画布合成）。"""
    image = Image.open(path).convert("RGBa")  # RGBa = 预乘 alpha，缩放不会产生白边/黑边
    ratio = float(target_height) / image.height
    width = max(1, int(round(image.width * ratio)))
    return image.resize((width, target_height), Image.LANCZOS).convert("RGBA")


def _premultiply(image):
    """RGBA 画布 → 预乘 BGRA 字节 + alpha 表。"""
    r, g, b, a = image.split()
    premultiplied = Image.merge(
        "RGBA",
        (
            ImageChops.multiply(r, a),
            ImageChops.multiply(g, a),
            ImageChops.multiply(b, a),
            a,
        ),
    )
    return premultiplied.tobytes("raw", "BGRA"), a.tobytes()


def _paint_layered(hwnd, data, width, height):
    """把预乘 BGRA 位图交给 UpdateLayeredWindow（ULW_ALPHA）。桌宠与皮肤窗口共用。"""
    screen_dc = _user32.GetDC(None)
    mem_dc = _gdi32.CreateCompatibleDC(screen_dc)
    bmi = _BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = width
    bmi.bmiHeader.biHeight = -height  # 负数 = 自上而下
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = 0  # BI_RGB

    bits = ctypes.c_void_p()
    dib = _gdi32.CreateDIBSection(
        mem_dc, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0
    )
    ctypes.memmove(bits, data, len(data))
    old = _gdi32.SelectObject(mem_dc, dib)

    blend = _BLENDFUNCTION(0, 0, 255, 1)  # AC_SRC_OVER / AC_SRC_ALPHA
    size = (ctypes.c_int * 2)(width, height)
    src = (ctypes.c_int * 2)(0, 0)
    # pptDst 传 None：只换像素和尺寸，不挪动窗口位置
    _user32.UpdateLayeredWindow(
        hwnd,
        screen_dc,
        None,
        size,
        mem_dc,
        src,
        0,
        ctypes.byref(blend),
        2,  # ULW_ALPHA
    )
    _gdi32.SelectObject(mem_dc, old)
    _gdi32.DeleteObject(dib)
    _gdi32.DeleteDC(mem_dc)
    _user32.ReleaseDC(None, screen_dc)


def _font(size):
    size = max(8, int(round(size)))
    cached = _FONT_CACHE.get(size)
    if cached is not None:
        return cached
    font = None
    for path in _FONT_CANDIDATES:
        if os.path.isfile(path):
            try:
                font = ImageFont.truetype(path, size)
                break
            except OSError:
                font = None
    if font is None:
        font = ImageFont.load_default()
    _FONT_CACHE[size] = font
    return font


def _text_width(font, text):
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    return probe.textlength(text, font=font)


def _wrap_text(font, text, max_width):
    lines = []
    line = ""
    for char in text:
        if char == "\n":
            lines.append(line)
            line = ""
            continue
        if line and _text_width(font, line + char) > max_width:
            lines.append(line)
            line = char
        else:
            line += char
    if line:
        lines.append(line)
    return lines or [""]


def _clip_text(font, text, max_width):
    """单行截断：超宽时保留能放下的部分并补省略号。"""
    if _text_width(font, text) <= max_width:
        return text
    out = ""
    for char in text:
        if _text_width(font, out + char + "…") > max_width:
            break
        out += char
    return out + "…"


# ---- 会话存储（只读：不写盘、不新建、不删除） ----


def _load_session_detail(sid):
    """按 id 读取单个会话（含 messages）；id 只允许字母数字与 -_，防止路径穿越。"""
    if not isinstance(sid, str) or not sid:
        return None
    if any(not (char.isalnum() or char in "-_") for char in sid):
        return None
    try:
        with open(os.path.join(_SESSIONS_DIR, sid + ".json"), "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def _server_base_url():
    """从宿主登记的 lifecycle_server.json 取本机 Web 服务地址；读不到返回 None。"""
    path = os.path.join(_SIMCHAT_DIR, "data", "lifecycle_server.json")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        port = int(data.get("port"))
    except (OSError, ValueError, TypeError):
        return None
    if not 0 < port < 65536:
        return None
    host = str(data.get("host") or "").strip()
    if host in ("", "0.0.0.0", "::", "localhost", "::1"):
        host = "127.0.0.1"
    return "http://%s:%d" % (host, port)


def _http_error_message(body):
    """从宿主 JSON 错误响应里取可读文案；解析失败时退回原始文本。"""
    try:
        data = json.loads(body)
    except (TypeError, ValueError):
        return str(body or "").strip()[:200]
    if isinstance(data, dict):
        return str(data.get("error") or data.get("message") or "").strip()[:200]
    return ""


# ---- 皮肤发现与缩略图 ----


def discover_skins():
    """扫描 common/ 下真实存在的 kirara-*-default.png。

    返回 [(label, filename, path, enabled, description)]：默认立绘排首位，其余按文件名排序。
    只列举磁盘上有的文件，不按旧命名推断；显示名查 _SKIN_LABELS，查不到就用文件名推导。
    禁用名单里的文件仍然列出，但 enabled=False（卡片不可选）。
    description 取 _SKIN_DESCRIPTIONS 原文，没有对应条目就留空（不编）。
    """
    if not os.path.isdir(_COMMON_DIR):
        return []
    names = [
        name
        for name in os.listdir(_COMMON_DIR)
        if name.lower().startswith("kirara-") and name.lower().endswith("-default.png")
    ]
    default_name = os.path.basename(_DEFAULT_SPRITE)
    names.sort(key=lambda name: (name != default_name, name.lower()))
    skins = []
    for name in names:
        label = _SKIN_LABELS.get(name)
        if not label:
            stem = os.path.splitext(name)[0]
            label = stem.replace("kirara-", "").replace("-default", "")
        enabled = name not in _SKIN_DISABLED
        skins.append(
            (label, name, os.path.join(_COMMON_DIR, name), enabled,
             _SKIN_DESCRIPTIONS.get(name, ""))
        )
    return skins


def _skin_thumbnail(path, size):
    """把立绘顶部裁成圆形头像；读不到/损坏时返回 None，由调用方画占位卡。"""
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return None
    key = (path, mtime, size)
    cached = _THUMB_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        image = Image.open(path).convert("RGBA")
    except Exception:
        return None
    box = image.getbbox() or (0, 0, image.width, image.height)
    left, top, right, bottom = box
    box_w, box_h = right - left, bottom - top
    # 立绘是全身像：取 alpha 边界内、顶部居中的正方形，保证每张都能露到脸
    side = max(1, min(box_w, int(box_h * 0.46)))
    center_x = (left + right) // 2
    crop_top = top + int(box_h * 0.02)
    crop = image.crop(
        (center_x - side // 2, crop_top, center_x - side // 2 + side, crop_top + side)
    ).resize((size, size), Image.LANCZOS)

    # 圆形遮罩按 4 倍超采样，边缘不锯齿
    scale = 4
    mask = Image.new("L", (size * scale, size * scale), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size * scale - 1, size * scale - 1], fill=255)
    mask = mask.resize((size, size), Image.LANCZOS)
    circular = Image.new("RGBA", (size, size), (255, 255, 255, 255))
    circular.alpha_composite(crop)
    circular.putalpha(mask)
    _THUMB_CACHE[key] = circular
    return circular


# ---- 按钮绘制 ----


def _draw_icon(draw, key, cx, cy, radius, color):
    """在 24×24 的视图框里描出八个按钮的线稿图标。"""
    # 视觉尺寸统一：所有图标收在约 15×15 的 24 视图框内；线宽按半径等比，避免粗细不一
    scale = radius * 1.1 / 24.0
    width = max(2, int(round(radius * 0.068)))

    def pt(x, y):
        return (cx + (x - 12.0) * scale, cy + (y - 12.0) * scale)

    if key == "voice":
        # 麦克风：胶囊 + U 型支架 + 底座
        draw.rounded_rectangle(
            [pt(9.0, 5.0), pt(15.0, 12.8)],
            radius=int(3.0 * scale),
            outline=color,
            width=width,
        )
        draw.arc([pt(6.4, 8.2), pt(17.6, 19.4)], start=0, end=180,
                 fill=color, width=width)
        draw.line([pt(12, 19.4), pt(12, 20.8)], fill=color, width=width)
        draw.line([pt(9.2, 20.8), pt(14.8, 20.8)], fill=color, width=width)
    elif key == "prompt":
        # 终端提示符 + 光标
        draw.line([pt(4.8, 5.4), pt(11.4, 12.0), pt(4.8, 18.6)], fill=color,
                  width=width, joint="curve")
        draw.line([pt(13.2, 18.6), pt(19.6, 18.6)], fill=color, width=width)
    elif key == "live":
        # 直播：中心点 + 两侧信号弧
        draw.ellipse([pt(9.8, 9.8), pt(14.2, 14.2)], fill=color)
        draw.arc([pt(7.0, 7.0), pt(17.0, 17.0)], start=-55, end=55,
                 fill=color, width=width)
        draw.arc([pt(7.0, 7.0), pt(17.0, 17.0)], start=125, end=235,
                 fill=color, width=width)
        draw.arc([pt(4.4, 4.4), pt(19.6, 19.6)], start=-50, end=50,
                 fill=color, width=width)
        draw.arc([pt(4.4, 4.4), pt(19.6, 19.6)], start=130, end=230,
                 fill=color, width=width)
    elif key == "plugin":
        # 插件：2×2 模块方块（原拼图形状在 24px 下会糊成挂锁）
        for offset_x, offset_y in ((5.0, 5.0), (13.2, 5.0), (5.0, 13.2), (13.2, 13.2)):
            draw.rounded_rectangle(
                [pt(offset_x, offset_y), pt(offset_x + 5.8, offset_y + 5.8)],
                radius=int(1.4 * scale),
                outline=color,
                width=width,
            )
    elif key == "settings":
        # 齿轮：内圈 + 六根齿（八齿在 24px 下会糊成太阳）
        draw.ellipse([pt(7.8, 7.8), pt(16.2, 16.2)], outline=color, width=width)
        for step in range(6):
            angle = math.radians(step * 60)
            draw.line(
                [
                    pt(12 + math.cos(angle) * 3.9, 12 + math.sin(angle) * 3.9),
                    pt(12 + math.cos(angle) * 7.2, 12 + math.sin(angle) * 7.2),
                ],
                fill=color,
                width=width,
            )
    elif key == "exit":
        # 电源符号
        draw.arc([pt(5.2, 6.0), pt(18.8, 19.6)], start=300, end=240,
                 fill=color, width=width)
        draw.line([pt(12, 4.4), pt(12, 12.2)], fill=color, width=width)
    elif key == "context":
        # 上下文：叠放卡片
        draw.rounded_rectangle(
            [pt(5.0, 7.6), pt(19.0, 19.4)],
            radius=int(2.0 * scale),
            outline=color,
            width=width,
        )
        draw.line([pt(8.2, 11.2), pt(15.8, 11.2)], fill=color, width=width)
        draw.line([pt(8.2, 14.6), pt(13.4, 14.6)], fill=color, width=width)
        draw.line([pt(7.4, 4.6), pt(16.6, 4.6)], fill=color,
                  width=max(1, width - 1))
    elif key == "outfit":
        # T 恤
        shirt = [
            (8.2, 4.6), (4.4, 7.8), (6.6, 11.4), (8.2, 10.2),
            (8.2, 19.2), (15.8, 19.2), (15.8, 10.2), (17.4, 11.4),
            (19.6, 7.8), (15.8, 4.6), (13.8, 6.4), (12, 7.2),
            (10.2, 6.4),
        ]
        draw.line(
            [pt(x, y) for x, y in shirt] + [pt(*shirt[0])],
            fill=color,
            width=width,
            joint="curve",
        )


def _lighten(rgb, amount):
    """把颜色朝白色提亮一档（悬停态用，仍是纯色，不产生渐变）。"""
    return tuple(int(round(c + (255 - c) * amount)) for c in rgb[:3])


def _render_orb_button(key, tint, _glow, hovered):
    """预渲染一枚扁平圆钮：纯色填充 + 单色线性图标，无高光/阴影/发光/描边。"""
    radius = _BTN_RENDER_RADIUS
    size = int(round(radius * 2))
    center = size / 2.0
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    # 纯色圆盘；悬停只把填充提亮，不做发光/渐变/内阴影
    fill = _lighten(tint, 0.12) if hovered else tuple(tint[:3])
    ImageDraw.Draw(image).ellipse(
        [center - radius, center - radius, center + radius, center + radius],
        fill=fill + (255,),
    )

    # 图标：白色单色线，粗细与视觉尺寸由 _draw_icon 统一
    _draw_icon(ImageDraw.Draw(image), key, center, center, radius, (255, 255, 255, 255))
    return image


def _build_button_images():
    images = {}
    for key, _label, tint, glow in _BTN_SPECS:
        images[(key, False)] = _render_orb_button(key, tint, glow, False)
        images[(key, True)] = _render_orb_button(key, tint, glow, True)
    return images


class LayeredPet:
    """分层窗口桌宠；start() 在后台线程跑消息循环。"""

    def __init__(self, sprite_path=None, height=_BASE_HEIGHT):
        self.sprite_path = sprite_path or _DEFAULT_SPRITE
        self.height = height
        self.hwnd = None
        self._size = (0, 0)
        self._alpha = b""
        self._drag = None
        self._home = (0, 0)
        self._ready = threading.Event()

        self._dpi = 1.0
        self._skin_picker = None
        self._prompt_panel = None  # 兼容旧命名；实际是 Kirara 对话面板
        self._sprite_img = None
        self._sprite_alpha = b""
        self._metrics = None
        self._btn_r = _BTN_DIAMETER / 2.0
        self._button_images = {}
        self._ring_glow = None
        self._ring_body = None

        self._menu_open = False
        self._progress = 0.0
        self._anim_opening = True
        self._anim_base = 0.0
        self._anim_start = 0.0

        self._hover = None
        self._hotspots = []
        self._tracking_leave = False

        self._bubble_text = ""
        self._bubble_until = 0.0
        self._bubble_rect = None
        self._line_index = 0

    # ---- 对外 ----

    def is_alive(self):
        return bool(self.hwnd and win32gui.IsWindow(self.hwnd))

    def start(self):
        thread = threading.Thread(target=self._run, name="kirara-layered-pet", daemon=True)
        thread.start()
        self._ready.wait(10)
        return thread

    def close(self):
        if self.hwnd:
            win32gui.PostMessage(self.hwnd, win32con.WM_CLOSE, 0, 0)

    # ---- 内部 ----

    def _run(self):
        try:
            self._create()
        except Exception:
            import traceback

            traceback.print_exc()
            self._ready.set()
            return
        win32gui.PumpMessages()
        self.hwnd = None

    def _create(self):
        enable_dpi_awareness()
        self._dpi = _dpi_scale()
        self._btn_r = max(18.0, (_BTN_DIAMETER / 2.0) * self._dpi)
        self._button_images = _build_button_images()
        self._reload_sprite(initial=True)
        self._home = self._compute_home()
        x, y = self._home
        width, height = self._metrics["canvas_w"], self._metrics["canvas_h"]

        wc = win32gui.WNDCLASS()
        wc.hInstance = win32api.GetModuleHandle(None)
        wc.lpszClassName = _CLASS_NAME
        wc.hCursor = win32gui.LoadCursor(0, win32con.IDC_HAND)
        wc.lpfnWndProc = {
            win32con.WM_DESTROY: self._on_destroy,
            win32con.WM_LBUTTONDOWN: self._on_lbutton_down,
            win32con.WM_MOUSEMOVE: self._on_mouse_move,
            win32con.WM_LBUTTONUP: self._on_lbutton_up,
            win32con.WM_RBUTTONUP: self._on_rbutton_up,
            win32con.WM_NCHITTEST: self._on_hit_test,
            win32con.WM_CAPTURECHANGED: self._on_capture_changed,
            win32con.WM_TIMER: self._on_timer,
            _WM_MOUSELEAVE: self._on_mouse_leave,
        }
        win32gui.RegisterClass(wc)

        ex_style = win32con.WS_EX_LAYERED | win32con.WS_EX_TOPMOST | win32con.WS_EX_TOOLWINDOW
        self.hwnd = win32gui.CreateWindowEx(
            ex_style,
            _CLASS_NAME,
            "Kirara",
            win32con.WS_POPUP,
            x,
            y,
            width,
            height,
            0,
            0,
            wc.hInstance,
            None,
        )
        self._render()
        win32gui.ShowWindow(self.hwnd, win32con.SW_SHOWNOACTIVATE)
        win32gui.SetWindowPos(
            self.hwnd,
            win32con.HWND_TOPMOST,
            x,
            y,
            0,
            0,
            win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE,
        )
        print("[pet] 工作区=%s 目标位置=(%d,%d) 实际=%s"
              % (_work_area(), x, y, win32gui.GetWindowRect(self.hwnd)))
        self._ready.set()

    # ---- 精灵与几何 ----

    def _sprite_target_height(self):
        return max(1, int(round(self.height * self._dpi)))

    def _reload_sprite(self, initial=False):
        old_metrics = self._metrics
        path = self.sprite_path
        if not os.path.isfile(path):
            path = _DEFAULT_SPRITE
        image = _load_sprite_image(path, self._sprite_target_height())
        self._sprite_img = image
        self._sprite_alpha = image.getchannel("A").tobytes()
        self._metrics = self._compute_metrics()
        # 立绘尺寸变了，环的几何随之变化，预渲染图层作废
        self._ring_glow = None
        self._ring_body = None
        if not initial and self.hwnd:
            self._apply_geometry(old_metrics)

    def _compute_metrics(self):
        width, height = self._sprite_img.size
        d = self._dpi
        # 贾维斯环 = 立绘矩形的外接圆：半径取对角线的一半，立绘整个落在环内
        ring_radius = math.hypot(width, height) / 2.0
        stroke = _RING_STROKE * d
        # 窗口要同时容纳环本体、环辉光、以及穿在环上的按钮（按钮圆心在环上，外侧还要多半个直径）
        glow_extent = stroke * 1.5 + _RING_GLOW_BLUR * d * 3.0
        btn_extent = self._btn_r * 1.08
        ring_extent = ring_radius + stroke / 2.0 + max(glow_extent, btn_extent) + 6 * d
        margin_x = int(math.ceil(max(0.0, ring_extent - width / 2.0)))
        # 顶部/底部在环之外再留出气泡与悬浮标签的位置
        margin_top = int(math.ceil(max(128 * d, ring_extent - height / 2.0 + 24 * d)))
        margin_bottom = int(math.ceil(max(60 * d, ring_extent - height / 2.0)))
        canvas_w = width + margin_x * 2
        canvas_h = margin_top + height + margin_bottom
        center_x = margin_x + width / 2.0
        center_y = margin_top + height / 2.0
        return {
            "sprite_w": width,
            "sprite_h": height,
            "mx": margin_x,
            "mt": margin_top,
            "mb": margin_bottom,
            "canvas_w": canvas_w,
            "canvas_h": canvas_h,
            "cx": center_x,
            "cy": center_y,
            "ring_radius": ring_radius,
            "ring_stroke": stroke,
        }

    def _compute_home(self):
        work_x, work_y, work_w, work_h = _work_area()
        metric = self._metrics
        # 按整块画布（含按钮环与气泡留白）贴边，避免展开时按钮被屏幕边缘裁掉
        x = work_x + work_w - 12 - metric["canvas_w"]
        y = work_y + work_h - 20 - metric["canvas_h"]
        return (x, y)

    def _apply_geometry(self, old):
        """尺寸变化后保持立绘中心不动，同步窗口大小与归位点。"""
        rect = win32gui.GetWindowRect(self.hwnd)
        if not old:
            old = self._metrics
        old_center = (rect[0] + old["mx"] + old["sprite_w"] / 2.0,
                      rect[1] + old["mt"] + old["sprite_h"] / 2.0)
        metric = self._metrics
        x = int(round(old_center[0] - (metric["mx"] + metric["sprite_w"] / 2.0)))
        y = int(round(old_center[1] - (metric["mt"] + metric["sprite_h"] / 2.0)))
        win32gui.SetWindowPos(
            self.hwnd,
            win32con.HWND_TOPMOST,
            x,
            y,
            metric["canvas_w"],
            metric["canvas_h"],
            win32con.SWP_NOACTIVATE,
        )
        self._home = self._compute_home()
        self._hover = None
        self._render()

    def _compose(self):
        metric = self._metrics
        canvas = Image.new(
            "RGBA", (metric["canvas_w"], metric["canvas_h"]), (0, 0, 0, 0)
        )

        # 图层顺序（自下而上）：环辉光 → 环本体 → 立绘 → 按钮 → 预留圆弧层 → 气泡
        # 环与按钮分开绘制、分开合成；辉光只属于环，按钮保持扁平
        hotspots = []
        if self._progress > 0.001:
            self._draw_jarvis_ring(canvas, min(1.0, self._progress * 1.6))

        canvas.alpha_composite(self._sprite_img, (metric["mx"], metric["mt"]))

        if self._progress > 0.001:
            hotspots = self._draw_ring_buttons(canvas)

        # 预留：同心圆弧控件层。坐标基准统一取 self._ring_geometry()（同一圆心/半径），
        # 画在这里即可叠在按钮之下、气泡之上。

        now = time.perf_counter()
        if self._bubble_text and now < self._bubble_until:
            self._draw_bubble(canvas)

        self._hotspots = hotspots if self._progress > 0.9 else []
        return canvas

    def _render(self):
        if not self.hwnd:
            return
        canvas = self._compose()
        data, alpha = _premultiply(canvas)
        self._alpha = alpha
        self._size = canvas.size
        self._paint(data, canvas.size[0], canvas.size[1])

    def _paint(self, data, width, height):
        _paint_layered(self.hwnd, data, width, height)

    # ---- 圆形按钮阵列 ----

    def _ring_geometry(self):
        """贾维斯环的坐标基准；后续同心圆弧控件共用这里的圆心与半径。"""
        metric = self._metrics
        return {
            "cx": metric["cx"],
            "cy": metric["cy"],
            "radius": metric["ring_radius"],
            "stroke": metric["ring_stroke"],
        }

    def _build_ring_layers(self):
        """预渲染「环辉光」与「环本体」两张全画布图层；几何不变时只做透明度变化。"""
        metric = self._metrics
        geo = self._ring_geometry()
        size = (metric["canvas_w"], metric["canvas_h"])
        radius, stroke = geo["radius"], geo["stroke"]

        # 环本体：先按 4 倍超采样画圆环遮罩，再缩回原尺寸，10px 细环也不会锯齿或断裂
        scale = _RING_SUPERSAMPLE
        big_size = (size[0] * scale, size[1] * scale)
        mask = Image.new("L", big_size, 0)
        mask_draw = ImageDraw.Draw(mask)
        bx, by = geo["cx"] * scale, geo["cy"] * scale
        outer = (radius + stroke / 2.0) * scale
        inner = (radius - stroke / 2.0) * scale
        mask_draw.ellipse([bx - outer, by - outer, bx + outer, by + outer], fill=255)
        mask_draw.ellipse([bx - inner, by - inner, bx + inner, by + inner], fill=0)
        body = Image.new("RGBA", size, _RING_COLOR + (255,))
        body.putalpha(mask.resize(size, Image.LANCZOS))

        # 环辉光：以 10px 环为基准叠两层模糊（紧光 + 弥散光），
        # 只做柔和的halo，不能糊成一圈粗带，否则「细环串珠」的形态会被吃掉
        glow_mask = Image.new("L", size, 0)
        glow_draw = ImageDraw.Draw(glow_mask)
        glow_outer = radius + stroke / 2.0
        glow_inner = radius - stroke / 2.0
        glow_draw.ellipse(
            [geo["cx"] - glow_outer, geo["cy"] - glow_outer,
             geo["cx"] + glow_outer, geo["cy"] + glow_outer],
            fill=255,
        )
        glow_draw.ellipse(
            [geo["cx"] - glow_inner, geo["cy"] - glow_inner,
             geo["cx"] + glow_inner, geo["cy"] + glow_inner],
            fill=0,
        )
        tight = glow_mask.filter(
            ImageFilter.GaussianBlur(3.0 * self._dpi)
        ).point(lambda value: int(value * 0.55))
        wide = glow_mask.filter(
            ImageFilter.GaussianBlur(11.0 * self._dpi)
        ).point(lambda value: int(value * 0.45))
        glow = Image.new("RGBA", size, _RING_COLOR + (255,))
        glow.putalpha(ImageChops.add(tight, wide))
        return glow, body

    def _draw_jarvis_ring(self, canvas, alpha):
        if self._ring_glow is None or self._ring_body is None:
            self._ring_glow, self._ring_body = self._build_ring_layers()

        if alpha >= 0.999:
            canvas.alpha_composite(self._ring_glow)
            canvas.alpha_composite(self._ring_body)
            return

        # 256 项查找表比逐像素 lambda 快得多，动画期每帧只改透明度
        table = bytes(int(value * alpha) for value in range(256))
        for layer in (self._ring_glow, self._ring_body):
            faded = layer.copy()
            faded.putalpha(layer.getchannel("A").point(table))
            canvas.alpha_composite(faded)

    def _button_progress(self, index, progress):
        if self._anim_opening:
            local = (progress - index * 0.05) / 0.72
        else:
            local = (progress - (len(_BTN_SPECS) - 1 - index) * 0.02) / 0.9
        local = max(0.0, min(1.0, local))
        return 1.0 - (1.0 - local) ** 3

    def _draw_ring_buttons(self, canvas):
        geo = self._ring_geometry()
        d = self._dpi
        hotspots = []
        order = [i for i in range(len(_BTN_SPECS)) if i != self._hover]
        if self._hover is not None:
            order.append(self._hover)

        for index in order:
            key, _label, _tint, _glow = _BTN_SPECS[index]
            eased = self._button_progress(index, self._progress)
            if eased <= 0.02:
                continue

            angle = math.radians(_RING_ANGLES[index] + (1.0 - eased) * -70.0)
            radius_factor = 0.25 + 0.75 * eased
            # 静止时圆心正好落在环上，展开过程中沿半径向外滑到环上
            cx = geo["cx"] + math.cos(angle) * geo["radius"] * radius_factor
            cy = geo["cy"] + math.sin(angle) * geo["radius"] * radius_factor

            hovered = self._hover == index
            scale = (0.3 + 0.7 * eased) * (1.08 if hovered else 1.0)
            radius = self._btn_r * scale
            sprite = self._button_images[(key, hovered)]
            disp = max(8, int(round(sprite.width * radius / _BTN_RENDER_RADIUS)))
            button = sprite.resize((disp, disp), Image.BILINEAR)
            if eased < 0.999:
                button.putalpha(button.getchannel("A").point(lambda v: int(v * eased)))
            canvas.alpha_composite(
                button, (int(round(cx - disp / 2.0)), int(round(cy - disp / 2.0)))
            )
            hotspots.append((index, key, cx, cy, max(radius, 14 * d)))

        if self._hover is not None and self._progress > 0.9:
            self._draw_hover_label(canvas, hotspots)

        return hotspots

    def _draw_hover_label(self, canvas, hotspots):
        if not hotspots:
            return
        # 悬停按钮被排到最后绘制，按稳定的 _BTN_SPECS 下标匹配，而不是列表位置
        for index, _key, cx, cy, radius in hotspots:
            if index != self._hover:
                continue
            label = _BTN_SPECS[index][1]
            d = self._dpi
            font = _font(10.5 * d)
            pad_x = 8 * d
            width = _text_width(font, label) + pad_x * 2
            height = 20 * d
            left = max(4.0, min(cx - width / 2.0, canvas.width - width - 4.0))
            top = max(4.0, min(cy + radius + 8 * d, canvas.height - height - 4.0))
            layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(layer)
            draw.rounded_rectangle(
                [left, top, left + width, top + height],
                radius=int(height / 2),
                fill=(12, 14, 22, 172),
            )
            draw.text(
                (left + pad_x, top + height / 2.0),
                label,
                font=font,
                fill=(255, 255, 255, 232),
                anchor="lm",
            )
            canvas.alpha_composite(layer)
            return

    # ---- 气泡 ----

    def _draw_bubble(self, canvas):
        metric = self._metrics
        d = self._dpi
        font = _font(12.5 * d)
        max_text_width = min(canvas.width - 24 * d, 250 * d)
        lines = _wrap_text(font, self._bubble_text, max_text_width)

        line_height = 17 * d
        pad_x, pad_y = 12 * d, 9 * d
        text_width = max(_text_width(font, line) for line in lines)
        width = min(canvas.width - 12, text_width + pad_x * 2 + 4)
        height = line_height * len(lines) + pad_y * 2
        center_x = metric["mx"] + metric["sprite_w"] / 2.0
        left = max(6.0, min(center_x - width / 2.0, canvas.width - width - 6.0))
        # 顶部正中是「服装」按钮，气泡整体上移，避免盖住按钮
        top = metric["mt"] - 68 * d - height - 8 * d
        if top < 4:
            top = 4.0
        # 记录气泡矩形，命中测试用它把气泡从透明区域里单独圈出来
        self._bubble_rect = (left, top, left + width, top + height + 9 * d)

        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        draw.rounded_rectangle(
            [left, top, left + width, top + height],
            radius=int(14 * d),
            fill=(20, 22, 36, 230),
            outline=(255, 255, 255, 54),
            width=max(1, int(round(d))),
        )
        tail_y = top + height - 2
        draw.polygon(
            [(center_x - 8 * d, tail_y), (center_x + 8 * d, tail_y), (center_x, tail_y + 9 * d)],
            fill=(20, 22, 36, 230),
        )
        text_y = top + pad_y
        for line in lines:
            draw.text((left + pad_x, text_y), line, font=font, fill=(245, 247, 255, 242))
            text_y += line_height
        canvas.alpha_composite(layer)

    def _show_bubble(self, text, seconds=4.5):
        self._bubble_text = text
        self._bubble_until = time.perf_counter() + seconds
        if self.hwnd:
            _user32.SetTimer(self.hwnd, _TIMER_BUBBLE, 250, None)
            self._render()

    def _show_line(self):
        self._show_bubble(_LINES[self._line_index])

    # ---- 展开 / 收起 ----

    def _toggle_menu(self):
        if not self.hwnd:
            return
        if not self._menu_open:
            self._menu_open = True
            self._anim_opening = True
            self._show_line()
        else:
            self._anim_opening = False
            self._hover = None
            self._bubble_text = ""
            _user32.KillTimer(self.hwnd, _TIMER_BUBBLE)
        self._anim_base = self._progress
        self._anim_start = time.perf_counter()
        _user32.SetTimer(self.hwnd, _TIMER_ANIM, _ANIM_FRAME_MS, None)

    def _on_timer(self, hwnd, msg, wparam, lparam):
        if wparam == _TIMER_ANIM:
            elapsed = time.perf_counter() - self._anim_start
            if self._anim_opening:
                progress = min(1.0, self._anim_base + elapsed / _ANIM_OPEN_S)
                done = progress >= 1.0
            else:
                progress = max(0.0, self._anim_base - elapsed / _ANIM_CLOSE_S)
                done = progress <= 0.0
            self._progress = progress
            if done:
                _user32.KillTimer(hwnd, _TIMER_ANIM)
                if not self._anim_opening:
                    self._menu_open = False
                    self._hover = None
            self._render()
        elif wparam == _TIMER_BUBBLE:
            if time.perf_counter() >= self._bubble_until:
                self._bubble_text = ""
                _user32.KillTimer(hwnd, _TIMER_BUBBLE)
            self._render()
        return 0

    # ---- 按钮动作 ----

    def _activate(self, key):
        if key == "voice":
            self._show_bubble("语音输入尚未接入。", 2.4)
        elif key == "prompt":
            self._open_prompt_panel()
        elif key == "live":
            self._show_bubble("Go Live 尚未接入。", 2.4)
        elif key == "plugin":
            self._show_bubble("插件面板尚未接入。", 2.4)
        elif key == "settings":
            self._show_bubble("设置面板尚未接入。", 2.4)
        elif key == "context":
            self._show_bubble("上下文面板尚未接入。", 2.4)
        elif key == "outfit":
            self._open_skin_picker()
        elif key == "exit":
            win32gui.DestroyWindow(self.hwnd)

    def _open_skin_picker(self):
        """「服装」珠子：打开独立的皮肤选择窗口（同线程，泵在主窗口的消息循环里）。"""
        if self._skin_picker is not None and self._skin_picker.hwnd:
            self._skin_picker.bring_to_front()
            return
        skins = discover_skins()
        if not skins:
            self._show_bubble("没有找到皮肤文件：" + _COMMON_DIR, 3.2)
            return
        self._skin_picker = SkinPickerWindow(self, self._dpi, skins)
        self._skin_picker.show()

    def _close_skin_picker(self):
        if self._skin_picker is not None and self._skin_picker.hwnd:
            self._skin_picker.close()

    def _open_prompt_panel(self):
        """「提示词」珠子：Kirara 专属对话面板（与网页端共用同一段会话）。"""
        if self._prompt_panel is not None and self._prompt_panel.hwnd:
            self._prompt_panel.reload()
            self._prompt_panel.bring_to_front()
            return
        self._prompt_panel = ChatPanel(self, self._dpi)
        self._prompt_panel.show()

    def _close_prompt_panel(self):
        if self._prompt_panel is not None and self._prompt_panel.hwnd:
            self._prompt_panel.close()

    def apply_skin(self, label, filename):
        """切换皮肤；禁用、缺失或损坏时保持原皮肤并给出提示。"""
        if filename in _SKIN_DISABLED:
            self._show_bubble("该皮肤尚未完成：" + label, 2.6)
            return False
        path = os.path.join(_COMMON_DIR, filename)
        if not os.path.isfile(path):
            self._show_bubble("皮肤文件缺失：" + label, 2.8)
            return False
        old_path = self.sprite_path
        self.sprite_path = path
        try:
            self._reload_sprite()
        except Exception:
            self.sprite_path = old_path
            self._reload_sprite()
            self._show_bubble("皮肤加载失败：" + label, 2.8)
            return False
        self._show_bubble("服装：" + label, 2.0)
        return True

    def _go_home(self):
        win32gui.SetWindowPos(
            self.hwnd,
            win32con.HWND_TOPMOST,
            self._home[0],
            self._home[1],
            0,
            0,
            win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE,
        )

    # ---- 命中与输入 ----

    def _sprite_hit(self, local_x, local_y):
        metric = self._metrics
        x = int(local_x) - metric["mx"]
        y = int(local_y) - metric["mt"]
        if 0 <= x < metric["sprite_w"] and 0 <= y < metric["sprite_h"]:
            return self._sprite_alpha[y * metric["sprite_w"] + x] > 8
        return False

    def _button_at(self, local_x, local_y):
        # 热点元组携带稳定的 _BTN_SPECS 下标；绘制顺序（悬停重排）不影响激活结果
        for index, _key, cx, cy, radius in self._hotspots:
            if (local_x - cx) ** 2 + (local_y - cy) ** 2 <= radius ** 2:
                return index
        return None

    def _on_destroy(self, hwnd, msg, wparam, lparam):
        self._close_skin_picker()
        self._close_prompt_panel()
        self.hwnd = None
        win32gui.PostQuitMessage(0)
        return 0

    def _on_lbutton_down(self, hwnd, msg, wparam, lparam):
        x, y = win32gui.GetCursorPos()
        rect = win32gui.GetWindowRect(hwnd)
        # (起点x, 起点y, 窗口x, 窗口y, 是否拖动过)
        self._drag = (x, y, rect[0], rect[1], False)
        win32gui.SetCapture(hwnd)
        return 0

    def _on_mouse_move(self, hwnd, msg, wparam, lparam):
        if self._drag:
            x, y = win32gui.GetCursorPos()
            start_x, start_y, win_x, win_y, moved = self._drag
            dx, dy = x - start_x, y - start_y
            if not moved and abs(dx) + abs(dy) > 3:
                moved = True
            self._drag = (start_x, start_y, win_x, win_y, moved)
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOPMOST,
                win_x + dx,
                win_y + dy,
                0,
                0,
                win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE,
            )
            return 0

        if not self._menu_open or self._progress < 0.9:
            return 0
        x, y = win32gui.GetCursorPos()
        local_x, local_y = win32gui.ScreenToClient(hwnd, (x, y))
        hovered = self._button_at(local_x, local_y)
        if hovered != self._hover:
            self._hover = hovered
            self._render()
        if hovered is not None and not self._tracking_leave:
            track = _TRACKMOUSEEVENT(
                ctypes.sizeof(_TRACKMOUSEEVENT), _TME_LEAVE, hwnd, 0
            )
            _user32.TrackMouseEvent(ctypes.byref(track))
            self._tracking_leave = True
        return 0

    def _on_mouse_leave(self, hwnd, msg, wparam, lparam):
        self._tracking_leave = False
        if self._hover is not None:
            self._hover = None
            self._render()
        return 0

    def _on_lbutton_up(self, hwnd, msg, wparam, lparam):
        drag = self._drag
        self._drag = None
        win32gui.ReleaseCapture()
        if not drag or drag[4]:
            return 0
        x, y = win32gui.GetCursorPos()
        local_x, local_y = win32gui.ScreenToClient(hwnd, (x, y))
        index = self._button_at(local_x, local_y)
        if index is not None:
            self._activate(_BTN_SPECS[index][0])
            return 0
        if self._sprite_hit(local_x, local_y):
            self._toggle_menu()
        return 0

    def _on_capture_changed(self, hwnd, msg, wparam, lparam):
        self._drag = None
        return 0

    def _in_ring_core(self, local_x, local_y):
        """到环心的距离落在 10px 环芯带内才算命中；环外侧由参数决定，辉光不参与。"""
        geo = self._ring_geometry()
        distance = math.hypot(local_x - geo["cx"], local_y - geo["cy"])
        return abs(distance - geo["radius"]) <= geo["stroke"] / 2.0

    def _on_hit_test(self, hwnd, msg, wparam, lparam):
        """按几何判定命中：气泡 / 珠子 / 立绘像素 / 10px 环芯；辉光层完全排除。

        不用 alpha 阈值是因为辉光是渐隐的，阈值调到哪都会留一圈「有时能点、
        有时不能点」的模糊带；这里改成算距离，辉光的像素从头到尾不参与判断。
        """
        x = ctypes.c_short(lparam & 0xFFFF).value
        y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
        client_x, client_y = win32gui.ScreenToClient(hwnd, (x, y))
        width, height = self._size
        if not (0 <= client_x < width and 0 <= client_y < height):
            return win32con.HTTRANSPARENT

        local_x, local_y = float(client_x), float(client_y)

        # 1. 气泡：只在自己绘制时的矩形里按像素 alpha 判断（圆角处自然让开）
        rect = self._bubble_rect
        if (
            self._bubble_text
            and time.perf_counter() < self._bubble_until
            and rect is not None
            and rect[0] <= local_x <= rect[2]
            and rect[1] <= local_y <= rect[3]
            and self._alpha[client_y * width + client_x] > 8
        ):
            return win32con.HTCLIENT

        # 2. 珠子：与点击判定共用 _hotspots 的圆
        if self._button_at(local_x, local_y) is not None:
            return win32con.HTCLIENT

        # 3. 立绘：矩形内不透明像素
        if self._sprite_hit(local_x, local_y):
            return win32con.HTCLIENT

        # 4. 环芯：收起状态下环不画出来，也不占命中
        if self._progress > 0.001 and self._in_ring_core(local_x, local_y):
            return win32con.HTCLIENT

        return win32con.HTTRANSPARENT

    def _on_rbutton_up(self, hwnd, msg, wparam, lparam):
        menu = win32gui.CreatePopupMenu()
        win32gui.AppendMenu(menu, win32con.MF_STRING, 1, "归位")
        win32gui.AppendMenu(menu, win32con.MF_STRING, 2, "退出桌宠")
        x, y = win32gui.GetCursorPos()
        win32gui.SetForegroundWindow(hwnd)
        command = win32gui.TrackPopupMenu(
            menu,
            win32con.TPM_RETURNCMD | win32con.TPM_RIGHTBUTTON,
            x,
            y,
            0,
            hwnd,
            None,
        )
        win32gui.PostMessage(hwnd, win32con.WM_NULL, 0, 0)
        win32gui.DestroyMenu(menu)
        if command == 1:
            self._go_home()
        elif command == 2:
            win32gui.DestroyWindow(hwnd)
        return 0


class PopupWindow:
    """可复用的顶层分层弹窗容器（皮肤选择等面板共用的外壳）。

    公共部分：位置与尺寸、圆角白底粉边、标题与关闭按钮、拖动、Esc 关闭、
    透明像素穿透、owned window 归属（始终在桌宠之上）、命中测试隔离、原生 tooltip。
    内容页只负责自己的布局与绘制，按需实现命中/点击/说明。

    内容页钩子：
        _content_layout()           计算 self._size 与内容矩形（必须实现）
        _draw_content(canvas, draw) 在公共外壳之上画内容
        _content_hit(x, y)          返回命中目标（close 由容器处理）
        _content_click(target)      处理内容命中
        _tooltip_specs()            返回 [(rect, text)] 供原生 tooltip 挂载
    """

    PANEL_RADIUS = _PICKER_WIN_RADIUS
    PAD = _PICKER_PAD
    TITLE_H = _PICKER_TITLE_H
    TITLE = ""
    HINT = "Esc 或 × 关闭"
    WINDOW_TITLE = "Kirara"
    CURSOR = win32con.IDC_ARROW

    def __init__(self, owner, dpi):
        self.owner = owner
        self._dpi = dpi
        self.hwnd = None
        self._size = (0, 0)
        self._alpha = b""
        self._drag = None
        self._hover = None
        self._tracking_leave = False
        self._pad = int(round(self.PAD * dpi))
        self._title_h = int(round(self.TITLE_H * dpi))
        self._close_rect = (0, 0, 0, 0)
        # 原生 tooltip：控件自己接管悬停跟踪，这里只保留 tool 结构体防止被 GC
        self._tip_hwnd = None
        self._tip_tools = []
        self._content_layout()
        self._layout_close()

    # ---- 内容页钩子 ----

    def _content_layout(self):
        raise NotImplementedError

    def _draw_content(self, canvas, draw):
        pass

    def _content_hit(self, local_x, local_y):
        return None

    def _content_click(self, target):
        return None

    def _tooltip_specs(self):
        return []

    # ---- 键盘 / 输入法 / 异步刷新钩子（默认不消费，内容页按需覆盖） ----

    def _content_key(self, wparam):
        return False

    def _content_char(self, wparam):
        return False

    def _content_ime(self, msg, wparam, lparam):
        return False

    def _content_timer(self, wparam):
        return False

    def _content_async(self):
        return False

    # ---- 公共布局 ----

    def _layout_close(self):
        width, _height = self._size
        d = self._dpi
        close_d = int(round(26 * d))
        close_cx = width - self._pad - close_d // 2
        close_cy = self._pad + self._title_h // 2
        self._close_rect = (
            close_cx - close_d // 2,
            close_cy - close_d // 2,
            close_cx + close_d // 2,
            close_cy + close_d // 2,
        )

    # ---- 公共绘制 ----

    def _compose(self):
        width, height = self._size
        d = self._dpi
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)

        # 窗口底板：纯白 + 粉边，圆角 16；角外保持全透明
        draw.rounded_rectangle(
            [0, 0, width - 1, height - 1],
            radius=int(round(self.PANEL_RADIUS * d)),
            fill=_UI_WHITE + (255,),
            outline=_UI_PINK + (255,),
            width=max(2, int(round(2 * d))),
        )

        title_cy = self._pad + self._title_h // 2
        draw.text(
            (self._pad, title_cy),
            self.TITLE,
            font=_font(18 * d),
            fill=_UI_PURPLE + (255,),
            anchor="lm",
        )
        draw.text(
            (self._close_rect[0] - 12 * d, title_cy),
            self.HINT,
            font=_font(10.5 * d),
            fill=_UI_MUTED + (255,),
            anchor="rm",
        )

        # 关闭按钮：白底粉边圆，悬停转金
        close_hover = self._hover == "close"
        draw.ellipse(
            self._close_rect,
            fill=(_UI_GOLD_FILL if close_hover else _UI_WHITE) + (255,),
            outline=(_UI_GOLD if close_hover else _UI_PINK) + (255,),
            width=max(2, int(round(2 * d))),
        )
        cl, ct, cr, cb = self._close_rect
        ccx, ccy = (cl + cr) / 2.0, (ct + cb) / 2.0
        arm = (cr - cl) * 0.22
        cross_w = max(2, int(round(2 * d)))
        draw.line(
            [(ccx - arm, ccy - arm), (ccx + arm, ccy + arm)],
            fill=_UI_PURPLE + (255,),
            width=cross_w,
        )
        draw.line(
            [(ccx - arm, ccy + arm), (ccx + arm, ccy - arm)],
            fill=_UI_PURPLE + (255,),
            width=cross_w,
        )

        self._draw_content(canvas, draw)
        return canvas

    def _render(self):
        if not self.hwnd:
            return
        canvas = self._compose()
        data, alpha = _premultiply(canvas)
        self._alpha = alpha
        self._size = canvas.size
        _paint_layered(self.hwnd, data, canvas.size[0], canvas.size[1])

    # ---- 公共窗口管理 ----

    def show(self):
        if self.hwnd:
            self.bring_to_front()
            return
        self._create()

    def bring_to_front(self):
        if not self.hwnd:
            return
        win32gui.SetWindowPos(
            self.hwnd,
            win32con.HWND_TOPMOST,
            0,
            0,
            0,
            0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW,
        )
        try:
            win32gui.SetForegroundWindow(self.hwnd)
        except win32gui.error:
            pass  # 前台锁定时拿不到焦点，窗口仍然置顶可点

    def close(self):
        if self.hwnd:
            win32gui.DestroyWindow(self.hwnd)

    def _create(self):
        # 类名后缀用递增序号：重开窗口时不会因 id 复用撞上已注册的类（1410）
        global _POPUP_CLASS_SEQ
        _POPUP_CLASS_SEQ += 1
        class_name = "%s%d" % (_POPUP_CLASS_NAME, _POPUP_CLASS_SEQ)
        wc = win32gui.WNDCLASS()
        wc.hInstance = win32api.GetModuleHandle(None)
        wc.lpszClassName = class_name
        wc.hCursor = win32gui.LoadCursor(0, self.CURSOR)
        wc.lpfnWndProc = {
            win32con.WM_DESTROY: self._on_destroy,
            win32con.WM_LBUTTONDOWN: self._on_lbutton_down,
            win32con.WM_MOUSEMOVE: self._on_mouse_move,
            win32con.WM_LBUTTONUP: self._on_lbutton_up,
            win32con.WM_NCHITTEST: self._on_hit_test,
            win32con.WM_CAPTURECHANGED: self._on_capture_changed,
            win32con.WM_KEYDOWN: self._on_key_down,
            win32con.WM_CHAR: self._on_char,
            win32con.WM_TIMER: self._on_timer,
            _WM_MOUSELEAVE: self._on_mouse_leave,
            _WM_IME_STARTCOMPOSITION: self._on_ime,
            _WM_IME_COMPOSITION: self._on_ime,
            _WM_IME_ENDCOMPOSITION: self._on_ime,
            _CHAT_ASYNC_MSG: self._on_async,
        }
        win32gui.RegisterClass(wc)

        width, height = self._size
        work_x, work_y, work_w, work_h = _work_area()
        x = work_x + max(0, (work_w - width) // 2)
        y = work_y + max(0, (work_h - height) // 2)
        ex_style = win32con.WS_EX_LAYERED | win32con.WS_EX_TOPMOST | win32con.WS_EX_TOOLWINDOW
        # 以桌宠窗口作为 owner：owned window 永远排在 owner 之上，
        # 桌宠被拖动/抬升（SetWindowPos HWND_TOPMOST）时也不会盖住弹窗、抢走内容点击。
        owner_hwnd = self.owner.hwnd if self.owner is not None and self.owner.hwnd else 0
        self.hwnd = win32gui.CreateWindowEx(
            ex_style,
            class_name,
            self.WINDOW_TITLE,
            win32con.WS_POPUP,
            x,
            y,
            width,
            height,
            owner_hwnd,
            0,
            wc.hInstance,
            None,
        )
        self._render()
        win32gui.ShowWindow(self.hwnd, win32con.SW_SHOW)
        self._create_tooltip(wc.hInstance)
        try:
            win32gui.SetForegroundWindow(self.hwnd)
        except win32gui.error:
            pass  # 前台锁定时拿不到焦点，窗口仍然置顶可点

    # ---- 公共交互 ----

    def _hit_target(self, local_x, local_y):
        cl, ct, cr, cb = self._close_rect
        if cl <= local_x <= cr and ct <= local_y <= cb:
            return "close"
        return self._content_hit(local_x, local_y)

    def _create_tooltip(self, hinst):
        """创建 comctl32 的 tooltips_class32；内容页通过 _tooltip_specs() 提供条目。

        显隐、悬停延迟全部交给系统 tooltip 控件自己处理（不移动/劫持鼠标，也不自绘）。
        """
        tip = _user32.CreateWindowExW(
            win32con.WS_EX_TOPMOST,
            "tooltips_class32",
            None,
            win32con.WS_POPUP | _TTS_ALWAYSTIP | _TTS_NOPREFIX,
            -32000, -32000, 10, 10,
            self.hwnd,
            None,
            hinst,
            None,
        )
        self._tip_hwnd = tip
        self._tip_tools = []
        if not tip:
            return
        _user32.SendMessageW(tip, _TTM_SETMAXTIPWIDTH, 0, _TIP_MAX_WIDTH)
        for rect, text in self._tooltip_specs():
            if not text:
                continue
            info = _TOOLINFO()
            info.cbSize = ctypes.sizeof(_TOOLINFO)
            info.uFlags = _TTF_SUBCLASS
            info.hwnd = self.hwnd
            info.uId = len(self._tip_tools) + 1  # 同一 hwnd 下用不同 uId 区分不同条目
            info.rect = _RECT(int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3]))
            info.hinst = hinst
            info.lpszText = text
            _user32.SendMessageW(tip, _TTM_ADDTOOLW, 0, ctypes.addressof(info))
            self._tip_tools.append(info)

    def refresh_tooltips(self):
        """内容页切换视图后重建 tooltip 条目（矩形与文案随当前视图变化）。"""
        if not self.hwnd:
            return
        if self._tip_hwnd:
            try:
                win32gui.DestroyWindow(self._tip_hwnd)
            except win32gui.error:
                pass
        self._tip_hwnd = None
        self._tip_tools = []
        self._create_tooltip(win32api.GetModuleHandle(None))

    def _on_destroy(self, hwnd, msg, wparam, lparam):
        if self._tip_hwnd:
            try:
                win32gui.DestroyWindow(self._tip_hwnd)
            except win32gui.error:
                pass
        self._tip_hwnd = None
        self._tip_tools = []
        self.hwnd = None
        return 0

    def _on_key_down(self, hwnd, msg, wparam, lparam):
        if self._content_key(wparam):
            return 0
        if wparam == win32con.VK_ESCAPE:
            self.close()
            return 0
        return 0

    def _on_char(self, hwnd, msg, wparam, lparam):
        self._content_char(wparam)
        return 0

    def _on_ime(self, hwnd, msg, wparam, lparam):
        self._content_ime(msg, wparam, lparam)
        return 0

    def _on_timer(self, hwnd, msg, wparam, lparam):
        self._content_timer(wparam)
        return 0

    def _on_async(self, hwnd, msg, wparam, lparam):
        self._content_async()
        return 0

    def _on_lbutton_down(self, hwnd, msg, wparam, lparam):
        x, y = win32gui.GetCursorPos()
        rect = win32gui.GetWindowRect(hwnd)
        self._drag = (x, y, rect[0], rect[1], False)
        win32gui.SetCapture(hwnd)
        return 0

    def _on_mouse_move(self, hwnd, msg, wparam, lparam):
        if self._drag:
            x, y = win32gui.GetCursorPos()
            start_x, start_y, win_x, win_y, moved = self._drag
            dx, dy = x - start_x, y - start_y
            if not moved and abs(dx) + abs(dy) > 3:
                moved = True
            self._drag = (start_x, start_y, win_x, win_y, moved)
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOPMOST,
                win_x + dx,
                win_y + dy,
                0,
                0,
                win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE,
            )
            return 0

        x, y = win32gui.GetCursorPos()
        local_x, local_y = win32gui.ScreenToClient(hwnd, (x, y))
        hovered = self._hit_target(local_x, local_y)
        if hovered != self._hover:
            self._hover = hovered
            self._render()
        if not self._tracking_leave:
            track = _TRACKMOUSEEVENT(
                ctypes.sizeof(_TRACKMOUSEEVENT), _TME_LEAVE, hwnd, 0
            )
            _user32.TrackMouseEvent(ctypes.byref(track))
            self._tracking_leave = True
        return 0

    def _on_mouse_leave(self, hwnd, msg, wparam, lparam):
        self._tracking_leave = False
        if self._hover is not None:
            self._hover = None
            self._render()
        return 0

    def _on_lbutton_up(self, hwnd, msg, wparam, lparam):
        drag = self._drag
        self._drag = None
        win32gui.ReleaseCapture()
        if not drag or drag[4]:
            return 0
        # WM_LBUTTONUP 的 lParam 本身就是客户区坐标，直接用，免去一次屏幕坐标换算
        local_x = ctypes.c_short(lparam & 0xFFFF).value
        local_y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
        target = self._hit_target(local_x, local_y)
        if target == "close":
            self.close()
        else:
            self._content_click(target)
        return 0

    def _on_capture_changed(self, hwnd, msg, wparam, lparam):
        self._drag = None
        return 0

    def _on_hit_test(self, hwnd, msg, wparam, lparam):
        x = ctypes.c_short(lparam & 0xFFFF).value
        y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
        client_x, client_y = win32gui.ScreenToClient(hwnd, (x, y))
        width, height = self._size
        if not (0 <= client_x < width and 0 <= client_y < height):
            return win32con.HTTRANSPARENT
        # 圆角与内容间隙之外的透明像素让鼠标穿透
        if not self._alpha or self._alpha[client_y * width + client_x] <= 8:
            return win32con.HTTRANSPARENT
        return win32con.HTCLIENT


class SkinPickerWindow(PopupWindow):
    """皮肤选择内容页：皮肤列表来自 discover_skins()（磁盘实际文件）。

    视觉沿用统一令牌：白底 #ffffff、粉边 #ff69b4、紫字 #8a2be2、
    选中金底 #ffe8a3 + 金边 #ffd700，圆角 10px，无阴影、无渐变、无高光。
    点选后回调桌宠 apply_skin() 并保持窗口打开，由 ×、Esc 或桌宠退出关闭；
    卡片悬停用系统原生 tooltip 显示说明。
    """

    TITLE = "切换装扮"
    HINT = "Esc 或 × 关闭"
    WINDOW_TITLE = "Kirara 皮肤"
    CURSOR = win32con.IDC_HAND

    def __init__(self, owner, dpi, skins):
        self._skins = skins
        self._thumb_size = max(16, int(round(_PICKER_THUMB * dpi)))
        self._thumbs = [
            _skin_thumbnail(path, self._thumb_size)
            for _label, _name, path, _on, _desc in skins
        ]
        self._selected_path = os.path.normcase(os.path.abspath(owner.sprite_path))
        super().__init__(owner, dpi)

    def _content_layout(self):
        d = self._dpi
        self._card_w = int(round(_PICKER_CARD_W * d))
        self._card_h = int(round(_PICKER_CARD_H * d))
        self._gap = int(round(_PICKER_GAP * d))

        cols = _PICKER_COLS
        rows = max(1, (len(self._skins) + cols - 1) // cols)
        grid_w = cols * self._card_w + (cols - 1) * self._gap
        grid_h = rows * self._card_h + (rows - 1) * self._gap
        width = grid_w + self._pad * 2
        height = self._pad + self._title_h + int(round(10 * d)) + grid_h + self._pad
        self._size = (width, height)

        grid_top = self._pad + self._title_h + int(round(10 * d))
        self._cards = []
        for index, skin in enumerate(self._skins):
            row, col = divmod(index, cols)
            left = self._pad + col * (self._card_w + self._gap)
            top = grid_top + row * (self._card_h + self._gap)
            rect = (left, top, left + self._card_w, top + self._card_h)
            self._cards.append((rect,) + tuple(skin))

    def _draw_content(self, canvas, draw):
        d = self._dpi
        thumb = self._thumb_size
        text_top_gap = 9 * d
        caption_font = _font(12 * d)
        caption_w = self._card_w - 16 * d
        line_h = 15 * d

        for index, (rect, label, _filename, path, enabled, _desc) in enumerate(self._cards):
            left, top, right, bottom = rect
            selected = (
                enabled
                and os.path.normcase(os.path.abspath(path)) == self._selected_path
            )
            usable = self._thumbs[index] is not None
            hovered = enabled and usable and self._hover == ("card", index)

            draw.rounded_rectangle(
                rect,
                radius=int(round(_PICKER_CARD_RADIUS * d)),
                fill=(_UI_GOLD_FILL if selected else _UI_WHITE) + (255,),
                outline=(
                    _UI_DISABLED if not enabled
                    else (_UI_GOLD if (selected or hovered) else _UI_PINK)
                ) + (255,),
                width=max(2, int(round(2 * d))),
            )

            cx = (left + right) / 2.0
            lines = _wrap_text(caption_font, label, caption_w)[:2]
            # 头像 + 文字整体在卡片里垂直居中
            content_h = thumb + text_top_gap + line_h * len(lines)
            thumb_top = top + (self._card_h - content_h) / 2.0
            circle = [
                cx - thumb / 2.0,
                thumb_top,
                cx + thumb / 2.0,
                thumb_top + thumb,
            ]
            if usable:
                thumb_img = self._thumbs[index]
                if not enabled:
                    # 禁用卡：内容整体降透明度
                    thumb_img = thumb_img.copy()
                    thumb_img.putalpha(
                        thumb_img.getchannel("A").point(
                            lambda value: int(value * _DISABLED_CONTENT_ALPHA)
                        )
                    )
                canvas.alpha_composite(
                    thumb_img,
                    (int(round(cx - thumb / 2.0)), int(round(thumb_top))),
                )
                draw.ellipse(
                    circle,
                    outline=(_UI_DISABLED if not enabled else _UI_PINK) + (255,),
                    width=max(2, int(round(2 * d))),
                )
            else:
                # 读不到/损坏的文件：占位卡，不参与点击
                draw.ellipse(
                    circle,
                    fill=_UI_WHITE + (255,),
                    outline=(_UI_DISABLED if not enabled else _UI_PINK) + (255,),
                    width=max(2, int(round(2 * d))),
                )
                draw.text(
                    (cx, thumb_top + thumb / 2.0),
                    "无法预览",
                    font=_font(11 * d),
                    fill=_UI_MUTED + (255,),
                    anchor="mm",
                )

            text_y = thumb_top + thumb + text_top_gap
            caption_fill = _UI_PURPLE + (
                int(255 * _DISABLED_CONTENT_ALPHA) if not enabled else 255,
            )
            for line_index, line in enumerate(lines):
                draw.text(
                    (cx, text_y + line_h * (line_index + 0.5)),
                    line,
                    font=caption_font,
                    fill=caption_fill,
                    anchor="mm",
                )

    def _content_hit(self, local_x, local_y):
        for index, (rect, _label, _filename, _path, enabled, _desc) in enumerate(self._cards):
            # 禁用卡与无法预览的卡都跳过：不产生悬停/点击目标
            if not enabled or self._thumbs[index] is None:
                continue
            if rect[0] <= local_x <= rect[2] and rect[1] <= local_y <= rect[3]:
                return ("card", index)
        return None

    def _content_click(self, target):
        if not isinstance(target, tuple):
            return
        _rect, label, filename, path, _enabled, _desc = self._cards[target[1]]
        # 应用成功也不关窗：更新选中态，方便连续点几张对比
        if self.owner.apply_skin(label, filename):
            self._selected_path = os.path.normcase(os.path.abspath(path))
            self._render()

    def _tooltip_specs(self):
        specs = []
        for rect, _label, _filename, _path, _enabled, desc in self._cards:
            if desc:
                specs.append((rect, desc))
        return specs


class ChatPanel(PopupWindow):
    """「提示词」珠子改造成的 Kirara 专属对话面板。

    与网页端共用 .simchat/data/sessions/mod-kirara.json：
      - 打开时与每 2 秒按 mtime+size 比对，另一端写入后自动刷新
      - 发送走宿主 POST /api/chat（固定 session_id，system 触发词 "Kirara"）
      - 自绘输入框用 imm32 接中文输入法（组合串 + 候选框定位）
    """

    TITLE = "Kirara"
    HINT = "Enter 发送 · Esc 关闭"
    WINDOW_TITLE = "Kirara 对话"
    CURSOR = win32con.IDC_IBEAM

    def __init__(self, owner, dpi):
        self._messages = []
        self._sig = self._session_sig()
        self._session_system = ""
        self._input = ""
        self._caret = 0
        self._composing = False
        self._comp_text = ""
        self._status = ""
        self._pending_user = ""
        self._stream_text = ""
        self._sending = False
        self._caret_xy = (0, 0)
        super().__init__(owner, dpi)

    def show(self):
        if self.hwnd:
            self.bring_to_front()
            return
        super().show()
        if not self.hwnd:
            return
        self._load()
        _user32.SetTimer(self.hwnd, _CHAT_TIMER_ID, _CHAT_POLL_MS, None)
        self._render()
        threading.Thread(target=self._initial_sync, daemon=True).start()

    def _content_layout(self):
        d = self._dpi
        self._width = int(round(_CHAT_WIDTH * d))
        self._height = int(round(_CHAT_HEIGHT * d))
        self._size = (self._width, self._height)
        self._body_top = self._pad + self._title_h + int(round(10 * d))
        self._input_h = int(round(_CHAT_INPUT_H * d))
        self._send_w = int(round(_CHAT_SEND_W * d))
        self._input_top = self._height - self._pad - self._input_h
        self._transcript_bottom = self._input_top - int(round(10 * d))
        self._input_rect = (
            self._pad, self._input_top,
            self._width - self._pad - self._send_w - int(round(8 * d)),
            self._input_top + self._input_h,
        )
        self._send_rect = (
            self._width - self._pad - self._send_w, self._input_top,
            self._width - self._pad, self._input_top + self._input_h,
        )

    # ---- 读写同一份会话文件 ----

    def _load(self):
        data = _load_session_detail(_KIRARA_SESSION_ID) or {}
        self._messages = list(data.get("messages") or [])
        self._session_system = str(data.get("system") or "")
        self._sig = self._session_sig()

    def _session_sig(self):
        path = os.path.join(_SESSIONS_DIR, _KIRARA_SESSION_ID + ".json")
        try:
            stat = os.stat(path)
            return (stat.st_mtime_ns, stat.st_size)
        except OSError:
            return None

    # ---- 绘制：消息列表 ----

    def _draw_content(self, canvas, draw):
        self._draw_transcript(draw)
        if self._status:
            draw.text(
                (self._pad, self._transcript_bottom - int(round(8 * self._dpi))),
                self._status,
                font=_font(10 * self._dpi),
                fill=_UI_MUTED + (255,),
                anchor="lb",
            )
        self._draw_input(draw)

    def _transcript_lines(self, max_w):
        """从最新消息往前收集，直到填满可视高度；返回按时间正序的行块。"""
        d = self._dpi
        body_font = _font(11.5 * d)
        line_h = int(round(16 * d))
        gap = int(round(_CHAT_MSG_GAP * d))
        budget = self._transcript_bottom - self._body_top
        msgs = list(self._messages)
        if self._pending_user:
            msgs.append({"role": "user", "content": self._pending_user})
        if self._stream_text:
            msgs.append({"role": "assistant", "content": self._stream_text})
        blocks = []
        used = 0
        for message in reversed(msgs):
            role = message.get("role") or ""
            label = "你" if role == "user" else ("绮罗罗" if role == "assistant" else str(role))
            fill = _UI_PURPLE if role == "user" else _UI_PINK
            content = str(message.get("content") or "").replace("\r", "\n")
            lines = []
            for part in content.split("\n"):
                lines.extend(_wrap_text(body_font, part, max_w) or [""])
            lines = lines[:_CHAT_LINES_PER_MSG] or [""]
            block_h = int(round(13 * d)) + line_h * len(lines) + gap
            if used + block_h > budget and blocks:
                break
            blocks.append((label, fill, lines))
            used += block_h
        blocks.reverse()
        return blocks

    def _draw_transcript(self, draw):
        d = self._dpi
        max_w = self._width - self._pad * 2
        blocks = self._transcript_lines(max_w)
        if not blocks:
            draw.text(
                (self._width / 2.0, (self._body_top + self._transcript_bottom) / 2.0),
                "还没有对话，先说点什么吧",
                font=_font(11.5 * d),
                fill=_UI_MUTED + (255,),
                anchor="mm",
            )
            return
        role_font = _font(9.5 * d)
        body_font = _font(11.5 * d)
        line_h = int(round(16 * d))
        gap = int(round(_CHAT_MSG_GAP * d))
        y = self._body_top
        for label, fill, lines in blocks:
            draw.text((self._pad, y), label, font=role_font, fill=fill + (255,), anchor="la")
            y += int(round(13 * d))
            for line in lines:
                draw.text((self._pad, y), line, font=body_font, fill=_UI_TEXT + (255,), anchor="la")
                y += line_h
            y += gap

    # ---- 绘制：输入框 ----

    def _input_view(self):
        """单行输入的可视窗口：光标始终可见，左侧超出部分裁掉。"""
        d = self._dpi
        font = _font(12 * d)
        rect = self._input_rect
        inner_left = rect[0] + int(round(12 * d))
        inner_right = rect[2] - int(round(10 * d))
        max_w = max(10, inner_right - inner_left)
        text = self._input
        caret = max(0, min(self._caret, len(text)))
        start = 0
        while start < caret and _text_width(font, text[start:caret]) > max_w:
            start += 1
        visible = _clip_text(font, text[start:], max_w)
        offset = min(max_w, _text_width(font, text[start:caret]))
        return font, inner_left, visible, offset

    def _draw_input(self, draw):
        d = self._dpi
        rect = self._input_rect
        draw.rounded_rectangle(
            rect,
            radius=int(round(_CHAT_CARD_RADIUS * d)),
            fill=_UI_WHITE + (255,),
            outline=_UI_PINK + (255,),
            width=max(2, int(round(2 * d))),
        )
        font, inner_left, visible, offset = self._input_view()
        cy = (rect[1] + rect[3]) / 2.0
        if visible or self._comp_text:
            draw.text((inner_left, cy), visible, font=font, fill=_UI_TEXT + (255,), anchor="lm")
            if self._comp_text:
                draw.text(
                    (inner_left + offset, cy),
                    self._comp_text,
                    font=font,
                    fill=_UI_PURPLE + (255,),
                    anchor="lm",
                )
        else:
            draw.text(
                (inner_left, cy),
                "和绮罗罗说点什么…",
                font=font,
                fill=_UI_MUTED + (255,),
                anchor="lm",
            )
        # 光标：组合串末尾优先，否则跟随输入文本
        caret_x = inner_left + offset
        if self._comp_text:
            caret_x += _text_width(font, self._comp_text)
        draw.line(
            [
                (caret_x, rect[1] + int(round(10 * d))),
                (caret_x, rect[3] - int(round(10 * d))),
            ],
            fill=_UI_PURPLE + (255,),
            width=max(1, int(round(1.5 * d))),
        )
        # IME 组合窗/候选窗定位用（客户区坐标，_position_ime 里转屏幕坐标）
        self._caret_xy = (int(caret_x), int(cy))

        send_rect = self._send_rect
        sending = self._sending
        hovered = self._hover == "send" and not sending
        if sending:
            outline = _UI_DISABLED
        elif hovered:
            outline = _UI_GOLD
        else:
            outline = _UI_PINK
        draw.rounded_rectangle(
            send_rect,
            radius=int(round(_CHAT_CARD_RADIUS * d)),
            fill=(_UI_GOLD_FILL if hovered else _UI_WHITE) + (255,),
            outline=outline + (255,),
            width=max(2, int(round(2 * d))),
        )
        draw.text(
            ((send_rect[0] + send_rect[2]) / 2.0, (send_rect[1] + send_rect[3]) / 2.0),
            "发送中" if sending else "发送",
            font=_font(11 * d),
            fill=(_UI_DISABLED if sending else (_UI_PINK if hovered else _UI_PURPLE)) + (255,),
            anchor="mm",
        )

    # ---- 键盘 / 输入法 ----

    def _content_key(self, wparam):
        if wparam == win32con.VK_ESCAPE and self._composing:
            self._cancel_composition()
            return True
        if self._composing:
            # 组合中其余按键（回车/退格/方向键）由输入法自己处理
            return False
        if wparam == win32con.VK_RETURN:
            self._send()
            return True
        if wparam == win32con.VK_BACK:
            if self._caret > 0:
                self._input = self._input[:self._caret - 1] + self._input[self._caret:]
                self._caret -= 1
                self._render()
            return True
        if wparam == win32con.VK_DELETE:
            if self._caret < len(self._input):
                self._input = self._input[:self._caret] + self._input[self._caret + 1:]
                self._render()
            return True
        if wparam == win32con.VK_LEFT:
            self._caret = max(0, self._caret - 1)
            self._render()
            return True
        if wparam == win32con.VK_RIGHT:
            self._caret = min(len(self._input), self._caret + 1)
            self._render()
            return True
        if wparam == win32con.VK_HOME:
            self._caret = 0
            self._render()
            return True
        if wparam == win32con.VK_END:
            self._caret = len(self._input)
            self._render()
            return True
        return False

    def _content_char(self, wparam):
        # 控制字符（含 Enter/Backspace）已在 WM_KEYDOWN 处理，避免重复
        if wparam < 0x20 or wparam == 0x7F:
            return True
        ch = chr(wparam)
        if ch:
            self._insert(ch)
        return True

    def _content_ime(self, msg, wparam, lparam):
        if msg == _WM_IME_STARTCOMPOSITION:
            self._composing = True
            self._comp_text = ""
            self._position_ime()
            self._render()
            return True
        if msg == _WM_IME_COMPOSITION:
            if lparam & _GCS_RESULTSTR:
                text = self._ime_text(_GCS_RESULTSTR)
                self._composing = False
                self._comp_text = ""
                if text:
                    self._insert(text)
                else:
                    self._render()
                return True
            if lparam & _GCS_COMPSTR:
                self._composing = True
                self._comp_text = self._ime_text(_GCS_COMPSTR)
                self._position_ime()
                self._render()
                return True
            return True
        if msg == _WM_IME_ENDCOMPOSITION:
            self._composing = False
            self._comp_text = ""
            self._render()
            return True
        return False

    def _insert(self, text):
        caret = max(0, min(self._caret, len(self._input)))
        self._input = self._input[:caret] + text + self._input[caret:]
        self._caret = caret + len(text)
        self._render()

    def _ime_text(self, flag):
        if not self.hwnd:
            return ""
        himc = _imm32.ImmGetContext(self.hwnd)
        if not himc:
            return ""
        try:
            length = _imm32.ImmGetCompositionStringW(himc, flag, None, 0)
            if length <= 0:
                return ""
            buf = ctypes.create_unicode_buffer(length // 2 + 1)
            _imm32.ImmGetCompositionStringW(himc, flag, buf, length)
            return buf.value
        finally:
            _imm32.ImmReleaseContext(self.hwnd, himc)

    def _position_ime(self):
        if not self.hwnd:
            return
        himc = _imm32.ImmGetContext(self.hwnd)
        if not himc:
            return
        try:
            sx, sy = win32gui.ClientToScreen(self.hwnd, self._caret_xy)
            form = _COMPOSITIONFORM()
            form.dwStyle = _CFS_POINT
            form.ptCurrentPos = _POINT(int(sx), int(sy))
            _imm32.ImmSetCompositionWindow(himc, ctypes.byref(form))
            cand = _CANDIDATEFORM()
            cand.dwIndex = 0
            cand.dwStyle = _CFS_CANDIDATEPOS
            cand.ptCurrentPos = _POINT(int(sx), int(sy))
            _imm32.ImmSetCandidateWindow(himc, ctypes.byref(cand))
        finally:
            _imm32.ImmReleaseContext(self.hwnd, himc)

    def _cancel_composition(self):
        himc = _imm32.ImmGetContext(self.hwnd) if self.hwnd else None
        if himc:
            try:
                _imm32.ImmNotifyIME(himc, _NI_COMPOSITIONSTR, _CPS_CANCEL, 0)
            finally:
                _imm32.ImmReleaseContext(self.hwnd, himc)
        self._composing = False
        self._comp_text = ""
        self._render()

    # ---- 命中与点击 ----

    def _content_hit(self, local_x, local_y):
        if self._in_rect(self._input_rect, local_x, local_y):
            return "input"
        if self._in_rect(self._send_rect, local_x, local_y):
            return "send"
        return None

    def _content_click(self, target):
        if target == "send":
            self._send()
        elif target == "input" and self.hwnd:
            win32gui.SetFocus(self.hwnd)

    @staticmethod
    def _in_rect(rect, x, y):
        return rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]

    # ---- 刷新：2 秒轮询另一端写入 ----

    def _content_timer(self, wparam):
        if wparam != _CHAT_TIMER_ID:
            return False
        if self._sending:
            return True
        if self._session_sig() != self._sig:
            self._load()
            self._render()
        return True

    def _content_async(self):
        self._render()

    def _post_async(self):
        hwnd = self.hwnd
        if not hwnd:
            return
        try:
            win32gui.PostMessage(hwnd, _CHAT_ASYNC_MSG, 0, 0)
        except win32gui.error:
            pass

    def reload(self):
        """重新读盘并重绘（再次打开面板时调用）。"""
        self._load()
        self._render()

    # ---- 发送：宿主 /api/chat ----

    def _initial_sync(self):
        """打开面板时确保 Kirara 会话存在；服务不可用时只显示本地记录。"""
        try:
            self._ensure_session()
            self._status = ""
        except Exception as error:
            self._status = str(error)
        self._load()
        self._post_async()

    def _ensure_session(self):
        base = _server_base_url()
        if not base:
            raise RuntimeError("未找到 SimChat 服务地址")
        request = urllib.request.Request(
            base + "/api/mods/chat-cards/%s/ensure" % _KIRARA_MOD_ID,
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                response.read()
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", "replace")
            message = _http_error_message(body) or ("MOD 会话创建失败: HTTP %s" % error.code)
            raise RuntimeError(message)
        except urllib.error.URLError as error:
            raise RuntimeError("无法连接 SimChat 服务：%s" % (error.reason,))

    def _send(self):
        if self._sending or self._composing:
            return
        text = self._input.strip()
        if not text or not self.hwnd:
            return
        self._input = ""
        self._caret = 0
        self._pending_user = text
        self._stream_text = ""
        self._status = ""
        self._sending = True
        self._render()
        threading.Thread(target=self._send_worker, args=(text,), daemon=True).start()

    def _send_worker(self, text):
        error = ""
        partial = ""
        try:
            self._ensure_session()
            self._load()  # 会话可能刚创建：读回 system 触发词
            base = _server_base_url()
            if not base:
                raise RuntimeError("未找到 SimChat 服务地址")
            payload = json.dumps({
                "message": text,
                "session_id": _KIRARA_SESSION_ID,
                # system 取 MOD 声明并写入会话文件的触发词（模型卡：Kirara）
                "system": self._session_system or None,
            }).encode("utf-8")
            request = urllib.request.Request(
                base + "/api/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=300) as response:
                for raw in response:
                    line = raw.decode("utf-8", "replace").strip()
                    if not line.startswith("data:"):
                        continue
                    try:
                        event = json.loads(line[5:].strip())
                    except ValueError:
                        continue
                    kind = event.get("event")
                    if kind == "token":
                        partial += event.get("content") or ""
                        self._stream_text = partial
                        self._post_async()
                    elif kind == "final":
                        partial = event.get("content") or partial
                        self._stream_text = partial
                    elif kind == "error":
                        error = event.get("message") or "生成失败"
                    elif kind == "aborted":
                        partial = event.get("content") or partial
        except urllib.error.HTTPError as error_obj:
            body = error_obj.read().decode("utf-8", "replace")
            error = _http_error_message(body) or ("请求失败: HTTP %s" % error_obj.code)
        except urllib.error.URLError as error_obj:
            error = "无法连接 SimChat 服务：%s" % (error_obj.reason,)
        except Exception as error_obj:
            error = str(error_obj)
        finally:
            self._sending = False
            self._pending_user = ""
            self._stream_text = ""
            self._load()
            self._status = error
            self._post_async()


if __name__ == "__main__":
    pet = LayeredPet()
    thread = pet.start()
    print("[pet] hwnd=%s size=%s，右键菜单可退出" % (pet.hwnd, pet._size))
    # 等窗口线程结束（窗口销毁后 PumpMessages 返回），主线程随之退出进程
    thread.join()
