# local_model_client.py - 本地大模型客户端，支持加载GGUF格式模型
import os
import logging
from typing import Dict, Any, Optional
import time

# 尝试导入llama_cpp，如果失败则使用模拟实现
try:
    print("Loading llama_cpp module...")
    from llama_cpp import Llama
    HAS_LLAMA_CPP = True
except ImportError:
    HAS_LLAMA_CPP = False
    logging.warning("llama_cpp模块未安装，使用模拟实现")

# 模拟Llama客户端（当llama_cpp模块不可用时）
class MockLlama:
    def __init__(self, model_path, **kwargs):
        self.model_path = model_path
        self.kwargs = kwargs
    
    def create_completion(self, **kwargs):
        return {
            'choices': [{
                'text': "这是模拟的本地模型响应。由于llama_cpp模块未安装，无法加载实际模型。"
            }]
        }
    
    def __del__(self):
        pass

# 当llama_cpp模块不可用时，使用模拟实现
if not HAS_LLAMA_CPP:
    class Llama:
        def __init__(self, model_path, **kwargs):
            self.model_path = model_path
            self.kwargs = kwargs
        
        def create_completion(self, **kwargs):
            return {
                'choices': [{
                    'text': "这是模拟的本地模型响应。由于llama_cpp模块未安装，无法加载实际模型。"
                }]
            }

logger = logging.getLogger(__name__)

class LocalModelConfig:
    """本地模型配置类"""
    def __init__(self, name: str, model_path: str, max_tokens: int = 2048, temperature: float = 0.7):
        self.name = name
        self.model_path = model_path
        self.max_tokens = max_tokens
        self.temperature = temperature

class LocalModelClient:
    """本地大模型客户端，支持加载GGUF格式模型"""
    
    def __init__(self):
        self.models = {}
        self.current_model = None
        self.llama_instance = None
        # 请求统计
        self.request_count = 0
        self.last_request_time = 0
        
    def add_model(self, config: LocalModelConfig):
        """添加本地模型配置"""
        self.models[config.name] = config
        logger.info(f"添加本地模型配置: {config.name}")
        
    def set_current_model(self, model_name: str):
        """设置当前使用的本地模型"""
        if model_name in self.models:
            self.current_model = model_name
            config = self.models[model_name]
            
            # 检查模型文件是否存在
            if not os.path.exists(config.model_path):
                logger.error(f"模型文件不存在: {config.model_path}")
                return False
                
            try:
                # 加载模型
                logger.info(f"正在加载本地模型: {config.name} ({config.model_path})")
                self.llama_instance = Llama(
                    model_path=config.model_path,
                    n_ctx=config.max_tokens,
                    n_threads=os.cpu_count() or 4,
                    n_gpu_layers=-1  # 使用所有可用GPU层
                )
                logger.info(f"本地模型 {config.name} 加载成功")
                return True
            except Exception as e:
                logger.error(f"加载本地模型失败: {e}")
                return False
        else:
            logger.error(f"本地模型 {model_name} 不存在")
            return False
    
    def generate_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """生成本地模型响应"""
        if not self.current_model or not self.llama_instance:
            return {
                'success': False,
                'error': '未选择本地模型或模型未加载'
            }
        
        try:
            config = self.models[self.current_model]
            
            # 系统提示词（强化“COPILOT”属性）
            system_prompt = "你是一个二次元少女形象的人工智能协作系统,绮罗（Kirara）,活泼甜美而富有想象力，能够看到人类看不到的“闪闪发亮”的点,带有“二次元”的说话风格"
            
            # 准备完整的prompt
            full_prompt = f"{system_prompt}\n\n用户: {prompt}\n\n绮罗: "
            
            # 准备请求参数
            request_params = {
                'prompt': full_prompt,
                'max_tokens': kwargs.get('max_tokens', config.max_tokens),
                'temperature': kwargs.get('temperature', config.temperature),
                'top_p': kwargs.get('top_p', 0.9),
                'stop': ['\n', '###'],
                'echo': False
            }
            
            logger.info(f"本地模型 {self.current_model} 生成响应: {prompt[:50]}...")
            
            start_time = time.time()
            response = self.llama_instance.create_completion(**request_params)
            end_time = time.time()
            
            response_time = end_time - start_time
            response_text = response['choices'][0]['text'].strip()
            
            logger.info(f"本地模型 {self.current_model} 响应时间: {response_time:.2f}秒")
            logger.info(f"本地模型 {self.current_model} 响应: {response_text[:100]}...")
            
            return {
                'success': True,
                'response': response_text,
                'model': self.current_model,
                'response_time': response_time,
                'usage': {
                    'prompt_tokens': len(full_prompt.split()),
                    'completion_tokens': len(response_text.split()),
                    'total_tokens': len(full_prompt.split()) + len(response_text.split())
                }
            }
            
        except Exception as e:
            logger.error(f"本地模型生成响应时发生错误: {e}")
            return {
                'success': False,
                'error': f'本地模型生成响应失败: {str(e)}'
            }
    
    def get_available_models(self) -> list:
        """获取可用本地模型列表"""
        return list(self.models.keys())
    
    def get_model_info(self, model_name: str) -> Optional[Dict]:
        """获取本地模型信息"""
        if model_name in self.models:
            config = self.models[model_name]
            return {
                'name': config.name,
                'model_path': config.model_path,
                'max_tokens': config.max_tokens,
                'temperature': config.temperature
            }
        return None

# 创建全局本地模型客户端实例
local_model_client = LocalModelClient()

# 初始化本地模型配置
def init_local_models():
    """初始化本地模型配置"""
    # 检查models目录是否存在
    models_dir = os.path.join(os.path.dirname(__file__), '..', 'models')
    if not os.path.exists(models_dir):
        logger.warning(f"models目录不存在: {models_dir}")
        return local_model_client
        
    # 遍历models目录，查找GGUF格式的模型文件
    gguf_files = [f for f in os.listdir(models_dir) if f.endswith('.gguf')]
    
    for gguf_file in gguf_files:
        model_path = os.path.join(models_dir, gguf_file)
        model_name = os.path.splitext(gguf_file)[0]
        
        # 创建模型配置
        model_config = LocalModelConfig(
            name=model_name,
            model_path=model_path,
            max_tokens=2048,
            temperature=0.7
        )
        
        local_model_client.add_model(model_config)
        logger.info(f"添加本地模型: {model_name} ({model_path})")
    
    # 设置默认本地模型（如果有）
    if gguf_files:
        default_model = os.path.splitext(gguf_files[0])[0]
        local_model_client.set_current_model(default_model)
        logger.info(f"设置默认本地模型: {default_model}")
    
    logger.info("本地模型配置初始化完成")
    return local_model_client