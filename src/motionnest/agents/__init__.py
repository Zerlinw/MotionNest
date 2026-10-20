"""Agent 业务层：只依赖 TaskRouter，不感知具体模型。

低成本档（deepseek-flash，全自动）：
    DataInterpreter / StoryboardAgent / Animator / Reviser
强模型档（deepseek-v4-pro 等，人工签发）：
    MusicDirector / CameraDesigner / FinalReviewer
"""

from .animator import Animator
from .base import BaseAgent
from .camera_designer import CameraDesigner
from .data_interpreter import DataInterpreter
from .final_reviewer import FinalReviewer
from .music_director import MusicDirector
from .reviser import Reviser
from .storyboard import StoryboardAgent

__all__ = [
    "Animator",
    "BaseAgent",
    "CameraDesigner",
    "DataInterpreter",
    "FinalReviewer",
    "MusicDirector",
    "Reviser",
    "StoryboardAgent",
]
