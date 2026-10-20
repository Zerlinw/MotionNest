"""数据门禁细节：缺失、类型、单位、时区、来源。

规则哲学：数字、来源和口径错误是**阻塞发布**的问题，
必须在生成任何画面之前拦住，而不是让 LLM 在提示词里"注意一下"。
"""

from __future__ import annotations

from ..core.schemas import DataDictionary, DataSummary


def check_data(summary: DataSummary, dictionary: DataDictionary) -> tuple[list[str], list[str]]:
    """返回 (errors, warnings)。errors 非空即阻塞。"""
    errors: list[str] = []
    warnings: list[str] = []

    dict_columns = {spec.name: spec for spec in dictionary.columns}
    summary_columns = {column.name: column for column in summary.columns}

    # 1. 字典覆盖度：数据列必须都在字典中有声明
    for name in summary_columns:
        if name not in dict_columns:
            errors.append(f"列 {name!r} 未在数据字典中声明（口径未知，禁止生成）")

    # 2. 字典中声明但数据里没有的列
    for name in dict_columns:
        if name not in summary_columns:
            errors.append(f"字典声明的列 {name!r} 在数据中不存在")

    # 3. 逐列校验：必填、空值、数值列单位
    for name, column in summary_columns.items():
        spec = dict_columns.get(name)
        if spec is None:
            continue
        if spec.required and column.nulls == summary.rows:
            errors.append(f"必填列 {name!r} 全部为空")
        elif spec.required and column.nulls > 0:
            warnings.append(f"列 {name!r} 存在 {column.nulls} 个空值，聚合前需确认处理方式")
        if column.dtype == "number" and not spec.unit:
            warnings.append(f"数值列 {name!r} 未声明单位（单位缺失可能导致图元误读）")
        if column.dtype != spec.dtype and spec.dtype != "text":
            warnings.append(f"列 {name!r} 推断类型 {column.dtype} 与字典声明 {spec.dtype} 不一致")

    # 4. 行数
    if summary.rows < 2:
        errors.append(f"数据行数过少（{summary.rows}），不足以支撑叙事")

    # 5. 来源与时区
    if not dictionary.source.strip():
        errors.append("数据字典缺少 source（来源），无法进入引用清单")
    if dictionary.timezone in ("", "local") and any(c.dtype == "date" for c in summary_columns.values()):
        warnings.append("含日期列但时区为 local，跨期比较前请显式声明时区")

    return errors, warnings
