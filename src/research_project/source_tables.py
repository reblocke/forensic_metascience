"""Explicit, source-bound table inputs; no inferred numerical-method eligibility."""

from __future__ import annotations

import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pandas as pd

from research_project.inspect_sr.records import source_version_id
from research_project.randomization import (
    _build_categorical_row,
    _build_continuous_row,
    normalize_group_key,
    parse_count_percent_denominator,
    parse_group_header,
    parse_median_range,
    parse_p_value,
)


def _expand(rows: list) -> list[list[str]]:
    grid: dict[tuple[int, int], str] = {}
    for r, row in enumerate(rows):
        c = 0
        for text, rowspan, colspan in row:
            while (r, c) in grid:
                c += 1
            if not 1 <= rowspan <= 100 or not 1 <= colspan <= 100:
                raise ValueError("Invalid table span")
            for dr in range(rowspan):
                for dc in range(colspan):
                    if (r + dr, c + dc) in grid:
                        raise ValueError("Overlapping table cells")
                    grid[r + dr, c + dc] = text.strip()
            c += colspan
    width = max((c for _, c in grid), default=-1) + 1
    return [[grid.get((r, c), "") for c in range(width)] for r in range(len(rows))]


class _HTMLTables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = {}
        self.depth = 0
        self.rows = []
        self.row = None
        self.cell = None
        self.attrs = {}
        self.span = (1, 1)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table":
            self.depth += 1
            if self.depth == 1:
                self.attrs, self.rows = attrs, []
        elif self.depth == 1 and tag == "tr":
            self.row = []
        elif self.depth == 1 and tag in {"td", "th"}:
            self.cell = ""
            self.span = (int(attrs.get("rowspan", 1)), int(attrs.get("colspan", 1)))
        elif self.cell is not None and tag in {"br", "p"}:
            self.cell += "\n"

    def handle_data(self, data):
        if self.cell is not None:
            self.cell += data

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self.cell is not None and self.row is not None:
            self.row.append((self.cell, *self.span))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        elif tag == "table":
            if self.depth == 1 and self.attrs.get("aria-hidden") != "true":
                key = self.attrs.get("aria-labelledby") or self.attrs.get("id")
                if not key:
                    key = f"table-{len(self.tables) + 1}"
                locator = f"html:{key}"
                if locator in self.tables:
                    raise ValueError("Duplicate visible source-table identity")
                self.tables[locator] = _expand(self.rows)
            self.depth -= 1


def read_html_tables(text: str) -> dict[str, list[list[str]]]:
    """Retain visible table identities and expand explicit HTML cell spans."""
    parser = _HTMLTables()
    parser.feed(text)
    return parser.tables


def read_docx_tables(path: Path) -> dict[str, list[list[str]]]:
    """Read OOXML cells with explicit horizontal and vertical merge expansion."""
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    tables = {}
    for i, table in enumerate(root.findall(".//w:body/w:tbl", ns), 1):
        rows = []
        vertical = {}
        for row in table.findall("w:tr", ns):
            cells = []
            column = 0
            for cell in row.findall("w:tc", ns):
                merge = cell.find("w:tcPr/w:vMerge", ns)
                span = cell.find("w:tcPr/w:gridSpan", ns)
                width = int(span.get(f"{{{ns['w']}}}val")) if span is not None else 1
                paragraphs = [
                    "".join(p.itertext())
                    if not p.findall(".//w:t", ns)
                    else "".join(t.text or "" for t in p.findall(".//w:t", ns))
                    for p in cell.findall("w:p", ns)
                ]
                text = "\n".join(paragraphs).strip()
                if merge is not None and merge.get(f"{{{ns['w']}}}val") != "restart":
                    if column not in vertical or (text and text != vertical[column]):
                        raise ValueError("Unresolved DOCX vertical merge")
                    text = vertical[column]
                for c in range(column, column + width):
                    if merge is not None:
                        vertical[c] = text
                    else:
                        vertical.pop(c, None)
                cells.append((text, 1, width))
                column += width
            rows.append(cells)
        tables[f"docx:table={i}"] = _expand(rows)
    return tables


def load_table_input(path: Path, repo_root: Path) -> dict:
    """Validate hashes and re-extract every retained table before using annotations."""
    spec = json.loads(path.read_text(encoding="utf-8"))
    if spec.get("schema_version") != "source_table_input_v1":
        raise ValueError("Unsupported source-table input schema")
    root = repo_root.resolve()
    sources = {}
    for source in spec["sources"]:
        candidate = (root / source["path"]).resolve()
        if root not in candidate.parents or not candidate.is_file():
            raise ValueError("Source must be a repository-contained file")
        if hashlib.sha256(candidate.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError("Source hash mismatch")
        sid = source["source_id"]
        if sid in sources:
            raise ValueError("Duplicate source identity")
        if source["format"] == "html":
            tables = read_html_tables(candidate.read_text(encoding="utf-8"))
        elif source["format"] == "docx":
            tables = read_docx_tables(candidate)
        else:
            raise ValueError("Unsupported source-table format")
        source["source_version_id"] = source_version_id(sid, source["sha256"])
        sources[sid] = tables
    seen = set()
    for table in spec["tables"]:
        identity = table["source_id"], table["locator"]
        if identity in seen:
            raise ValueError("Repeated source-table identity")
        seen.add(identity)
        original = sources[table["source_id"]].get(table["locator"])
        if original != table["raw_rows"]:
            raise ValueError("Transcribed cells do not match original source cells")
    ids = [t["table_id"] for t in spec["tables"]]
    if len(set(ids)) != len(ids) or spec["baseline_table_id"] not in ids:
        raise ValueError("Invalid table identities")
    return spec


def parse_mapped_table(spec: dict, table_id: str) -> pd.DataFrame:
    """Normalize two explicitly mapped arms, retaining Total outside analysis rows."""
    table = next(t for t in spec["tables"] if t["table_id"] == table_id)
    raw = table["raw_rows"]
    mapping = table["column_map"]
    indexes = [v for v in mapping.values() if v is not None]
    if len(indexes) != len(set(indexes)) or any(
        type(v) is not int or v < 0 or v >= len(raw[0]) for v in indexes
    ):
        raise ValueError("Invalid or overlapping column mapping")
    for name in ("label", "arm_a", "arm_b"):
        if mapping.get(name) is None:
            raise ValueError("Missing required column mapping")
    header_n = table["header_rows"]
    if type(header_n) is not int or not 1 <= header_n < len(raw):
        raise ValueError("Invalid header row count")
    groups = {}
    for arm in ("arm_a", "arm_b"):
        header = " ".join(dict.fromkeys(row[mapping[arm]] for row in raw[:header_n]))
        if re.search(r"\b(total|overall)\b", header, re.I):
            raise ValueError("Total cannot be mapped as a treatment arm")
        groups[arm] = parse_group_header(header)
    if normalize_group_key(groups["arm_a"].label) == normalize_group_key(groups["arm_b"].label):
        raise ValueError("Treatment arm identities must differ")
    rows = []
    for index, cells in enumerate(raw[header_n:], header_n):
        label = cells[mapping["label"]].strip()
        kind = table["row_kinds"].get(str(index), "unknown")
        if kind == "section":
            continue
        if not label:
            raise ValueError("Analyzed rows require an explicit source label")
        if kind not in {"count_percent", "mean_sd", "median_iqr", "median_range", "unknown"}:
            raise ValueError("Unknown statistic kind")
        if kind == "mean_sd" and re.search(r"\bmedian\b", label, re.I):
            raise ValueError("A source median cannot be treated as a mean")
        pcol = mapping.get("p_value")
        p, p_raw, p_cmp = parse_p_value(cells[pcol] if pcol is not None else "")
        for arm, group in groups.items():
            value = cells[mapping[arm]]
            parse_status = "missing" if not value.strip() else "parsed"
            analysis_n = table.get("analysis_denominators", {}).get(str(index), {}).get(arm)
            if analysis_n is not None and (type(analysis_n) is not int or analysis_n <= 0):
                raise ValueError("Analysis denominator must be a positive integer")
            common = dict(
                trial_id=spec["trial_id"],
                variable_name=label,
                group_key=normalize_group_key(group.label),
                n_group=analysis_n or group.n,
                reported_p=p,
                reported_p_raw=p_raw,
                reported_p_comparator=p_cmp,
                raw_value=value,
                source_page=None,
                variable_order=index,
            )
            if kind == "count_percent":
                count, percent, explicit_n = parse_count_percent_denominator(value)
                if explicit_n is not None:
                    if analysis_n is not None and analysis_n != explicit_n:
                        raise ValueError("Conflicting analytic denominators")
                    analysis_n = explicit_n
                    common["n_group"] = explicit_n
                row = _build_categorical_row(
                    **common, level_name="all", count=count, percent=percent, level_order=0
                )
                row["statistic_kind"] = "count"
            else:
                center, low, high = parse_median_range(value)
                if kind.startswith("median") and value.strip():
                    if center is None or low is None or high is None:
                        parse_status = "unparsed_interval"
                    elif low > high or not low <= center <= high:
                        # Preserve the printed cell; do not silently repair malformed bounds.
                        parse_status = "invalid_interval"
                        low, high = None, None
                row = _build_continuous_row(**common, value=center, low=low, high=high)
                row["statistic_kind"] = "median" if kind.startswith("median") else "unknown"
                if kind == "mean_sd":
                    match = re.fullmatch(r"\s*([+-]?\d+(?:\.\d+)?)\s*±\s*(\d+(?:\.\d+)?)\s*", value)
                    if value.strip() and match is None:
                        raise ValueError("Unparsed mean/SD cell")
                    row.update(
                        var_type="continuous_mean_sd",
                        statistic_kind="arithmetic_mean",
                        value=float(match[1]) if match else None,
                        sd=float(match[2]) if match else None,
                        raw_statistic_value=match[1] if match else "",
                        sd_str=match[2] if match else "",
                        range_low=None,
                        range_high=None,
                    )
                elif kind == "unknown":
                    row.update(var_type="unknown", value=None, range_low=None, range_high=None)
                    parse_status = "unknown_statistic"
            row.update(
                randomized_n=group.n,
                parse_status=parse_status,
                analysis_n=analysis_n,
                statistic_label=kind,
                units=table.get("units", {}).get(str(index), "unknown"),
                source_id=table["source_id"],
                source_table=table_id,
                source_locator=f"{table['locator']}:row={index + 1}:column={mapping[arm] + 1}",
                extract_confidence="proposed_transcription",
                measurement_scale="unknown",
                raw_or_adjusted="unknown",
                weighting="unknown",
                imputation_status="unknown",
                transformation_status="unknown",
                eligibility_evidence="",
            )
            row["reported_p_source_locator"] = (
                f"{table['locator']}:row={index + 1}:column={pcol + 1}" if pcol is not None else ""
            )
            rows.append(row)
    if not rows:
        raise ValueError("Mapped table contains no analysis rows")
    return pd.DataFrame(rows)


def summary_rows(spec: dict) -> pd.DataFrame:
    """Export explicit mean/SD cells without inferring scale or analytic eligibility."""
    columns = [
        "trial_id",
        "source_pdf",
        "source_table",
        "source_page",
        "source_locator",
        "raw_value",
        "variable",
        "level",
        "group",
        "n",
        "x_str",
        "sd_str",
        "digits_x",
        "digits_sd",
        "statistic_kind",
        "analysis_n",
        "measurement_scale",
    ]
    sources = {s["source_id"]: s for s in spec["sources"]}
    output = []
    for table in spec["tables"]:
        if "column_map" not in table:
            continue
        parsed = parse_mapped_table(spec, table["table_id"])
        for row in parsed[parsed.var_type == "continuous_mean_sd"].to_dict("records"):
            x, sd = row["raw_statistic_value"], row["sd_str"]
            output.append(
                {
                    **row,
                    "source_pdf": Path(sources[table["source_id"]]["path"]).name,
                    "n": row["n_group"],
                    "x_str": x,
                    "sd_str": sd,
                    "digits_x": len(x.partition(".")[2]),
                    "digits_sd": len(sd.partition(".")[2]),
                }
            )
    return pd.DataFrame(output) if output else pd.DataFrame(columns=columns)
