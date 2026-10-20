"""数据加载与摘要：给模型看"目录"，而不是整表原文。

支持 CSV / JSON；摘要包含行列数、每列类型、空值、唯一值、数值范围与样例，
数据字典（口径、单位、来源）由用户提供，是管线的一等公民。
"""

from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path
from typing import Any

from ..core.schemas import ColumnSpec, ColumnSummary, DataDictionary, DataSummary
from ..exceptions import ConfigError

_DATE_RE = re.compile(r"^\d{4}[-/]\d{1,2}([-/]\d{1,2})?")


def load_table(path: Path) -> tuple[list[dict[str, Any]], DataSummary]:
    """加载 CSV/JSON 表，返回 (记录列表, 摘要)。"""
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"数据文件不存在：{path}")
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            records = [dict(row) for row in csv.DictReader(handle)]
    elif suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            for key in ("records", "data", "rows"):
                if isinstance(payload.get(key), list):
                    payload = payload[key]
                    break
        if not isinstance(payload, list) or not all(isinstance(r, dict) for r in payload):
            raise ConfigError("JSON 数据必须是对象数组，或包含 records/data/rows 数组的对象")
        records = payload
    else:
        raise ConfigError(f"不支持的数据格式：{suffix}（仅 .csv / .json）")
    if not records:
        raise ConfigError(f"数据文件为空：{path}")
    return records, summarize(records)


def load_dictionary(path: Path) -> DataDictionary:
    """加载数据字典（口径/单位/来源）。"""
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"数据字典不存在：{path}")
    try:
        return DataDictionary.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ConfigError(f"数据字典非法：{exc}") from exc


def _to_number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, str):
        text = value.strip().replace(",", "")
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _detect_dtype(values: list[Any]) -> str:
    non_null = [v for v in values if v not in (None, "")]
    if not non_null:
        return "text"
    if all(_to_number(v) is not None for v in non_null):
        return "number"
    if all(isinstance(v, str) and _DATE_RE.match(v.strip()) for v in non_null):
        return "date"
    if len(set(non_null)) <= max(10, len(non_null) // 2):
        return "category"
    return "text"


def summarize(records: list[dict[str, Any]]) -> DataSummary:
    columns: list[ColumnSummary] = []
    names = list(records[0].keys())
    for name in names:
        values = [record.get(name) for record in records]
        non_null = [v for v in values if v not in (None, "")]
        numbers = [n for n in (_to_number(v) for v in non_null) if n is not None]
        dtype = _detect_dtype(non_null)
        columns.append(
            ColumnSummary(
                name=name,
                dtype=dtype,
                nulls=len(values) - len(non_null),
                unique=len({str(v) for v in non_null}),
                min=min(numbers) if numbers and dtype == "number" else None,
                max=max(numbers) if numbers and dtype == "number" else None,
                sample=[str(v) for v in non_null[:3]],
            )
        )
    date_columns = [c.name for c in columns if c.dtype == "date"]
    date_range = ""
    if date_columns:
        name = date_columns[0]
        dates = sorted(str(record.get(name)) for record in records if record.get(name) not in (None, ""))
        if dates:
            date_range = f"{dates[0]} ~ {dates[-1]}"
    return DataSummary(rows=len(records), columns=columns, date_range=date_range)


def dictionary_from_summary(summary: DataSummary, source: str = "") -> DataDictionary:
    """无用户字典时生成默认字典（单位留空，交由数据门禁提醒补齐）。"""
    return DataDictionary(
        columns=[
            ColumnSpec(
                name=column.name,
                dtype=column.dtype,
                unit=None,
                description="",
                required=True,
            )
            for column in summary.columns
        ],
        source=source,
    )
