# DEPRECATED — P2.4 起 skill 由 SimChat MOD 体系提供
# 保留本文件只为旧 import 路径兼容（Galax/JRVS 零改动）

import os, sys

# 确保能从任意宿主位置 import simchat.loader
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:
    from simchat.loader.skill_manager_facade import (
        SkillManager, get_skill_manager,
        init_readFile_skill, init_screenshotRecognition_skill,
        init_areYouUnderTrouble_skill, init_webSearch_skill,
        init_realityCheck_skill,
    )
    from simchat.sdk.python.simchat_mod import BaseSkill
except ImportError:
    # fallback：simchat 未初始化时的空壳
    class SkillManager:
        def get_registry(self): return None
        def execute_skill(self, *a, **kw): return {}
        def list_all_skills(self): return []
    def get_skill_manager(): return SkillManager()
    def init_readFile_skill(): pass
    def init_screenshotRecognition_skill(): pass
    def init_areYouUnderTrouble_skill(): pass
    def init_webSearch_skill(): pass
    def init_realityCheck_skill(): pass
    class BaseSkill: pass

__all__ = ['BaseSkill', 'SkillManager', 'get_skill_manager',
           'init_readFile_skill', 'init_screenshotRecognition_skill',
           'init_areYouUnderTrouble_skill', 'init_webSearch_skill', 'init_realityCheck_skill']
