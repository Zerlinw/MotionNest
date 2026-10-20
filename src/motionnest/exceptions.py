"""MotionNest 异常体系。"""

from __future__ import annotations


class MotionNestError(Exception):
    """所有 MotionNest 异常的基类。"""


class ConfigError(MotionNestError):
    """配置缺失或非法（models.yaml / router.yaml / project.json）。"""


class MissingApiKeyError(MotionNestError):
    """模型所需的环境变量密钥未配置。"""


class ModelUnavailableError(MotionNestError):
    """某任务在所有路由规则下都找不到可用模型。"""


class UnknownTaskError(MotionNestError):
    """向路由器请求了未登记的路由任务。"""


class HumanReviewRequired(MotionNestError):
    """强模型不可用且规则允许人工兜底时抛出，携带待人工处理的上下文。"""

    def __init__(self, task: str, reason: str, rule: object | None = None) -> None:
        self.task = task
        self.reason = reason
        self.rule = rule
        super().__init__(f"任务 {task} 需要人工处理：{reason}")


class SchemaValidationError(MotionNestError):
    """模型输出多次未通过 schema 校验。"""


class GateError(MotionNestError):
    """质量门禁未通过（默认阻止正式导出）。"""
