"""Explicit, operator-attested synthesis accounting; no inferred groups or qualification."""

from __future__ import annotations

import copy
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

from research_project.inspect_sr.records import evidence_id
from research_project.medical_review.audit import recorded_artifact, validate_run_artifacts
from research_project.medical_review.evaluation import _exact, _identifier
from research_project.medical_review.evaluation_assessment import (
    PERSON_FIELDS,
    WORKSPACES,
    _person,
    _validate_views,
    _write,
    load_assessment,
)
from research_project.medical_review.evaluation_assessment import (
    _code_sources as assessment_code_sources,
)
from research_project.medical_review.evaluation_candidates import _snapshot
from research_project.medical_review.evaluation_packets import (
    DEFAULT_PACKET_BYTES,
    DEFAULT_TOTAL_BYTES,
    MAX_FILES,
    MAX_PACKETS,
    _freeze_directory,
    _json_bytes,
)
from research_project.medical_review.evaluation_reference import _text, _unique_strings
from research_project.medical_review.records import (
    PRIVATE_RUNS,
    PRIVATE_SOURCES,
    content_hash,
    identity,
    parse_json,
    private_path,
    read_json,
    write_json,
)
from research_project.run_manifest import create_run, sha256_file, update_run

INPUT_FIELDS = {
    "schema_version",
    "synthesis_packets_id",
    "supersedes_run_reference",
    "assessors",
    "adjudication",
}
GROUP_FIELDS = {
    "group_id",
    "reviewer_item_ids",
    "synthesis_item_ids",
    "conflicting_interpretations",
    "rationale",
}
ITEM_FIELDS = {
    "item_id",
    "group_id",
    "disposition",
    "distorted",
    "error_stage",
    "evidence",
    "critical_caveats",
    "rationale",
}
ADJUDICATION_FIELDS = ITEM_FIELDS | {"assessor_ids", "assessor_shortfall_reason"}
ERROR_STAGES = {
    "source_extraction",
    "study_reconstruction",
    "reasoning",
    "retrieval",
    "numerical_execution",
    "report_synthesis",
    "unknown",
    "not_applicable",
}


def _code_sources() -> dict[str, Path]:
    return {**assessment_code_sources(), "evaluation_synthesis.py": Path(__file__)}


def _specifications(repo: Path, loaded: dict[str, Any]):
    parent = loaded["packets"]
    candidates = parent["candidates"]["candidates"]
    candidate_map = {c["candidate_id"]: c for c in candidates["candidates"]}
    item_map = {i["item_id"]: i for i in parent["packets"]["items"]}
    views, items, literals, files = [], [], {}, {}
    total, file_count = 0, 0
    if len(parent["packets"]["views"]) > MAX_PACKETS:
        raise ValueError("Synthesis view count exceeds 1024; split explicitly.")
    for view in parent["packets"]["views"]:
        root = view["workspace_reference"]
        original = read_json(
            recorded_artifact(
                repo, parent["run_root"], parent["manifest"], root + "/assessment_packet.json"
            )
        )
        outputs, scopes = [], []
        output_map, attempt_map = {}, {}
        for attempt in candidates["attempts"]:
            if attempt["packet_id"] != view["packet_id"]:
                continue
            scope_id = identity(
                "synthesisattempt",
                {
                    "record": candidates["record_id"],
                    "attempt": attempt["attempt_id"],
                },
            )
            reviewer_outputs, synthesis_outputs = [], []
            for output in attempt["outputs"]:
                output_id = identity(
                    "synthesisoutput",
                    {
                        "record": candidates["record_id"],
                        "attempt": attempt["attempt_id"],
                        "output": output["output_id"],
                    },
                )
                output_map[(attempt["attempt_id"], output["output_id"])] = output_id
                (reviewer_outputs if output["stage"] == "reviewer" else synthesis_outputs).append(
                    output_id
                )
                outputs.append(
                    {
                        "output_scope_id": output_id,
                        "attempt_scope_id": scope_id,
                        "stage_role": "reviewer_input"
                        if output["stage"] == "reviewer"
                        else "synthesis_output",
                        "reported_run_status": output["reported_run_status"],
                        "summary": copy.deepcopy(output["original_summary"]),
                        "notes": copy.deepcopy(output["original_notes"]),
                    }
                )
            complete = bool(reviewer_outputs and synthesis_outputs) and (
                attempt["status"] == "completed"
                and all(o["reported_run_status"] == "ok" for o in attempt["outputs"])
            )
            attempt_map[attempt["attempt_id"]] = (scope_id, complete)
            scopes.append(
                {
                    "attempt_scope_id": scope_id,
                    "reviewer_output_scope_ids": reviewer_outputs,
                    "synthesis_output_scope_ids": synthesis_outputs,
                    "declared_pair_complete": complete,
                }
            )
        output_contexts = {o["output_scope_id"]: o for o in outputs}
        paired_items = []
        for row in original["items"]:
            item = item_map[row["item_id"]]
            candidate = candidate_map[item["candidate_id"]]
            scope, complete = attempt_map[item["attempt_id"]]
            output_id = output_map[(item["attempt_id"], candidate["output_id"])]
            paired_items.append(
                {
                    **copy.deepcopy(row),
                    "attempt_scope_id": scope,
                    "output_scope_id": output_id,
                    "stage_role": "reviewer_input"
                    if item["stage"] == "reviewer"
                    else "synthesis_output",
                }
            )
            context = output_contexts[output_id]
            items.append(
                {
                    **copy.deepcopy(item),
                    "attempt_scope_id": scope,
                    "output_scope_id": output_id,
                    "declared_pair_complete": complete,
                    "quote_material": {
                        "finding": copy.deepcopy(row["finding"]),
                        "output_context": {
                            "summary": context["summary"],
                            "notes": context["notes"],
                        },
                    },
                }
            )
        payload = {
            "schema_version": "medical_evaluation_synthesis_view_v1",
            "view_id": view["view_id"],
            "sources": original["sources"],
            "reviewer_source_version_ids": original["reviewer_source_version_ids"],
            "items": paired_items,
            "outputs": outputs,
            "comparison_scopes": scopes,
            "source_fidelity_verified": False,
            "review_coverage_available": False,
            "official_assessment": None,
            "limitations": [
                "Stage/status declarations do not prove execution or complete review coverage.",
                "Metadata removal cannot prove blinding; "
                "source access, style and stages may reveal origin.",
                "Missing stages are unavailable, not zero loss or a clean paper.",
            ],
        }
        raw = _json_bytes(payload)
        literals[root + "/synthesis_packet.json"] = raw
        receipts = [
            copy.deepcopy(r) for r in view["files"] if r["path"] != "assessment_packet.json"
        ]
        for receipt in receipts:
            reference = root + "/" + receipt["path"]
            files[reference] = recorded_artifact(
                repo, parent["run_root"], parent["manifest"], reference
            )
        receipts.append(
            {
                "path": "synthesis_packet.json",
                "sha256": hashlib.sha256(raw).hexdigest(),
                "byte_count": len(raw),
            }
        )
        size = sum(r["byte_count"] for r in receipts)
        total += size
        file_count += len(receipts)
        if size > DEFAULT_PACKET_BYTES or total > DEFAULT_TOTAL_BYTES or file_count > MAX_FILES:
            raise ValueError("Synthesis packet limits exceeded; split without truncation.")
        views.append({**copy.deepcopy(view), "files": receipts, "comparison_scopes": scopes})
    record = {
        "schema_version": "medical_evaluation_synthesis_packets_v1",
        "assessment_record_id": loaded["assessment"]["record_id"],
        "assessment_packets_id": parent["packets"]["record_id"],
        "views": views,
        "items": items,
        "blinding_verified": False,
        "blinding_scope": "metadata_removed_stage_content_preserved_operator_attestation_required",
        "medical_performance_validated": False,
        "official_assessment": None,
    }
    record["record_id"] = identity("synthesispackets", record)
    _json_bytes(record)
    return record, literals, files


def _start(repo: Path, parent: Path, stage: str, record: dict[str, Any], raw: bytes | None = None):
    parent_hash = sha256_file(parent / "run_manifest.json")
    code_sources = _code_sources()
    code = {k: p.read_bytes() for k, p in code_sources.items()}
    run, manifest = create_run(
        repo_root=repo,
        output_root=PRIVATE_RUNS,
        study_id=read_json(parent / "run_manifest.json")["study_id"],
        categories=["medical_evaluation"],
        config_path=parent / "run_manifest.json",
        input_paths=[parent / "run_manifest.json"],
        settings={
            "medical_evaluation_synthesis_stage": stage,
            "parent_run_reference": str(parent.relative_to(repo)),
            "parent_manifest_sha256": parent_hash,
            "record_sha256": content_hash(record),
            "raw_sha256": hashlib.sha256(raw).hexdigest() if raw is not None else None,
            "code_sha256": content_hash(
                {k: hashlib.sha256(v).hexdigest() for k, v in code.items()}
            ),
            "offline": True,
            "allow_llm": False,
            "allow_web_search": False,
        },
    )
    return run, manifest, parent_hash, code_sources, code


def _load_stage(repo: Path, run: Path, stage: str):
    manifest = validate_run_artifacts(repo, run)
    settings = manifest["effective_settings"]
    if (
        manifest["status"] != "completed"
        or settings.get("medical_evaluation_synthesis_stage") != stage
    ):
        raise ValueError("Synthesis stage is not successfully completed.")
    parent = private_path(repo, Path(settings["parent_run_reference"]), PRIVATE_RUNS)
    if sha256_file(parent / "run_manifest.json") != settings["parent_manifest_sha256"]:
        raise ValueError("Synthesis parent manifest changed.")
    archived = {
        k: sha256_file(
            recorded_artifact(repo, run, manifest, "generated/medical_evaluation/code/" + k)
        )
        for k in _code_sources()
    }
    if content_hash(archived) != settings["code_sha256"]:
        raise ValueError("Synthesis code archive changed.")
    return manifest, settings, parent


def prepare_synthesis_packets(repo_root: Path, assessment_run: Path) -> Path:
    repo = repo_root.resolve()
    parent = private_path(repo, assessment_run, PRIVATE_RUNS)
    record, literals, files = _specifications(repo, load_assessment(repo, parent))
    run, manifest, parent_hash, code_sources, code = _start(repo, parent, "packets", record)
    try:
        for name, value in code.items():
            _write(run, manifest, "generated/medical_evaluation/code/" + name, value)
        total = 0
        for view in record["views"]:
            packet_bytes = 0
            for item in view["files"]:
                reference = view["workspace_reference"] + "/" + item["path"]
                path = run / reference
                path.parent.mkdir(parents=True, exist_ok=True)
                if reference in literals:
                    _write(run, manifest, reference, literals[reference])
                    packet_bytes += len(literals[reference])
                    total += len(literals[reference])
                else:
                    with files[reference].open("rb") as incoming, path.open("xb") as outgoing:
                        for chunk in iter(lambda: incoming.read(128 * 1024), b""):
                            packet_bytes += len(chunk)
                            total += len(chunk)
                            if packet_bytes > DEFAULT_PACKET_BYTES or total > DEFAULT_TOTAL_BYTES:
                                raise ValueError("Synthesis streaming byte limit exceeded.")
                            outgoing.write(chunk)
                    update_run(manifest, artifact=str(path))
                if packet_bytes > DEFAULT_PACKET_BYTES or total > DEFAULT_TOTAL_BYTES:
                    raise ValueError("Synthesis literal byte limit exceeded.")
                if path.stat().st_size != item["byte_count"] or sha256_file(path) != item["sha256"]:
                    raise ValueError("Synthesis packet bytes changed while copying.")
                path.chmod(0o444)
            _freeze_directory(run / view["workspace_reference"])
        _freeze_directory(run / WORKSPACES)
        if (
            sha256_file(parent / "run_manifest.json") != parent_hash
            or _specifications(repo, load_assessment(repo, parent))[0] != record
            or any(code_sources[k].read_bytes() != v for k, v in code.items())
        ):
            raise ValueError("Synthesis assessment/source/code changed while preparing.")
        _validate_views(repo, run, read_json(manifest), record)
        path = run / "processed/medical_evaluation/synthesis_packets.json"
        write_json(path, record)
        update_run(manifest, artifact=str(path))
        update_run(manifest, stage="packets", status="completed")
        update_run(manifest, status="completed")
    except Exception as error:
        update_run(manifest, status="failed", error=str(error))
        raise
    return run


def load_synthesis_packets(repo_root: Path, run_path: Path) -> dict[str, Any]:
    repo = repo_root.resolve()
    run = private_path(repo, run_path, PRIVATE_RUNS)
    manifest, settings, parent = _load_stage(repo, run, "packets")
    loaded = load_assessment(repo, parent)
    record = read_json(
        recorded_artifact(
            repo, run, manifest, "processed/medical_evaluation/synthesis_packets.json"
        )
    )
    if (
        content_hash(record) != settings["record_sha256"]
        or _specifications(repo, loaded)[0] != record
    ):
        raise ValueError("Synthesis packet assessment/source/semantic binding changed.")
    _validate_views(repo, run, manifest, record)
    return {"run_root": run, "manifest": manifest, "assessment": loaded, "packets": record}


def _strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)


def _quote(quote: Any, item_ids: list[str], items: dict[str, Any]) -> None:
    _text(quote, "synthesis quote")
    if not any(
        quote in text for key in item_ids for text in _strings(items[key]["quote_material"])
    ):
        raise ValueError("Synthesis quote is absent from its explicitly linked supplied artifact.")


def _groups(person: dict[str, Any], expected: set[str], items: dict[str, Any]):
    if not isinstance(person["groups"], list):
        raise ValueError("Synthesis groups require an explicit array.")
    groups, membership = {}, {}
    for row in person["groups"]:
        _exact(row, GROUP_FIELDS, "synthesis group")
        _identifier(row["group_id"], "group_id")
        if row["group_id"] in groups:
            raise ValueError("Duplicate synthesis group ID.")
        _text(row["rationale"], "group rationale")
        _unique_strings(row["conflicting_interpretations"], "conflicting interpretations")
        for field, stage in (
            ("reviewer_item_ids", "reviewer"),
            ("synthesis_item_ids", "synthesis"),
        ):
            _unique_strings(row[field], "group members", nonempty=True)
            for key in row[field]:
                if key not in expected or key in membership or items[key]["stage"] != stage:
                    raise ValueError("Unknown, duplicate or wrong-stage synthesis group member.")
                membership[key] = row["group_id"]
        members = row["reviewer_item_ids"] + row["synthesis_item_ids"]
        scopes = {(items[key]["packet_id"], items[key]["attempt_id"]) for key in members}
        if len(scopes) != 1:
            raise ValueError("Synthesis group crosses a packet or attempt source scope.")
        groups[row["group_id"]] = copy.deepcopy(row)
    return groups, membership


def _evidence(row: dict[str, Any], item: dict[str, Any], views: dict[str, Any]):
    values = row["evidence"]
    if not isinstance(values, list) or (
        not values and row["disposition"] not in {"unavailable", "unresolved"}
    ):
        raise ValueError("Resolved synthesis accounting requires explicit source evidence.")
    versions = set(views[item["view_id"]]["source_version_ids"])
    normalized, seen = [], set()
    for value in values:
        _exact(value, {"source_version_id", "locator", "raw_value"}, "synthesis source evidence")
        if value["source_version_id"] not in versions:
            raise ValueError("Synthesis evidence is outside the item case source scope.")
        _text(value["locator"], "source locator")
        _text(value["raw_value"], "source quote")
        key = evidence_id(
            value["source_version_id"],
            value["locator"],
            value["raw_value"],
            "human_source_review",
            "1",
        )
        if key in seen:
            raise ValueError("Duplicate synthesis source evidence.")
        seen.add(key)
        normalized.append(
            {
                **copy.deepcopy(value),
                "evidence_id": key,
                "verification": "operator_attested_source_review",
            }
        )
    return normalized


def _rows(
    person: dict[str, Any],
    expected: set[str],
    items: dict[str, Any],
    views: dict[str, Any],
    *,
    adjudicated: bool,
):
    groups, membership = _groups(person, expected, items)
    if not isinstance(person["judgments"], list):
        raise ValueError("Synthesis judgments require an explicit array.")
    judged, rows = set(), []
    for row in person["judgments"]:
        _exact(row, ADJUDICATION_FIELDS if adjudicated else ITEM_FIELDS, "synthesis item judgment")
        key = row["item_id"]
        if key not in expected or key in judged:
            raise ValueError("Unknown or duplicate synthesis item judgment.")
        judged.add(key)
        item = items[key]
        if row["group_id"] != membership.get(key):
            raise ValueError("Synthesis item/group membership is incomplete or conflicting.")
        group = groups.get(row["group_id"])
        allowed = (
            {
                "displayed",
                "grouped",
                "dismissed",
                "optional",
                "unresolved",
                "deferred",
                "lost",
                "unavailable",
            }
            if item["stage"] == "reviewer"
            else {"mapped", "new_in_synthesis", "unresolved", "unavailable"}
        )
        if row["disposition"] not in allowed:
            raise ValueError("Unsupported synthesis item disposition for its stage.")
        if row["disposition"] in {"displayed", "grouped", "mapped"} and group is None:
            raise ValueError("Displayed/grouped/mapped synthesis items require explicit members.")
        if (
            row["disposition"]
            in {"dismissed", "optional", "deferred", "lost", "unavailable", "new_in_synthesis"}
            and group is not None
        ):
            raise ValueError("Unmapped synthesis dispositions cannot retain a group.")
        if group is not None and row["disposition"] in {"displayed", "grouped"}:
            grouped = len(group["reviewer_item_ids"]) > 1
            if grouped != (row["disposition"] == "grouped"):
                raise ValueError(
                    "Displayed/grouped disposition conflicts with explicit source count."
                )
        if (
            row["disposition"] in {"lost", "new_in_synthesis"}
            and not item["declared_pair_complete"]
        ):
            raise ValueError("Loss/newness requires an explicitly declared completed stage pair.")
        if row["distorted"] is not None and type(row["distorted"]) is not bool:
            raise ValueError("Synthesis distortion must be an explicit boolean or null.")
        if row["distorted"] is True and group is None:
            raise ValueError("Distortion requires an explicit linked output group.")
        if row["error_stage"] not in ERROR_STAGES:
            raise ValueError("Unsupported synthesis error stage.")
        _text(row["rationale"], "synthesis judgment rationale")
        if not isinstance(row["critical_caveats"], list):
            raise ValueError("Critical caveats require an explicit array.")
        if item["stage"] != "reviewer" and row["critical_caveats"]:
            raise ValueError("Critical input caveats belong to their original reviewer item.")
        if row["disposition"] == "unavailable" and (
            row["distorted"] is not None or row["critical_caveats"]
        ):
            raise ValueError("Unavailable synthesis cannot claim assessed distortion or caveats.")
        quotes = set()
        for caveat in row["critical_caveats"]:
            _exact(
                caveat, {"input_quote", "output_quote", "status", "rationale"}, "critical caveat"
            )
            _quote(caveat["input_quote"], [key], items)
            if caveat["input_quote"] in quotes:
                raise ValueError("Duplicate critical input caveat.")
            quotes.add(caveat["input_quote"])
            _text(caveat["rationale"], "critical caveat rationale")
            if caveat["status"] not in {"preserved", "lost", "distorted", "unresolved"}:
                raise ValueError("Unsupported critical caveat disposition.")
            if caveat["status"] == "lost" and not item["declared_pair_complete"]:
                raise ValueError(
                    "Caveat loss requires an explicitly declared completed stage pair."
                )
            if caveat["status"] in {"preserved", "distorted"} and caveat["output_quote"] is None:
                raise ValueError("Preserved/distorted caveats require an explicit output quote.")
            if caveat["status"] == "lost" and caveat["output_quote"] is not None:
                raise ValueError("A lost caveat cannot declare a retained output quote.")
            if caveat["output_quote"] is not None:
                if group is None:
                    raise ValueError("A caveat output quote requires explicit synthesis members.")
                _quote(caveat["output_quote"], group["synthesis_item_ids"], items)
            if caveat["status"] == "distorted" and row["distorted"] is not True:
                raise ValueError("A distorted caveat requires an explicit item distortion flag.")
        rows.append({**copy.deepcopy(row), "evidence": _evidence(row, item, views)})
    if judged != expected:
        raise ValueError(
            "Synthesis judgments must account for every supplied item in reviewed views."
        )
    return list(groups.values()), rows


def validate_synthesis(
    loaded: dict[str, Any], data: Any, previous: dict[str, Any] | None = None
) -> dict[str, Any]:
    _exact(data, INPUT_FIELDS, "synthesis input")
    if (
        data["schema_version"] != "medical_evaluation_synthesis_input_v1"
        or data["synthesis_packets_id"] != loaded["packets"]["record_id"]
    ):
        raise ValueError("Synthesis input schema/packet identity mismatch.")
    if (data["supersedes_run_reference"] is None) != (previous is None):
        raise ValueError("Synthesis supersession requires its explicit validated predecessor.")
    views = {v["view_id"]: v for v in loaded["packets"]["views"]}
    items = {i["item_id"]: i for i in loaded["packets"]["items"]}
    if not isinstance(data["assessors"], list) or not data["assessors"]:
        raise ValueError("Synthesis assessment needs explicit human assessors.")
    assessors, observations, ids, people = [], {}, set(), set()
    for person in data["assessors"]:
        _exact(person, PERSON_FIELDS | {"groups", "assessor_id"}, "synthesis assessor")
        _identifier(person["assessor_id"], "assessor_id")
        if person["assessor_id"] in ids or person["human_identity"] in people:
            raise ValueError("Duplicate synthesis assessor identity.")
        ids.add(person["assessor_id"])
        people.add(person["human_identity"])
        expected = _person(person, views)
        groups, rows = _rows(person, expected, items, views, adjudicated=False)
        assessors.append({**copy.deepcopy(person), "groups": groups, "judgments": rows})
        for row in rows:
            observations.setdefault(row["item_id"], set()).add(person["assessor_id"])
    adjud = data["adjudication"]
    _exact(adjud, PERSON_FIELDS | {"groups"}, "synthesis adjudication")
    if set(adjud["reviewed_view_ids"]) != set(views):
        raise ValueError("Synthesis adjudication must review every planned view.")
    expected = _person(adjud, views)
    if previous is not None and (
        previous["synthesis_packets_id"] != data["synthesis_packets_id"]
        or previous["adjudication"]["human_identity"] != adjud["human_identity"]
        or datetime.fromisoformat(adjud["date"])
        <= datetime.fromisoformat(previous["adjudication"]["date"])
    ):
        raise ValueError(
            "Synthesis supersession needs the same scope/adjudicator and a later date."
        )
    if any(
        datetime.fromisoformat(p["date"]) > datetime.fromisoformat(adjud["date"]) for p in assessors
    ):
        raise ValueError("Synthesis adjudication cannot precede independent observations.")
    if datetime.fromisoformat(adjud["date"]) < datetime.fromisoformat(
        loaded["assessment"]["assessment"]["adjudication"]["date"]
    ):
        raise ValueError("Synthesis adjudication cannot precede its candidate assessment.")
    groups, rows = _rows(adjud, expected, items, views, adjudicated=True)
    for row in rows:
        _unique_strings(row["assessor_ids"], "synthesis assessor membership")
        observed = observations.get(row["item_id"], set())
        if set(row["assessor_ids"]) != observed:
            raise ValueError("Synthesis adjudication must retain every independent observation.")
        if len(observed) < 2:
            _text(row["assessor_shortfall_reason"], "synthesis assessor shortfall")
        elif row["assessor_shortfall_reason"] is not None:
            raise ValueError("Synthesis shortfall reason applies only below two assessors.")
        item = items[row["item_id"]]
        row.update(
            {k: item[k] for k in ("candidate_id", "case_id", "packet_id", "attempt_id", "stage")},
            assessor_count=len(observed),
        )
    record = {
        "schema_version": "medical_evaluation_synthesis_v1",
        "record_type": "operator_attested_synthesis_assessment",
        "synthesis_packets_id": data["synthesis_packets_id"],
        "assessment_record_id": loaded["packets"]["assessment_record_id"],
        "original": copy.deepcopy(data),
        "assessors": assessors,
        "adjudication": copy.deepcopy(adjud),
        "groups": groups,
        "judgments": rows,
        "supersedes_record_id": previous["record_id"] if previous is not None else None,
        "empty_views": [v["view_id"] for v in views.values() if not v["item_ids"]],
        "credentials_independence_blinding": "operator_attested_not_authenticated",
        "stage_completeness": "operator_reported_not_execution_or_coverage_receipt",
        "review_coverage_available": False,
        "medical_performance_validated": False,
        "official_assessment": None,
    }
    record["record_id"] = identity("synthesisassessment", record)
    _json_bytes(record)
    return record


def _previous(repo: Path, data: dict[str, Any], seen: set[Path]):
    reference = data["supersedes_run_reference"]
    if reference is None:
        return None, None, None
    if (
        not isinstance(reference, str)
        or Path(reference).is_absolute()
        or ".." in Path(reference).parts
    ):
        raise ValueError("Synthesis supersession requires a private repo-relative run.")
    run = private_path(repo, Path(reference), PRIVATE_RUNS)
    return (
        run,
        sha256_file(run / "run_manifest.json"),
        load_synthesis(repo, run, _seen=seen)["synthesis"],
    )


def record_synthesis(repo_root: Path, packets_run: Path, input_path: Path) -> Path:
    repo = repo_root.resolve()
    parent = private_path(repo, packets_run, PRIVATE_RUNS)
    loaded = load_synthesis_packets(repo, parent)
    source = private_path(
        repo, input_path, PRIVATE_SOURCES / loaded["manifest"]["study_id"] / "evaluation"
    )
    raw = _snapshot(source)
    data = parse_json(raw)
    _exact(data, INPUT_FIELDS, "synthesis input")
    previous_run, previous_hash, previous = _previous(repo, data, set())
    record = validate_synthesis(loaded, data, previous)
    run, manifest, parent_hash, code_sources, code = _start(repo, parent, "assessment", record, raw)
    try:
        _write(run, manifest, "generated/medical_evaluation/raw/synthesis_input.json", raw)
        for name, value in code.items():
            _write(run, manifest, "generated/medical_evaluation/code/" + name, value)
        if (
            sha256_file(source) != hashlib.sha256(raw).hexdigest()
            or sha256_file(parent / "run_manifest.json") != parent_hash
            or any(code_sources[k].read_bytes() != v for k, v in code.items())
            or (
                previous_run is not None
                and sha256_file(previous_run / "run_manifest.json") != previous_hash
            )
            or validate_synthesis(load_synthesis_packets(repo, parent), data, previous) != record
        ):
            raise ValueError("Synthesis input/source/predecessor/code changed while recording.")
        path = run / "processed/medical_evaluation/synthesis.json"
        write_json(path, record)
        update_run(manifest, artifact=str(path))
        update_run(manifest, stage="assessment", status="completed")
        update_run(manifest, status="completed")
    except Exception as error:
        update_run(manifest, status="failed", error=str(error))
        raise
    return run


def load_synthesis(
    repo_root: Path, run_path: Path, *, _seen: set[Path] | None = None
) -> dict[str, Any]:
    repo = repo_root.resolve()
    run = private_path(repo, run_path, PRIVATE_RUNS)
    seen = set() if _seen is None else set(_seen)
    if run in seen or len(seen) >= 100:
        raise ValueError("Synthesis supersession cycle/depth limit reached.")
    seen.add(run)
    manifest, settings, parent = _load_stage(repo, run, "assessment")
    loaded = load_synthesis_packets(repo, parent)
    raw = _snapshot(
        recorded_artifact(
            repo, run, manifest, "generated/medical_evaluation/raw/synthesis_input.json"
        )
    )
    data = parse_json(raw)
    _, _, previous = _previous(repo, data, seen)
    record = read_json(
        recorded_artifact(repo, run, manifest, "processed/medical_evaluation/synthesis.json")
    )
    if (
        hashlib.sha256(raw).hexdigest() != settings["raw_sha256"]
        or content_hash(record) != settings["record_sha256"]
        or validate_synthesis(loaded, data, previous) != record
    ):
        raise ValueError("Synthesis raw/source/semantic binding changed.")
    return {"run_root": run, "manifest": manifest, "packets": loaded, "synthesis": record}
