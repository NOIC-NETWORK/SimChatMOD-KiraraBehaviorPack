# api_client.py - 统一API客户端，支持多模型切换
import requests
import logging
from typing import Dict, Any, Optional
import json
import time

# 尝试导入OpenAI，如果失败则使用模拟实现
try:
    print("Loading OpenAI module...")
    from openai import OpenAI
    from openai import APIError
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    logging.warning("OpenAI模块未安装，使用模拟实现")

# 模拟OpenAI客户端（当OpenAI模块不可用时）
class MockOpenAI:
    def __init__(self, api_key, base_url):
        self.api_key = api_key
        self.base_url = base_url
        self.chat = self.MockChat()
    
    class MockChat:
        def __init__(self):
            self.completions = MockOpenAI.MockCompletions()
    
    class MockCompletions:
        def __init__(self):
            pass
        
        def create(self, **kwargs):
            class MockResponse:
                class MockChoices:
                    class MockMessage:
                        content = "这是模拟的AI响应。由于OpenAI模块未安装，无法调用实际API。"
                choices = [MockMessage()]
                
                class MockUsage:
                    prompt_tokens = 0
                    completion_tokens = 0
                    total_tokens = 0
                usage = MockUsage()
            return MockResponse()

# 当OpenAI模块不可用时，使用模拟实现
if not HAS_OPENAI:
    class OpenAI:
        def __init__(self, api_key, base_url):
            self.api_key = api_key
            self.base_url = base_url
            self.chat = MockOpenAI(api_key, base_url).chat
    
    class APIError(Exception):
        pass

logger = logging.getLogger(__name__)

class ModelConfig:
    """模型配置类"""
    def __init__(self, name: str, api_base: str, api_key: str, model_name: str, max_tokens: int = 2048):
        self.name = name
        self.api_base = api_base
        self.api_key = api_key
        self.model_name = model_name
        self.max_tokens = max_tokens

class UnifiedAPIClient:
    """统一API客户端，支持多模型切换"""
    
    def __init__(self):
        self.models = {}
        self.current_model = None
        self.client = None
        # 添加响应缓存
        self.response_cache = {}
        self.cache_ttl = 300  # 缓存5分钟
        # 请求统计
        self.request_count = 0
        self.last_request_time = 0
        
    def add_model(self, config: ModelConfig):
        """添加模型配置"""
        self.models[config.name] = config
        logger.info(f"添加模型配置: {config.name}")
        
    def set_current_model(self, model_name: str):
        """设置当前使用的模型"""
        if model_name in self.models:
            self.current_model = model_name
            config = self.models[model_name]
            self.client = OpenAI(
                api_key=config.api_key,
                base_url=config.api_base
            )
            logger.info(f"切换到模型: {model_name}")
            return True
        else:
            logger.error(f"模型 {model_name} 不存在")
            return False
    
    def generate_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """生成AI响应"""
        if not self.current_model or not self.client:
            return {
                'success': False,
                'error': '未选择模型或客户端未初始化'
            }
        
        try:
            config = self.models[self.current_model]
            
            # 准备请求参数
            request_params = {
                'model': config.model_name,
                'messages': [
                    {"role": "system", "content": "你是一个二次元少女形象的人工智能系统,绮罗（Kirara）,活泼甜美而富有想象力，能够看到人类看不到的“闪闪发亮”的点,带有“二次元”的说话风格"},
                    {"role": "user", "content": prompt}
                ],
                'max_tokens': kwargs.get('max_tokens', config.max_tokens),
                'temperature': kwargs.get('temperature', 0.7),
                'top_p': kwargs.get('top_p', 0.9),
            }
            
            logger.info(f"发送请求到 {self.current_model}: {prompt[:50]}...")
            
            start_time = time.time()
            response = self.client.chat.completions.create(**request_params)
            end_time = time.time()
            
            response_time = end_time - start_time
            response_text = response.choices[0].message.content.strip()
            
            logger.info(f"模型 {self.current_model} 响应时间: {response_time:.2f}秒")
            logger.info(f"模型 {self.current_model} 响应: {response_text[:100]}...")
            
            # 将usage对象及其嵌套对象转换为可JSON序列化的字典
            def convert_to_dict(obj):
                if hasattr(obj, 'to_dict'):
                    return obj.to_dict()
                elif hasattr(obj, '__dict__'):
                    result = {}
                    for key, value in obj.__dict__.items():
                        if not key.startswith('_'):
                            result[key] = convert_to_dict(value)
                    return result
                elif isinstance(obj, (list, tuple)):
                    return [convert_to_dict(item) for item in obj]
                elif isinstance(obj, dict):
                    return {key: convert_to_dict(value) for key, value in obj.items()}
                else:
                    return obj
            
            usage_data = getattr(response, 'usage', {})
            usage_dict = convert_to_dict(usage_data)
                
            return {
                'success': True,
                'response': response_text,
                'model': self.current_model,
                'response_time': response_time,
                'usage': usage_dict
            }
            
        except APIError as e:
            logger.error(f"API调用错误: {e}")
            return {
                'success': False,
                'error': f'API调用失败: {str(e)}'
            }
        except Exception as e:
            logger.error(f"生成响应时发生未知错误: {e}")
            return {
                'success': False,
                'error': f'生成响应失败: {str(e)}'
            }
    
    def get_available_models(self) -> list:
        """获取可用模型列表"""
        return list(self.models.keys())
    
    def get_model_info(self, model_name: str) -> Optional[Dict]:
        """获取模型信息"""
        if model_name in self.models:
            config = self.models[model_name]
            return {
                'name': config.name,
                'model_name': config.model_name,
                'api_base': config.api_base,
                'max_tokens': config.max_tokens
            }
        return None

# 创建全局API客户端实例
api_client = UnifiedAPIClient()

# 默认模型配置 - 实际使用时需要配置真实的API密钥
def init_models():
    """初始化模型配置"""
    # Qwen3模型配置
    qwen_config = ModelConfig(
        name="qwen3",
        api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key="sk-fdc4da28e4854cf2b9fb04c803f30bc9",  # 需要配置真实密钥
        model_name="qwen3.8-max",
        max_tokens=2048
    )
    
    # GLM-4模型配置
    glm_config = ModelConfig(
        name="glm4",
        api_base="https://open.bigmodel.cn/api/paas/v4",
        api_key="YOUR_GLM_API_KEY",  # 需要配置真实密钥
        model_name="glm-4",
        max_tokens=2048
    )
    #TTS模型配置
    tts_config = ModelConfig(
        name="tts",
        api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key="sk-fdc4da28e4854cf2b9fb04c803f30bc9",  # 需要配置真实密钥
        model_name="qwen3-tts1",
        max_tokens=2048
    )
    #VL模型配置
    vl_config = ModelConfig(
        name="vl",
        api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key="sk-fdc4da28e4854cf2b9fb04c803f30bc9",  # 需要配置真实密钥
        model_name="qwen3-tts1",
        max_tokens=2048
    )
    # 添加模型到客户端
    api_client.add_model(qwen_config)
    api_client.add_model(glm_config)
    api_client.add_model(tts_config)
    
    # 设置默认模型
    api_client.set_current_model("qwen3")
    
    logger.info("模型配置初始化完成")
    return api_client