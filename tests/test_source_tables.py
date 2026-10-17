from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from research_project.source_tables import (
    load_table_input,
    parse_mapped_table,
    read_html_tables,
    summary_rows,
)


def fixture(tmp_path: Path, with_p: bool = False) -> tuple[Path, dict]:
    extra = '<th rowspan="2">P value</th>' if with_p else ""
    p = "<td>&lt;0.001</td>" if with_p else ""
    html = (
        '<table aria-labelledby="T1"><tr><th rowspan="2">Characteristic</th>'
        f"<th>Total</th><th>Combination</th><th>Monotherapy</th>{extra}</tr>"
        "<tr><th>n = 112</th><th>n = 55</th><th>n = 57</th></tr>"
        f"<tr><td>Outcome, n (%)</td><td>10</td><td>4 (7.3%)</td><td>6 (10.5%)</td>{p}</tr>"
        f"<tr><td>Score, median (IQR)</td><td>5 (3–7)</td><td>5 (3–7)</td><td></td>{p}</tr>"
        "<tr><td>BMI, mean ± SD</td><td>22.0 ± 5.0</td><td>23.0 ± 6.0</td>"
        f"<td>22.0 ± 4.0</td>{p}</tr>"
        '</table><table aria-hidden="true"><tr><td>duplicate</td></tr></table>'
    )
    source = tmp_path / "source.html"
    source.write_text(html)
    table = {
        "table_id": "T1",
        "source_id": "article",
        "locator": "html:T1",
        "header_rows": 2,
        "column_map": {
            "label": 0,
            "total": 1,
            "arm_a": 2,
            "arm_b": 3,
            "p_value": 4 if with_p else None,
        },
        "row_kinds": {"2": "count_percent", "3": "median_iqr", "4": "mean_sd"},
        "raw_rows": read_html_tables(html)["html:T1"],
    }
    spec = {
        "schema_version": "source_table_input_v1",
        "trial_id": "trial",
        "baseline_table_id": "T1",
        "sources": [
            {
                "source_id": "article",
                "path": "source.html",
                "format": "html",
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            }
        ],
        "tables": [table],
        "allocation": {"planned_ratio": None, "evidence": None},
    }
    path = tmp_path / "tables.json"
    path.write_text(json.dumps(spec))
    return path, spec


@pytest.mark.parametrize("with_p", [False, True])
def test_total_is_reconciliation_only_and_p_is_optional(tmp_path: Path, with_p: bool):
    path, _ = fixture(tmp_path, with_p)
    spec = load_table_input(path, tmp_path)
    result = parse_mapped_table(spec, "T1")
    assert set(result.group) == {"combination", "monotherapy"}
    assert set(result.n_group) == {55, 57}
    assert len(result) == 6
    assert result.source_page.isna().all()
    assert result.source_locator.str.contains("html:T1:row=").all()
    count = result[result.var_type == "categorical_count_percent"]
    assert count.value.tolist() == [4, 6]
    if with_p:
        assert count.reported_p_raw.tolist() == ["<0.001", "<0.001"]
    else:
        assert result.reported_p.isna().all()
    medians = result[result.statistic_kind == "median"]
    assert pd.isna(medians.iloc[1].value)
    assert medians.iloc[1].raw_value == ""
    means = summary_rows(spec)
    assert means.x_str.tolist() == ["23.0", "22.0"]
    assert means.sd_str.tolist() == ["6.0", "4.0"]
    assert means.digits_x.tolist() == [1, 1]
    assert means.analysis_n.isna().all()
    assert len(read_html_tables((tmp_path / "source.html").read_text())) == 1


def test_mapping_and_source_tampering_fail_closed(tmp_path: Path):
    path, spec = fixture(tmp_path)
    spec["tables"][0]["column_map"]["arm_a"] = 1
    with pytest.raises(ValueError, match="column|Total"):
        parse_mapped_table(spec, "T1")
    (tmp_path / "source.html").write_text("changed")
    with pytest.raises(ValueError, match="hash"):
        load_table_input(path, tmp_path)


def test_transcription_must_match_source_cells(tmp_path: Path):
    path, spec = fixture(tmp_path)
    spec["tables"][0]["raw_rows"][2][2] = "5 (9.1%)"
    path.write_text(json.dumps(spec))
    with pytest.raises(ValueError, match="cells"):
        load_table_input(path, tmp_path)


def test_available_case_denominator_does_not_change_randomized_count(tmp_path: Path):
    path, spec = fixture(tmp_path)
    spec["tables"][0]["analysis_denominators"] = {"2": {"arm_a": 50, "arm_b": 52}}
    result = parse_mapped_table(spec, "T1")
    first = result.iloc[0]
    assert first.n_group == 50
    assert first.randomized_n == 55
    assert first.analysis_n == 50


def test_median_cannot_be_declared_mean(tmp_path: Path):
    _, spec = fixture(tmp_path)
    spec["tables"][0]["row_kinds"]["3"] = "mean_sd"
    with pytest.raises(ValueError, match="median"):
        parse_mapped_table(spec, "T1")


def test_repeated_visible_identity_is_rejected():
    html = '<table id="same"><tr><td>x</td></tr></table>'
    with pytest.raises(ValueError, match="Duplicate visible"):
        read_html_tables(html + html)


def test_docx_vertical_merge_retains_header_and_column_identity(tmp_path):
    from zipfile import ZipFile

    from research_project.source_tables import read_docx_tables

    xml = """<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:body><w:tbl><w:tr>
    <w:tc><w:tcPr><w:vMerge w:val="restart"/></w:tcPr><w:p><w:r>
    <w:t>Characteristic</w:t></w:r></w:p></w:tc>
    <w:tc><w:p><w:r><w:t>Group A</w:t></w:r></w:p></w:tc></w:tr>
    <w:tr><w:tc><w:tcPr><w:vMerge/></w:tcPr><w:p/></w:tc>
    <w:tc><w:p><w:r><w:t>n=10</w:t></w:r></w:p></w:tc></w:tr>
    </w:tbl></w:body></w:document>"""
    path = tmp_path / "table.docx"
    with ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", xml)
    assert read_docx_tables(path)["docx:table=1"] == [
        ["Characteristic", "Group A"],
        ["Characteristic", "n=10"],
    ]


@pytest.mark.parametrize("text, expected", [("", ""), ("Randomized in a 1:1 ratio.", "1:1")])
def test_planned_ratio_is_source_supported_not_observed_counts(tmp_path, text, expected):
    import runpy

    module = runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "scripts/extract_randomization_table1.py")
    )
    _, spec = fixture(tmp_path)
    parsed = parse_mapped_table(spec, "T1")
    metadata = module["_derive_metadata"]("trial", parsed, [], [text]).iloc[0]
    assert metadata.planned_allocation_ratio == expected
    assert metadata.allocation_ratio == expected
    assert (metadata.observed_randomized_n_a, metadata.observed_randomized_n_b) == (55, 57)
