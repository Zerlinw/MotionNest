"""数据层：加载、摘要、校验。"""

from .loader import dictionary_from_summary, load_dictionary, load_table, summarize
from .validate import check_data

__all__ = ["check_data", "dictionary_from_summary", "load_dictionary", "load_table", "summarize"]
