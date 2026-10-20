"""数据层测试：加载、类型推断、数据门禁。"""

from __future__ import annotations

from motionnest.core.schemas import ColumnSpec, DataDictionary
from motionnest.data.loader import load_table
from motionnest.qa.gates import data_gate


def _write_csv(tmp_path):
    csv_path = tmp_path / "t.csv"
    csv_path.write_text(
        "month,new_users,retained_d30\n"
        "2026-01,1200,402\n"
        "2026-02,1350,480\n"
        "2026-03,1180,398\n",
        encoding="utf-8",
    )
    return csv_path


def test_load_csv_and_summarize(tmp_path):
    records, summary = load_table(_write_csv(tmp_path))
    assert len(records) == 3
    assert summary.rows == 3
    by_name = {c.name: c for c in summary.columns}
    assert by_name["month"].dtype == "date"
    assert by_name["new_users"].dtype == "number"
    assert by_name["new_users"].min == 1180
    assert by_name["new_users"].max == 1350


def test_load_json_records(tmp_path):
    path = tmp_path / "t.json"
    path.write_text('[{"a": 1}, {"a": 2}]', encoding="utf-8")
    records, summary = load_table(path)
    assert summary.rows == 2
    assert summary.columns[0].dtype == "number"


def test_data_gate_blocks_missing_dictionary_column(tmp_path):
    _, summary = load_table(_write_csv(tmp_path))
    dictionary = DataDictionary(
        columns=[ColumnSpec(name="new_users", dtype="number", unit="人")],
        source="test",
    )
    gate = data_gate(summary, dictionary)
    assert gate.passed is False
    assert any("month" in error for error in gate.errors)


def test_data_gate_blocks_missing_source(tmp_path):
    _, summary = load_table(_write_csv(tmp_path))
    dictionary = DataDictionary(
        columns=[
            ColumnSpec(name="month", dtype="date"),
            ColumnSpec(name="new_users", dtype="number", unit="人"),
            ColumnSpec(name="retained_d30", dtype="number", unit="人"),
        ],
        source="",
    )
    gate = data_gate(summary, dictionary)
    assert gate.passed is False
    assert any("source" in error for error in gate.errors)


def test_data_gate_passes_with_full_dictionary(tmp_path):
    _, summary = load_table(_write_csv(tmp_path))
    dictionary = DataDictionary(
        columns=[
            ColumnSpec(name="month", dtype="date"),
            ColumnSpec(name="new_users", dtype="number", unit="人"),
            ColumnSpec(name="retained_d30", dtype="number", unit="人"),
        ],
        timezone="Asia/Shanghai",
        source="test",
    )
    gate = data_gate(summary, dictionary)
    assert gate.passed is True
    assert gate.errors == []
