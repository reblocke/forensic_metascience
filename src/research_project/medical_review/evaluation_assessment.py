"""Blinded source packets and operator-attested candidate judgments, never INSPECT-SR."""

from __future__ import annotations

import copy
import hashlib
import math
import random
import stat
from datetime import datetime
from pathlib import Path
from typing import Any

from research_project.inspect_sr.records import evidence_id
from research_project.medical_review.audit import recorded_artifact, validate_run_artifacts
from research_project.medical_review.evaluation import _exact, _identifier
from research_project.medical_review.evaluation_candidates import (
    _code_sources as candidate_code_sources,
)
from research_project.medical_review.evaluation_candidates import _snapshot, load_candidates
from research_project.medical_review.evaluation_packets import (
    DEFAULT_PACKET_BYTES,
    DEFAULT_TOTAL_BYTES,
    MAX_FILES,
    MAX_PACKETS,
    _freeze_directory,
    _json_bytes,
)
from research_project.medical_review.evaluation_reference import (
    ATTESTATION_FIELDS,
    _attestation,
    _text,
    _unique_strings,
)
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

WORKSPACES = "generated/medical_evaluation/assessment_workspaces"
JUDGMENT_FIELDS = {
    "item_id",
    "disposition",
    "issue_type",
    "important",
    "serious_false_allegation",
    "source_attribution",
    "evidence",
    "rationale",
}
ADJUDICATION_FIELDS = JUDGMENT_FIELDS | {
    "reference_ids",
    "assessor_ids",
    "assessor_shortfall_reason",
}
PERSON_FIELDS = ATTESTATION_FIELDS | {"reviewed_view_ids", "view_timings", "judgments"}
FINDING_FIELDS = {
    "finding_summary",
    "issue_type",
    "location",
    "claim_text",
    "assessment",
    "cannot_verify_reason",
    "evidence_summary",
    "source_objects",
    "claim_evidence_links",
    "numeric_check",
    "suggested_fix",
}


def _code_sources() -> dict[str, Path]:
    return {**candidate_code_sources(), "evaluation_assessment.py": Path(__file__)}


def _views(
    repo: Path, loaded: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, bytes], dict[str, Path]]:
    candidates = loaded["candidates"]
    parent = loaded["packets"]
    plan = parent["reference"]["plan"]
    cases = {c["case_id"]: c for c in plan["cases"]}
    views, items, literals, files = [], [], {}, {}
    total, file_count = 0, 0
    if len(parent["packets"]["packets"]) > MAX_PACKETS:
        raise ValueError("Assessment view count exceeds 1024; split explicitly.")
    for packet in parent["packets"]["packets"]:
        view_id = identity(
            "assessmentview",
            {
                "record": candidates["record_id"],
                "packet": packet["packet_id"],
                "seed": plan["seed"],
            },
        )
        root = WORKSPACES + "/" + view_id
        sources, receipts, view_items = [], [], []
        docs = sorted(
            [
                d
                for d in cases[packet["case_id"]]["bundle"]["documents"]
                if d["availability"] == "supplied"
            ],
            key=lambda d: d["source_version_id"],
        )
        names = {}
        for index, doc in enumerate(docs, 1):
            source = private_path(repo, Path(doc["path"]), PRIVATE_SOURCES)
            suffix = source.suffix.lower()
            if suffix not in {".pdf", ".txt", ".csv", ".tsv", ".json"}:
                suffix = ".bin"
            name = f"sources/source-{index:03d}{suffix}"
            names[doc["source_version_id"]] = name
            sources.append(
                {
                    "source_version_id": doc["source_version_id"],
                    "sha256": doc["sha256"],
                    "role": doc["role"],
                    "local_file": name,
                }
            )
            receipts.append(
                {"path": name, "sha256": doc["sha256"], "byte_count": source.stat().st_size}
            )
            files[root + "/" + name] = source
        aliases = {a["local_file"]: names[a["source_version_id"]] for a in packet["source_aliases"]}
        for candidate in candidates["candidates"]:
            if candidate["packet_id"] != packet["packet_id"]:
                continue
            item_id = identity(
                "assessmentitem",
                {
                    "record": candidates["record_id"],
                    "candidate": candidate["candidate_id"],
                    "seed": plan["seed"],
                },
            )
            finding = {k: copy.deepcopy(candidate["original"][k]) for k in FINDING_FIELDS}
            object_ids = {
                obj["id"]: identity("citation", {"item": item_id, "object": obj["id"]})
                for obj in finding["source_objects"]
            }
            for obj in finding["source_objects"]:
                obj["id"] = object_ids[obj["id"]]
                if obj["path"] in aliases:
                    obj["path"] = aliases[obj["path"]]
            for link in finding["claim_evidence_links"]:
                link["source_object_ids"] = [object_ids[v] for v in link["source_object_ids"]]
            view_items.append(
                {
                    "item_id": item_id,
                    "finding": finding,
                    "status": "unverified_proposal",
                    "numeric_check_qualified": False,
                }
            )
            items.append(
                {
                    "item_id": item_id,
                    "view_id": view_id,
                    "candidate_id": candidate["candidate_id"],
                    "packet_id": packet["packet_id"],
                    "attempt_id": candidate["attempt_id"],
                    "stage": candidate["stage"],
                    "case_id": packet["case_id"],
                }
            )
        random.Random(plan["seed"]).shuffle(view_items)
        payload = {
            "schema_version": "medical_evaluation_blinded_view_v1",
            "view_id": view_id,
            "sources": sources,
            "reviewer_source_version_ids": packet["source_version_ids"],
            "items": view_items,
            "source_fidelity_verified": False,
            "review_coverage_available": False,
            "official_assessment": None,
            "empty_findings_mean": "no_supplied_candidates_not_a_clean_paper",
            "limitations": [
                "Metadata removal cannot establish actual blinding; "
                "content/style may reveal origin.",
                "Full supplied case sources support human review; "
                "reviewer access is separately listed.",
                "Statements and numeric checks are unverified proposals; "
                "no official judgment is assigned.",
            ],
        }
        raw = _json_bytes(payload)
        literals[root + "/assessment_packet.json"] = raw
        receipts.append(
            {
                "path": "assessment_packet.json",
                "sha256": hashlib.sha256(raw).hexdigest(),
                "byte_count": len(raw),
            }
        )
        size = sum(r["byte_count"] for r in receipts)
        total += size
        file_count += len(receipts)
        if size > DEFAULT_PACKET_BYTES or total > DEFAULT_TOTAL_BYTES or file_count > MAX_FILES:
            raise ValueError(
                "Assessment packet preparation limits exceeded; split without truncation."
            )
        views.append(
            {
                "view_id": view_id,
                "packet_id": packet["packet_id"],
                "case_id": packet["case_id"],
                "condition_id": packet["condition_id"],
                "track": packet["track"],
                "workspace_reference": root,
                "source_version_ids": [s["source_version_id"] for s in sources],
                "item_ids": [i["item_id"] for i in view_items],
                "files": receipts,
            }
        )
    record = {
        "schema_version": "medical_evaluation_assessment_packets_v1",
        "candidate_record_id": candidates["record_id"],
        "views": views,
        "items": items,
        "blinding_verified": False,
        "blinding_scope": "metadata_removed_content_preserved_operator_attestation_required",
        "removed_finding_metadata": ["id", "category", "severity", "confidence"],
        "source_reference_transform": (
            "known_staged_paths_normalized_object_ids_pseudonymized_unmapped_paths_preserved"
        ),
        "medical_performance_validated": False,
        "official_assessment": None,
    }
    record["record_id"] = identity("assessmentpackets", record)
    _json_bytes(record)
    return record, literals, files


def _start(repo: Path, parent: Path, stage: str, record: dict[str, Any], raw: bytes | None = None):
    parent_hash = sha256_file(parent / "run_manifest.json")
    parent_manifest = read_json(parent / "run_manifest.json")
    code_sources = _code_sources()
    code = {k: p.read_bytes() for k, p in code_sources.items()}
    run, manifest = create_run(
        repo_root=repo,
        output_root=PRIVATE_RUNS,
        study_id=parent_manifest["study_id"],
        categories=["medical_evaluation"],
        config_path=parent / "run_manifest.json",
        input_paths=[parent / "run_manifest.json"],
        settings={
            "medical_evaluation_assessment_stage": stage,
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


def _write(run: Path, manifest: Path, reference: str, raw: bytes) -> None:
    path = run / reference
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)
    update_run(manifest, artifact=str(path))


def _validate_views(
    repo: Path, run: Path, manifest: dict[str, Any], record: dict[str, Any]
) -> None:
    parent = private_path(repo, run / WORKSPACES, PRIVATE_RUNS)
    if {p.name for p in parent.iterdir()} != {v["view_id"] for v in record["views"]}:
        raise ValueError("Assessment workspace inventory changed.")
    if stat.S_IMODE(parent.stat().st_mode) != 0o555:
        raise ValueError("Assessment workspaces must remain read-only.")
    for view in record["views"]:
        root = private_path(repo, run / view["workspace_reference"], PRIVATE_RUNS)
        actual = {str(p.relative_to(root)): p for p in root.rglob("*")}
        files = {r["path"] for r in view["files"]}
        directories = {str(p) for name in files for p in Path(name).parents if str(p) != "."}
        if set(actual) != files | directories:
            raise ValueError("Assessment file/directory inventory changed.")
        for path in (root, *actual.values()):
            private_path(repo, path, PRIVATE_RUNS)
            if path.is_symlink() or stat.S_IMODE(path.stat().st_mode) != (
                0o555 if path.is_dir() else 0o444
            ):
                raise ValueError("Assessment workspace permissions changed.")
        for item in view["files"]:
            path = recorded_artifact(
                repo, run, manifest, view["workspace_reference"] + "/" + item["path"]
            )
            if path.stat().st_size != item["byte_count"] or sha256_file(path) != item["sha256"]:
                raise ValueError("Assessment workspace hash changed.")


def prepare_assessment_packets(repo_root: Path, candidates_run: Path) -> Path:
    repo = repo_root.resolve()
    parent = private_path(repo, candidates_run, PRIVATE_RUNS)
    loaded = load_candidates(repo, parent)
    record, literals, files = _views(repo, loaded)
    run, manifest, parent_hash, code_sources, code = _start(
        repo, parent, "assessment-packets", record
    )
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
                                raise ValueError("Assessment streaming byte limit exceeded.")
                            outgoing.write(chunk)
                    update_run(manifest, artifact=str(path))
                if packet_bytes > DEFAULT_PACKET_BYTES or total > DEFAULT_TOTAL_BYTES:
                    raise ValueError("Assessment literal byte limit exceeded.")
                if path.stat().st_size != item["byte_count"] or sha256_file(path) != item["sha256"]:
                    raise ValueError("Assessment source/view bytes changed while copying.")
                path.chmod(0o444)
            _freeze_directory(run / view["workspace_reference"])
        _freeze_directory(run / WORKSPACES)
        if (
            sha256_file(parent / "run_manifest.json") != parent_hash
            or _views(repo, load_candidates(repo, parent))[0] != record
            or any(code_sources[k].read_bytes() != v for k, v in code.items())
        ):
            raise ValueError("Assessment candidate/source/code changed while preparing.")
        _validate_views(repo, run, read_json(manifest), record)
        path = run / "processed/medical_evaluation/assessment_packets.json"
        write_json(path, record)
        update_run(manifest, artifact=str(path))
        update_run(manifest, stage="assessment-packets", status="completed")
        update_run(manifest, status="completed")
    except Exception as error:
        update_run(manifest, status="failed", error=str(error))
        raise
    return run


def _load_stage(repo: Path, run: Path, stage: str):
    manifest = validate_run_artifacts(repo, run)
    settings = manifest["effective_settings"]
    if (
        manifest["status"] != "completed"
        or settings.get("medical_evaluation_assessment_stage") != stage
    ):
        raise ValueError("Assessment stage is not successfully completed.")
    parent = private_path(repo, Path(settings["parent_run_reference"]), PRIVATE_RUNS)
    if sha256_file(parent / "run_manifest.json") != settings["parent_manifest_sha256"]:
        raise ValueError("Assessment parent manifest changed.")
    archived = {
        k: sha256_file(
            recorded_artifact(repo, run, manifest, "generated/medical_evaluation/code/" + k)
        )
        for k in _code_sources()
    }
    if content_hash(archived) != settings["code_sha256"]:
        raise ValueError("Assessment code archive changed.")
    return manifest, settings, parent


def load_assessment_packets(repo_root: Path, run_path: Path) -> dict[str, Any]:
    repo = repo_root.resolve()
    run = private_path(repo, run_path, PRIVATE_RUNS)
    manifest, settings, parent = _load_stage(repo, run, "assessment-packets")
    loaded = load_candidates(repo, parent)
    record = read_json(
        recorded_artifact(
            repo, run, manifest, "processed/medical_evaluation/assessment_packets.json"
        )
    )
    if content_hash(record) != settings["record_sha256"] or _views(repo, loaded)[0] != record:
        raise ValueError("Assessment packet candidate/source/semantic binding changed.")
    _validate_views(repo, run, manifest, record)
    return {"run_root": run, "manifest": manifest, "candidates": loaded, "packets": record}


def _person(row: dict[str, Any], views: dict[str, Any]) -> set[str]:
    _unique_strings(row["reviewed_view_ids"], "reviewed views", nonempty=True)
    if not set(row["reviewed_view_ids"]) <= set(views):
        raise ValueError("Human review includes an unknown assessment view.")
    versions = {v for key in row["reviewed_view_ids"] for v in views[key]["source_version_ids"]}
    _attestation(row, versions)
    if not isinstance(row["view_timings"], list):
        raise ValueError("Human view timings require an explicit array.")
    timed = set()
    for timing in row["view_timings"]:
        _exact(timing, {"view_id", "verification_seconds", "revision_seconds"}, "human timing")
        if timing["view_id"] not in row["reviewed_view_ids"] or timing["view_id"] in timed:
            raise ValueError("Unknown or duplicate human timing view.")
        timed.add(timing["view_id"])
        for key in ("verification_seconds", "revision_seconds"):
            value = timing[key]
            if value is not None and (
                type(value) not in {int, float}
                or (type(value) is float and not math.isfinite(value))
                or value < 0
            ):
                raise ValueError("Human timing seconds must be nonnegative finite numbers or null.")
    if timed != set(row["reviewed_view_ids"]):
        raise ValueError("Human timing must explicitly account for every reviewed view.")
    return {item for key in row["reviewed_view_ids"] for item in views[key]["item_ids"]}


def _judgment(row: dict[str, Any], item: dict[str, Any], views: dict[str, Any]) -> dict[str, Any]:
    if row["disposition"] not in {
        "confirmed_concern",
        "unsupported_criticism",
        "unresolved",
        "optional_improvement",
    }:
        raise ValueError("Unsupported human candidate disposition.")
    _text(row["issue_type"], "issue type")
    _text(row["rationale"], "judgment rationale")
    for key in ("important", "serious_false_allegation"):
        if row[key] is not None and type(row[key]) is not bool:
            raise ValueError("Human importance/allegation flags must be explicit booleans or null.")
    if row["serious_false_allegation"] is True and row["disposition"] != "unsupported_criticism":
        raise ValueError("A serious false allegation must be an unsupported criticism.")
    if row["source_attribution"] not in {"correct", "incorrect", "unresolved", "not_provided"}:
        raise ValueError("Unsupported source attribution disposition.")
    evidence = row["evidence"]
    if not isinstance(evidence, list) or (not evidence and row["disposition"] != "unresolved"):
        raise ValueError("A resolved human judgment requires explicit source evidence.")
    versions = set(views[item["view_id"]]["source_version_ids"])
    result, seen = [], set()
    for ev in evidence:
        _exact(ev, {"source_version_id", "locator", "raw_value"}, "human source evidence")
        if ev["source_version_id"] not in versions:
            raise ValueError("Human evidence is outside the candidate's case source scope.")
        _text(ev["locator"], "human source locator")
        _text(ev["raw_value"], "human source quote")
        eid = evidence_id(
            ev["source_version_id"], ev["locator"], ev["raw_value"], "human_source_review", "1"
        )
        if eid in seen:
            raise ValueError("Duplicate human source evidence.")
        seen.add(eid)
        result.append(
            {
                **copy.deepcopy(ev),
                "evidence_id": eid,
                "verification": "operator_attested_source_review",
            }
        )
    return {**copy.deepcopy(row), "evidence": result}


def validate_assessment(
    loaded: dict[str, Any], data: Any, previous: dict[str, Any] | None = None
) -> dict[str, Any]:
    _exact(
        data,
        {
            "schema_version",
            "assessment_packets_id",
            "supersedes_run_reference",
            "assessors",
            "adjudication",
        },
        "human assessment input",
    )
    if (
        data["schema_version"] != "medical_evaluation_assessment_input_v1"
        or data["assessment_packets_id"] != loaded["packets"]["record_id"]
    ):
        raise ValueError("Human assessment schema/packet identity mismatch.")
    if (data["supersedes_run_reference"] is None) != (previous is None):
        raise ValueError(
            "Human assessment supersession requires its explicit validated predecessor."
        )
    views = {v["view_id"]: v for v in loaded["packets"]["views"]}
    items = {i["item_id"]: i for i in loaded["packets"]["items"]}
    refs = {
        (r["case_id"], r["reference_id"]): r
        for r in loaded["candidates"]["packets"]["reference"]["ledger"]["reference_issues"]
    }
    assessors, observations, ids, people = [], {}, set(), set()
    if not isinstance(data["assessors"], list) or not data["assessors"]:
        raise ValueError("Assessment needs explicit human assessors.")
    for person in data["assessors"]:
        _exact(person, PERSON_FIELDS | {"assessor_id"}, "human assessor")
        _identifier(person["assessor_id"], "assessor_id")
        expected = _person(person, views)
        if person["assessor_id"] in ids or person["human_identity"] in people:
            raise ValueError("Duplicate human assessor identity.")
        ids.add(person["assessor_id"])
        people.add(person["human_identity"])
        if not isinstance(person["judgments"], list):
            raise ValueError("Human judgments require an explicit array.")
        judged, normalized = set(), []
        for row in person["judgments"]:
            _exact(row, JUDGMENT_FIELDS, "independent judgment")
            item_id = row["item_id"]
            if item_id not in expected or item_id in judged:
                raise ValueError("Unknown or duplicate independently judged item.")
            judged.add(item_id)
            value = _judgment(row, items[item_id], views)
            normalized.append(value)
            observations.setdefault(item_id, {})[person["assessor_id"]] = value
        if judged != expected:
            raise ValueError("Assessor must account for every candidate in reviewed views.")
        assessors.append({**copy.deepcopy(person), "judgments": normalized})
    adjud = data["adjudication"]
    _exact(adjud, PERSON_FIELDS, "human adjudication")
    if set(adjud["reviewed_view_ids"]) != set(views):
        raise ValueError("Adjudication must account for all assessment views.")
    expected = _person(adjud, views)
    if previous is not None:
        if (
            previous["assessment_packets_id"] != data["assessment_packets_id"]
            or previous["adjudication"]["human_identity"] != adjud["human_identity"]
            or datetime.fromisoformat(adjud["date"])
            <= datetime.fromisoformat(previous["adjudication"]["date"])
        ):
            raise ValueError("Supersession requires the same scope/adjudicator and a later date.")
    if any(
        datetime.fromisoformat(p["date"]) > datetime.fromisoformat(adjud["date"]) for p in assessors
    ):
        raise ValueError("Adjudication cannot precede independent observations.")
    if not isinstance(adjud["judgments"], list):
        raise ValueError("Adjudicated judgments require an explicit array.")
    judged, judgments = set(), []
    for row in adjud["judgments"]:
        _exact(row, ADJUDICATION_FIELDS, "adjudicated candidate")
        item_id = row["item_id"]
        if item_id not in expected or item_id in judged:
            raise ValueError("Unknown or duplicate adjudicated item.")
        judged.add(item_id)
        _unique_strings(row["assessor_ids"], "assessor membership")
        observed = observations.get(item_id, {})
        if set(row["assessor_ids"]) != set(observed):
            raise ValueError("Adjudication must retain every independent observation membership.")
        if len(observed) < 2:
            _text(row["assessor_shortfall_reason"], "assessor shortfall")
        elif row["assessor_shortfall_reason"] is not None:
            raise ValueError("Assessor shortfall reason is only applicable below two assessors.")
        _unique_strings(row["reference_ids"], "source reference membership")
        if any((items[item_id]["case_id"], rid) not in refs for rid in row["reference_ids"]):
            raise ValueError("Reference membership is outside its predeclared case scope.")
        judgments.append(
            {
                **_judgment(row, items[item_id], views),
                "candidate_id": items[item_id]["candidate_id"],
                "packet_id": items[item_id]["packet_id"],
                "case_id": items[item_id]["case_id"],
                "assessor_count": len(observed),
            }
        )
    if judged != expected:
        raise ValueError("Adjudication must account for every supplied candidate.")
    record = {
        "schema_version": "medical_evaluation_assessment_v1",
        "record_type": "operator_attested_candidate_assessment",
        "assessment_packets_id": data["assessment_packets_id"],
        "original": copy.deepcopy(data),
        "assessors": assessors,
        "adjudication": copy.deepcopy(adjud),
        "judgments": judgments,
        "supersedes_record_id": previous["record_id"] if previous is not None else None,
        "credentials_independence_blinding": "operator_attested_not_authenticated",
        "empty_views": [v["view_id"] for v in views.values() if not v["item_ids"]],
        "review_coverage_available": False,
        "medical_performance_validated": False,
        "official_assessment": None,
        "synthesis_accounting": "pending_separate_explicit_membership_not_inferred",
    }
    record["record_id"] = identity("candidateassessment", record)
    _json_bytes(record)
    return record


def _previous(repo: Path, data: dict[str, Any], seen: set[Path]):
    ref = data["supersedes_run_reference"]
    if ref is None:
        return None, None, None
    if not isinstance(ref, str) or Path(ref).is_absolute() or ".." in Path(ref).parts:
        raise ValueError("Superseded assessment requires a private repo-relative run.")
    run = private_path(repo, Path(ref), PRIVATE_RUNS)
    record = load_assessment(repo, run, _seen=seen)["assessment"]
    return run, sha256_file(run / "run_manifest.json"), record


def record_assessment(repo_root: Path, packets_run: Path, input_path: Path) -> Path:
    repo = repo_root.resolve()
    parent = private_path(repo, packets_run, PRIVATE_RUNS)
    loaded = load_assessment_packets(repo, parent)
    source = private_path(
        repo, input_path, PRIVATE_SOURCES / loaded["manifest"]["study_id"] / "evaluation"
    )
    raw = _snapshot(source)
    data = parse_json(raw)
    _exact(
        data,
        {
            "schema_version",
            "assessment_packets_id",
            "supersedes_run_reference",
            "assessors",
            "adjudication",
        },
        "human assessment input",
    )
    previous_run, previous_hash, previous = _previous(repo, data, set())
    record = validate_assessment(loaded, data, previous)
    run, manifest, parent_hash, code_sources, code = _start(repo, parent, "assessment", record, raw)
    try:
        _write(run, manifest, "generated/medical_evaluation/raw/assessment_input.json", raw)
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
            or validate_assessment(load_assessment_packets(repo, parent), data, previous) != record
        ):
            raise ValueError(
                "Human assessment input/source/predecessor/code changed while recording."
            )
        path = run / "processed/medical_evaluation/assessment.json"
        write_json(path, record)
        update_run(manifest, artifact=str(path))
        update_run(manifest, stage="assessment", status="completed")
        update_run(manifest, status="completed")
    except Exception as error:
        update_run(manifest, status="failed", error=str(error))
        raise
    return run


def load_assessment(
    repo_root: Path, run_path: Path, *, _seen: set[Path] | None = None
) -> dict[str, Any]:
    repo = repo_root.resolve()
    run = private_path(repo, run_path, PRIVATE_RUNS)
    seen = set() if _seen is None else set(_seen)
    if run in seen or len(seen) >= 100:
        raise ValueError("Human assessment supersession cycle/depth limit reached.")
    seen.add(run)
    manifest, settings, parent = _load_stage(repo, run, "assessment")
    loaded = load_assessment_packets(repo, parent)
    raw = _snapshot(
        recorded_artifact(
            repo, run, manifest, "generated/medical_evaluation/raw/assessment_input.json"
        )
    )
    data = parse_json(raw)
    _, _, previous = _previous(repo, data, seen)
    record = read_json(
        recorded_artifact(repo, run, manifest, "processed/medical_evaluation/assessment.json")
    )
    if (
        hashlib.sha256(raw).hexdigest() != settings["raw_sha256"]
        or content_hash(record) != settings["record_sha256"]
        or validate_assessment(loaded, data, previous) != record
    ):
        raise ValueError("Human assessment raw/source/semantic binding changed.")
    return {"run_root": run, "manifest": manifest, "packets": loaded, "assessment": record}
