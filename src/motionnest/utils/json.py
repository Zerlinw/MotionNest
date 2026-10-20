"""宽松 JSON 解析：从模型文本中提取第一个完整 JSON 值。

模型偶尔会包裹 markdown 围栏或前后缀废话，这里统一兜底；
解析失败抛 ValueError，由 Agent 的重试循环捕获并回喂纠错。
"""

from __future__ import annotations

import json
import re
from typing import Any

_FENCE_RE = re.compile(r"^```(?:json|JSON)?\s*|\s*```$", re.MULTILINE)
_PAIRS = {"{": "}", "[": "]"}


def parse_json_loose(text: str) -> Any:
    cleaned = _FENCE_RE.sub("", text.strip()).strip()
    start = -1
    for index, char in enumerate(cleaned):
        if char in _PAIRS:
            start = index
            break
    if start < 0:
        raise ValueError(f"响应中未找到 JSON：{cleaned[:120]!r}")

    depth = 0
    in_string = False
    escape = False
    opener = ""
    for index in range(start, len(cleaned)):
        char = cleaned[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in _PAIRS:
            if depth == 0:
                opener = char
            depth += 1
        elif char in _PAIRS.values():
            depth -= 1
            if depth == 0:
                candidate = cleaned[start : index + 1]
                if char == _PAIRS[opener]:
                    return json.loads(candidate)
                raise ValueError("JSON 括号不匹配")
    raise ValueError("JSON 不完整（括号未闭合）")
