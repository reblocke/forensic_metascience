from __future__ import annotations

from research_project.randomization import build_csf_input, build_simdistr_input, parse_table1_long


def _table1_fixture() -> list[list[str]]:
    return [
        [
            "Characteristics",
            "Early ToD group (n = 105)",
            "Late ToD group (n = 105)",
            "P value",
        ],
        ["Age (year, median, range)", "61 (33-80)", "60 (34-77)", "0.53"],
        ["Sex (n, %)", "", "", ""],
        ["Male", "95 (90.5)", "95 (90.5)", "1.000"],
        ["Female", "10 (9.5)", "10 (9.5)", ""],
        ["Smoking history (n, %)", "", "", ""],
        ["Smoker", "84 (80.0)", "87 (82.9)", "0.590"],
        ["Never smoked", "21 (20.0)", "18 (17.1)", ""],
        ["PD-L1 TPS (n, %)", "", "", ""],
        ["<1%", "41 (39.0)", "47 (44.8)", "0.862"],
        ["1-49%", "31 (29.5)", "29 (27.5)", ""],
        [">=50%", "26 (24.8)", "22 (21.0)", ""],
        ["Unknown", "7 (6.7)", "7 (6.7)", ""],
        ["LIPI score (n, %)", "", "", ""],
        ["Low risk", "63 (60.0)", "58 (55.2)", "0.673"],
        ["Medium risk", "35 (33.3)", "37 (35.3)", ""],
        ["High risk", "7 (6.7)", "10 (9.5)", ""],
    ]


def test_parse_table1_long_extracts_expected_fields() -> None:
    table = _table1_fixture()
    parsed = parse_table1_long(table=table, trial_id="trial_x", source_page=3)

    assert not parsed.empty
    assert set(parsed["group"]) == {"early_tod", "late_tod"}
    assert set(parsed["trial_id"]) == {"trial_x"}

    age_rows = parsed[
        (parsed["variable"] == "Age (year, median, range)") & (parsed["level"] == "all")
    ]
    assert len(age_rows) == 2
    assert sorted(age_rows["value"].tolist()) == [60.0, 61.0]

    sex_rows = parsed[(parsed["variable"] == "Sex") & (parsed["level"] == "Male")]
    assert len(sex_rows) == 2
    assert sex_rows["reported_p"].dropna().iloc[0] == 1.0

    smoking_rows = parsed[
        (parsed["variable"] == "Smoking history") & (parsed["level"] == "Never smoked")
    ]
    assert len(smoking_rows) == 2
    assert smoking_rows["reported_p"].dropna().iloc[0] == 0.59


def test_build_package_inputs_shapes_and_columns() -> None:
    parsed = parse_table1_long(table=_table1_fixture(), trial_id="trial_x", source_page=3)
    simdistr_df = build_simdistr_input(parsed)
    csf_df = build_csf_input(parsed)

    assert not simdistr_df.empty
    assert not csf_df.empty
    assert list(simdistr_df.columns) == [
        "1_category",
        "2_outcome",
        "3_n_arm1",
        "4_n_arm2",
        "5_n_arm1_outcome",
        "6_n_arm2_outcome",
        "7_prop_arm1",
        "8_prop_arm2",
        "9_observed_pval",
    ]

    sex_rows = simdistr_df[simdistr_df["1_category"] == "Sex"]
    assert len(sex_rows) == 1
    assert sex_rows.iloc[0]["2_outcome"] == "Male"

    pdl1_rows = simdistr_df[simdistr_df["1_category"] == "PD-L1 TPS"]
    assert len(pdl1_rows) == 4

    assert csf_df["one_vs_rest"].all()
    assert set(csf_df["trial_id"]) == {"trial_x"}
