# kirara_tts.py
# Kirara 音声合成服务（基于 pyttsx3 / SAPI5）
# 支持：音色枚举、预设音色（贾维斯/贾薇丝/绮罗）、系统语音选择、WAV 字节合成
import os
import base64
import tempfile
import threading

# 安全导入 pyttsx3（未安装时服务降级，不影响主程序启动）
TTS_AVAILABLE = False
try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    pyttsx3 = None
    print("[Kirara TTS] 警告: pyttsx3 未安装，音声合成不可用")

# pyttsx3 的 runAndWait() 与驱动循环非线程安全，全局串行化所有合成请求
_tts_lock = threading.Lock()

# ==========================================
#              预设音色 (Voice Presets)
# ==========================================
# gender: 期望的系统语音性别；rate: 语速；pitch 由不同系统语音天然区分
VOICE_PRESETS = {
    "jrvs": {
        "label": "贾维斯",
        "en_name": "JRVS",
        "icon": "🎩",
        "gender": "male",
        "rate": 135,
        "volume": 0.95,
        "description": "沉稳男声，专业副驾驶",
        "sample_text": "先生，您好。我是贾维斯，TeleVideo 公司的 AI 副驾驶。"
    },
    "lady": {
        "label": "贾薇丝",
        "en_name": "JARVIS-Lady",
        "icon": "👩‍💼",
        "gender": "female",
        "rate": 145,
        "volume": 0.95,
        "description": "优雅女声，从容干练",
        "sample_text": "先生，您好。我是贾薇丝，随时听候您的吩咐。"
    },
    "kirara": {
        "label": "绮罗",
        "en_name": "Kirara",
        "icon": "🎀",
        "gender": "female",
        "rate": 168,
        "volume": 1.0,
        "description": "活泼少女音声，甜美可爱",
        "sample_text": "主人sama好呀！我是绮罗，有什么可以帮到您的吗？"
    }
}
DEFAULT_VOICE_SELECTOR = "preset:kirara"

# 常见中文 SAPI 语音名 → 性别启发式
_FEMALE_NAME_KEYWORDS = ("huihui", "yaoyao", "xiaoxiao", "xiaoyi", "female", "woman",
                         "女", "zira", "aria", "jenny", "xiaomo")
_MALE_NAME_KEYWORDS = ("kangkang", "male", "man", "男", "david", "mark", "yunxi", "yunyang")


def _detect_gender(voice):
    """尽力推断系统语音性别（SAPI5 的 gender 字段经常为空）。"""
    gender = ""
    try:
        gender = str(getattr(voice, "gender", "") or "").lower()
    except Exception:
        pass
    name = ""
    try:
        name = str(getattr(voice, "name", "") or "").lower()
    except Exception:
        pass

    if "female" in gender or "女" in gender:
        return "female"
    if "male" in gender or "男" in gender:
        return "male"

    for kw in _FEMALE_NAME_KEYWORDS:
        if kw in name:
            return "female"
    for kw in _MALE_NAME_KEYWORDS:
        if kw in name:
            return "male"
    return "unknown"


def _voice_is_chinese(voice):
    try:
        langs = getattr(voice, "languages", None) or []
        for loc in langs:
            loc_str = str(loc).lower()
            # SAPI LCID: zh-CN=2052(0x804), zh-TW=1028(0x404), zh-HK=3076(0xc04)
            if "zh" in loc_str or "804" in loc_str or "404" in loc_str or "c04" in loc_str:
                return True
        name = str(getattr(voice, "name", "")).lower()
        if any(k in name for k in ("chinese", "china", "huihui", "kangkang", "yaoyao", "中文", "汉语")):
            return True
    except Exception:
        pass
    return False


def list_tts_voices():
    """枚举本机可用的系统语音。

    返回: (voices, error)
      voices: [{"id": ..., "name": ..., "gender": "male/female/unknown", "chinese": bool}]
    """
    if not TTS_AVAILABLE:
        return [], "pyttsx3 未安装"

    with _tts_lock:
        engine = None
        try:
            engine = pyttsx3.init()
            voices = []
            for v in engine.getProperty("voices"):
                voices.append({
                    "id": str(v.id),
                    "name": str(getattr(v, "name", v.id)),
                    "gender": _detect_gender(v),
                    "chinese": _voice_is_chinese(v)
                })
            return voices, None
        except Exception as e:
            return [], f"{type(e).__name__}: {e}"
        finally:
            if engine is not None:
                try:
                    engine.stop()
                except Exception:
                    pass


def get_voice_presets():
    """返回可供前端渲染的预设音色枚举。"""
    return [
        {
            "key": key,
            "label": cfg["label"],
            "en_name": cfg["en_name"],
            "icon": cfg["icon"],
            "gender": cfg["gender"],
            "description": cfg["description"],
            "sample_text": cfg["sample_text"],
        }
        for key, cfg in VOICE_PRESETS.items()
    ]


def _parse_selector(selector):
    """解析前端音色选择值：'preset:kirara' / 'voice:<id>' / 裸 id。"""
    if not selector:
        return "preset", "kirara"
    selector = str(selector)
    if selector.startswith("preset:"):
        return "preset", selector[len("preset:"):]
    if selector.startswith("voice:"):
        return "voice", selector[len("voice:"):]
    # 兼容裸 key
    if selector in VOICE_PRESETS:
        return "preset", selector
    return "voice", selector


def _resolve_system_voice(engine, kind, value):
    """在引擎上选定 voice id，并返回 (rate, volume, voice_name)。"""
    preset_rate = 145
    preset_volume = 0.95
    want_gender = None

    if kind == "preset":
        preset = VOICE_PRESETS.get(value)
        if preset is None:
            preset = VOICE_PRESETS["kirara"]
        want_gender = preset["gender"]
        preset_rate = preset["rate"]
        preset_volume = preset["volume"]
    # kind == "voice" 时 value 为系统语音 id

    voices = engine.getProperty("voices")
    chosen = None

    if kind == "voice":
        for v in voices:
            if str(v.id) == value:
                chosen = v
                break
    else:
        # 1) 性别匹配且优先中文
        gender_matches = [v for v in voices if _detect_gender(v) == want_gender]
        chosen = next((v for v in gender_matches if _voice_is_chinese(v)), None)
        if chosen is None and gender_matches:
            chosen = gender_matches[0]
        # 2) 性别无匹配时退而求其次：任意中文语音
        if chosen is None:
            chosen = next((v for v in voices if _voice_is_chinese(v)), None)
        # 3) 最后兜底：系统默认语音

    if chosen is not None:
        try:
            engine.setProperty("voice", chosen.id)
        except Exception as e:
            print(f"[Kirara TTS] 设置语音失败: {e}")
        voice_name = str(getattr(chosen, "name", chosen.id))
    else:
        voice_name = "系统默认语音"

    return preset_rate, preset_volume, voice_name


def _synthesize(text, selector, want_bytes):
    """在全局锁内创建一次性引擎完成合成（SAPI 要求 init 与 runAndWait 在同一线程）。"""
    if not TTS_AVAILABLE:
        raise RuntimeError("pyttsx3 未安装，无法进行音声合成")

    kind, value = _parse_selector(selector)
    tmp_path = None
    with _tts_lock:
        engine = pyttsx3.init()
        try:
            rate, volume, voice_name = _resolve_system_voice(engine, kind, value)
            engine.setProperty("rate", rate)
            engine.setProperty("volume", volume)

            if want_bytes:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                    tmp_path = tmp.name
                engine.save_to_file(text, tmp_path)
                engine.runAndWait()
                with open(tmp_path, "rb") as f:
                    audio_bytes = f.read()
                return audio_bytes, voice_name
            else:
                engine.say(text)
                engine.runAndWait()
                return None, voice_name
        finally:
            try:
                engine.stop()
            except Exception:
                pass
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass


def synthesize_to_wav(text, selector=None):
    """合成语音并返回 WAV 字节。"""
    return _synthesize(text, selector, want_bytes=True)


def synthesize_to_data_uri(text, selector=None):
    """合成语音并返回浏览器可直接播放的 data:audio/wav;base64 URI。"""
    audio_bytes, voice_name = synthesize_to_wav(text, selector)
    b64 = base64.b64encode(audio_bytes).decode("utf-8")
    return f"data:audio/wav;base64,{b64}", voice_name


def speak_text(text, selector=None):
    """在服务器本机直接播报（阻塞至播报结束）。"""
    return _synthesize(text, selector, want_bytes=False)


class Kirara_TTS:
    """向后兼容的 TTS 封装类（内部调用新的模块级函数）。"""

    def __init__(self):
        self.lock = _tts_lock
        if not TTS_AVAILABLE:
            print("[Kirara TTS] 警告: pyttsx3 未安装，播报功能不可用")

    def speak(self, text, selector=None):
        speak_text(text, selector)

    def speak_async(self, text, selector=None):
        thread = threading.Thread(target=self.speak, args=(text, selector), daemon=True)
        thread.start()

    def get_audio_bytes(self, text, selector=None):
        audio_bytes, _ = synthesize_to_wav(text, selector)
        return base64.b64encode(audio_bytes).decode("utf-8")

    def stop(self):
        # 一次性引擎设计下无需显式停止
        pass
