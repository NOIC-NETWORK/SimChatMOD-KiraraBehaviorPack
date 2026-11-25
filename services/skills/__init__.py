import os
import sys

SKILLS_DIR = os.path.dirname(os.path.abspath(__file__))
if SKILLS_DIR not in sys.path:
    sys.path.insert(0, SKILLS_DIR)

from skills.skills import (
    BaseSkill,
    SkillRegistry,
    SkillExecutor,
    SkillManager,
    CustomSkillWrapper,
    get_skill_manager
)

from skills.readFile import ReadFileSkill, init_readFile_skill
from skills.screenshotRecognition import ScreenshotRecognitionSkill, init_screenshotRecognition_skill
from skills.areYouUnderTrouble import AreYouUnderTroubleSkill, init_areYouUnderTrouble_skill

__all__ = [
    'BaseSkill',
    'SkillRegistry',
    'SkillExecutor',
    'SkillManager',
    'CustomSkillWrapper',
    'get_skill_manager',
    'ReadFileSkill',
    'init_readFile_skill',
    'ScreenshotRecognitionSkill',
    'init_screenshotRecognition_skill',
    'AreYouUnderTroubleSkill',
    'init_areYouUnderTrouble_skill'
]