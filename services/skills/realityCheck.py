# shim — 旧路径兼容，realtyCheck 已迁 SimChat MOD
# 旧代码: from realityCheck import RealityCheckSkill
# 本 shim 让旧 import 继续工作，内部 facade 委托

import os, sys
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from simchat.loader.skill_manager_facade import get_skill_manager


class RealityCheckSkill(object):
    """兼容旧代码的 shim——execute/detect 委托到 ModLoader.call_tool('realityCheck', ...)。"""
    def __init__(self):
        self._manager = get_skill_manager()

    def execute(self, params):
        return self._manager.execute_skill("realityCheck", params or {})

    def detect(self, text):
        resp = self._manager.execute_skill("realityCheck", {"text": text})
        if isinstance(resp, dict) and resp.get("success"):
            return resp
        return resp if isinstance(resp, dict) else {}
