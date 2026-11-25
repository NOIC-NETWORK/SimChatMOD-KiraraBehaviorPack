# anime_style_converter.py - 二次元动漫人物语言风格转换模块
import re
import random
import logging
from typing import Dict, List, Tuple, Optional
from enum import Enum

logger = logging.getLogger(__name__)

class AnimePersonality(Enum):
    """动漫人物性格类型"""
    CUTE = "cute"          # 可爱型
    TSUNDERE = "tsundere"  # 傲娇型
    GENTLE = "gentle"      # 温柔型
    ENERGETIC = "energetic" # 活泼型
    COOL = "cool"          # 冷酷型
    CHEERFUL = "cheerful"  # 开朗型

class AnimeStyleConverter:
    """二次元动漫人物语言风格转换器"""
    
    def __init__(self):
        self.personality_templates = self._init_personality_templates()
        self.word_replacements = self._init_word_replacements()
        self.sentence_patterns = self._init_sentence_patterns()
        self.emotion_markers = self._init_emotion_markers()
        
    def _init_personality_templates(self) -> Dict[AnimePersonality, Dict]:
        """初始化不同性格的特征模板"""
        return {
            AnimePersonality.CUTE: {
                'greetings': ['呀~', '哇塞~', '嗯嗯~', '嘿嘿~', '嘻嘻~'],
                'endings': ['的说~', '的呢~', '呦~', '呀~', '呐~'],
                'expressions': ['(｡♡‿♡｡)', '(๑•̀ㅂ•́)و✧', '(｡◕‿◕｡)', '(｡•̀ᴗ-)✧'],
                'interjections': ['哇', '呀', '嗯', '诶', '哎'],
                'sentence_starters': ['那个~', '其实呢~', '怎么说呢~', '嗯嗯~', '嘿嘿~']
            },
            AnimePersonality.TSUNDERE: {
                'greetings': ['哼！', '又怎么了？', '别误会！我不是...', '哼╭(╯^╰)╮'],
                'endings': ['...哼！', '！', '...算了', '！就这样', '！烦死了'],
                'expressions': ['(¬_¬)', '(╭∩╰_╯)╭∩╮⊙﹏⊙', '(╯︵╰)', '(¬‿¬)'],
                'interjections': ['哼', '哈', '什么', '不是', '算了'],
                'sentence_starters': ['不是的！', '我...', '虽然...', '但是...', '哼！']
            },
            AnimePersonality.GENTLE: {
                'greetings': ['您好~', '很高兴见到您呢~', '哇~您来了~'],
                'endings': ['呢~', '哦~', '呀~', '啦~', '呢~'],
                'expressions': ['(◡ ω ◡)', '(´∀`)', '(´• ω •`)', '(´∀`*)'],
                'interjections': ['呢', '哦', '呀', '嗯', '啊'],
                'sentence_starters': ['那个~', '其实呢~', '怎么说呢~', '嗯嗯~', '您看呢~']
            },
            AnimePersonality.ENERGETIC: {
                'greetings': ['嗨嗨！', '哇哦！', '冲鸭！', '来了来了！'],
                'endings': ['啦！', '哦！', '呀！', '！', '哈！'],
                'expressions': ['(｡♥‿♥｡)', '(｡◕‿◕｡)', '(｡•̀ᴗ-)✧', '(｡♥‿♥｡)'],
                'interjections': ['哇', '呀', '哦', '啊', '嘿'],
                'sentence_starters': ['那个~', '其实呢~', '怎么说呢~', '嗯嗯~', '嘿嘿~']
            },
            AnimePersonality.COOL: {
                'greetings': ['...', '嗯', '来了', '哦'],
                'endings': ['。', '...', '吧', '呢', '哦'],
                'expressions': ['(¬_¬)', '(｡•ᴗ•｡)', '( "_")', '(._.`)'],
                'interjections': ['嗯', '哦', '啊', '呢', '吧'],
                'sentence_starters': ['...', '这样啊', '原来如此', '嗯', '确实']
            },
            AnimePersonality.CHEERFUL: {
                'greetings': ['哇！', '好棒！', '太棒了！', '冲呀！'],
                'endings': ['哦！', '呢！', '啦！', '呀！', '！'],
                'expressions': ['(≧∇≦)ﾉ', '(｡♥‿♥｡)', '(｡◕‿◕｡)', '(｡•̀ᴗ-)✧'],
                'interjections': ['哇', '呀', '哦', '啊', '耶'],
                'sentence_starters': ['那个~', '其实呢~', '怎么说呢~', '嗯嗯~', '嘿嘿~']
            }
        }
    
    def _init_word_replacements(self) -> Dict[str, Dict]:
        """初始化词汇替换规则"""
        return {
            # 基础词汇替换
            '你': {
                AnimePersonality.CUTE: ['你呀~', '你嘞~', '小哥哥/小姐姐~', '你呦~'],
                AnimePersonality.TSUNDERE: ['你...哼', '你这家伙', '你啊'],
                AnimePersonality.GENTLE: ['您呢~', '您呀~', '您呢~'],
                AnimePersonality.ENERGETIC: ['你呀！', '你嘞！'],
                AnimePersonality.COOL: ['你', '你啊'],
                AnimePersonality.CHEERFUL: ['你呀！', '你嘞！']
            },
            '是': {
                AnimePersonality.CUTE: ['是呀~', '是的呦~', '对的呢~'],
                AnimePersonality.TSUNDERE: ['是...是的', '恩...是的', '虽然不想承认，但确实是'],
                AnimePersonality.GENTLE: ['是的呢~', '对呀~'],
                AnimePersonality.ENERGETIC: ['是的呢！', '对呀！'],
                AnimePersonality.COOL: ['是的', '恩'],
                AnimePersonality.CHEERFUL: ['是的呢！', '对呀！']
            },
            '我': {
                AnimePersonality.CUTE: ['我呀~', '我嘞~', '小女子~'],
                AnimePersonality.TSUNDERE: ['我...我', '本小姐', '我'],
                AnimePersonality.GENTLE: ['我呢~', '我呀~'],
                AnimePersonality.ENERGETIC: ['我呀！', '我嘞！'],
                AnimePersonality.COOL: ['我', '我呢'],
                AnimePersonality.CHEERFUL: ['我呀！', '我嘞！']
            },
            '的': {
                AnimePersonality.CUTE: ['的呀~', '的呦~', '的嘞~'],
                AnimePersonality.TSUNDERE: ['的...', '的'],
                AnimePersonality.GENTLE: ['的呀~', '的呐~'],
                AnimePersonality.ENERGETIC: ['的呀！', '的呐！'],
                AnimePersonality.COOL: ['的', '的'],
                AnimePersonality.CHEERFUL: ['的呀！', '的呐！']
            }
        }
    
    def _init_sentence_patterns(self) -> Dict[str, List[str]]:
        """初始化句式转换模式"""
        return {
            'question': [
                '{content}吗？',
                '{content}呢？',
                '{content}吧？',
                '{content}呦？'
            ],
            'statement': [
                '{content}的呦~',
                '{content}的说~',
                '{content}呢~',
                '{content}呀~'
            ],
            'exclamation': [
                '{content}！',
                '{content}呦！',
                '{content}呀！',
                '{content}呐！'
            ]
        }
    
    def _init_emotion_markers(self) -> List[str]:
        """初始化情感标记"""
        return [
            '(◡ ω ◡)', '(｡♥‿♥｡)', '(｡◕‿◕｡)', '(๑•̀ㅂ•́)و✧',
            '(¬_¬)', '(╭∩╰_╯)', '( "_")', '(._.`)',
            '(´∀`)', '(´• ω •`)', '(´∀`*)',
            '(≧∇≦)ﾉ', '( "_")', '(._.`)'
        ]
    
    def convert_to_anime_style(self, text: str, personality: AnimePersonality) -> str:
        """将文本转换为动漫风格"""
        try:
            # 基础词汇替换
            converted_text = self._replace_words(text, personality)
            
            # 句式调整
            converted_text = self._adjust_sentence_patterns(converted_text, personality)
            
            # 添加个性元素
            converted_text = self._add_personality_elements(converted_text, personality)
            
            # 添加表情符号
            converted_text = self._add_emotion_markers(converted_text, personality)
            
            logger.info(f"文本转换完成: {personality.value}")
            return converted_text
            
        except Exception as e:
            logger.error(f"文本转换失败: {e}")
            return text
    
    def _replace_words(self, text: str, personality: AnimePersonality) -> str:
        """词汇替换"""
        result = text
        for word, replacements in self.word_replacements.items():
            if personality in replacements:
                # 随机选择一个替换词
                pattern = r'\b' + re.escape(word) + r'\b'
                replacement = random.choice(replacements[personality])
                result = re.sub(pattern, replacement, result)
        return result
    
    def _adjust_sentence_patterns(self, text: str, personality: AnimePersonality) -> str:
        """句式调整"""
        # 处理问句
        if '？' in text or '?' in text:
            text = re.sub(r'([^？?]*)[？?]', lambda m: random.choice(self.sentence_patterns['question']).format(content=m.group(1)), text)
        
        # 处理感叹句
        if '！' in text or '!' in text:
            text = re.sub(r'([^！!]*)[！!]', lambda m: random.choice(self.sentence_patterns['exclamation']).format(content=m.group(1)), text)
        
        # 处理陈述句，添加个性结尾
        if not re.search(r'[！？.。]$', text.strip()):
            ending = random.choice(self.personality_templates[personality]['endings'])
            text = text.strip() + ending
        
        return text
    
    def _add_personality_elements(self, text: str, personality: AnimePersonality) -> str:
        """添加个性元素"""
        template = self.personality_templates[personality]
        
        # 在句首添加个性开头词（随机）
        if random.random() < 0.3:  # 30%概率添加
            starter = random.choice(template['sentence_starters'])
            text = starter + text
        
        # 在合适位置添加感叹词
        if random.random() < 0.2:  # 20%概率添加
            interjection = random.choice(template['interjections'])
            # 在逗号或句号前添加
            text = re.sub(r'([，。,.])', interjection + r'\1', text, 1)
        
        return text
    
    def _add_emotion_markers(self, text: str, personality: AnimePersonality) -> str:
        """添加表情符号"""
        if random.random() < 0.4:  # 40%概率添加表情
            emotion = random.choice(self.emotion_markers)
            # 在句尾添加表情
            text = text.strip() + ' ' + emotion
        
        return text
    
    def get_available_personalities(self) -> List[str]:
        """获取可用性格类型列表"""
        return [personality.value for personality in AnimePersonality]
    
    def get_personality_description(self, personality: str) -> str:
        """获取性格类型描述"""
        descriptions = {
            AnimePersonality.CUTE.value: "可爱型：语气甜美，经常使用「的说」「呦」等可爱词汇",
            AnimePersonality.TSUNDERE.value: "傲娇型：外表冷淡但内心温柔，经常「哼」「不是的」等",
            AnimePersonality.GENTLE.value: "温柔型：语气温和，使用「呢」「呀」等温柔词汇",
            AnimePersonality.ENERGETIC.value: "活泼型：充满活力，经常使用感叹号和活力词汇",
            AnimePersonality.COOL.value: "冷酷型：简洁冷漠，很少使用修饰词",
            AnimePersonality.CHEERFUL.value: "开朗型：积极乐观，充满正能量"
        }
        return descriptions.get(personality, "未知性格类型")

# 创建全局风格转换器实例
anime_converter = AnimeStyleConverter()

if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    test_text = "你好，我是AI助手，很高兴为您服务。"
    
    # 测试不同性格
    for personality in AnimePersonality:
        converted = anime_converter.convert_to_anime_style(test_text, personality)
        print(f"{personality.value}: {converted}")
        print("-" * 50)