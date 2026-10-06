from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest
from support.medical_review_fixtures import write_json

from research_project.medical_review.audit import load_dossier
from research_project.medical_review.importer import import_reviewer
from research_project.medical_review.records import PRIVATE_RUNS
from research_project.medical_review.reporting import (
    build_report_model,
    render_review,
    validate_report_model,
)


@pytest.mark.parametrize("nested", [False, True], ids=["default-root", "nested-private-root"])
def test_source_links_open_exact_versions_with_encoded_names_and_missing_sources(workspace, nested):
    repo, bundle_path, incoming, bundle, _ = workspace
    original = repo / bundle["documents"][0]["path"]
    source = original.with_name("main [methods](1) #?% 'é'.txt")
    original.rename(source)
    reference = source.relative_to(repo).as_posix()
    bundle["documents"][0]["path"] = reference
    bundle["evidence"][0]["parsed_path"] = reference
    missing = copy.deepcopy(bundle["documents"][0])
    missing.update(
        source_id="missing-supplement",
        source_version_id=None,
        role="supplement",
        availability="referenced_but_missing",
        path=None,
        sha256=None,
        upstream_paths=[],
    )
    bundle["documents"].append(missing)
    write_json(bundle_path, bundle)
    imported = import_reviewer(repo, bundle_path, incoming)
    output_root = repo / PRIVATE_RUNS / "custom/deeper" if nested else None
    report = render_review(repo, imported, output_root=output_root)
    from research_project.medical_review.records import read_json

    model = read_json(report / "processed/medical_review/report_model.json")
    navigation = model["source_navigation"]
    links = navigation["documents"]
    available, unavailable = links
    assert available["source_version_id"] == bundle["documents"][0]["source_version_id"]
    assert available["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert available["source_reference"] == reference
    target = urlsplit(available["href"])
    assert not target.scheme and not target.netloc and not target.query and not target.fragment
    assert (report / "reports/medical_review" / unquote(target.path)).resolve() == source
    assert "%20" in available["href"] and "%23" in available["href"]
    assert "%3F" in available["href"] and "%25" in available["href"]
    assert "[" not in available["href"] and "(" not in available["href"]
    assert unavailable["href"] is None and unavailable["source_reference"] is None
    assert unavailable["availability"] == "referenced_but_missing"
    assert "Open original source" in model["rendered_markdown"]
    assert f"]({available['href']})" in model["rendered_markdown"]
    assert "missing-supplement" in model["rendered_markdown"]
    assert model["proposals"] == load_dossier(repo, imported)["proposals"]
    assert load_dossier(repo, report)["bundle"] == bundle
    assert not (repo / "data/private/inspect_sr").exists()


def test_source_navigation_validator_rejects_external_target_and_omission(workspace):
    repo, bundle_path, incoming, _, _ = workspace
    dossier = load_dossier(repo, import_reviewer(repo, bundle_path, incoming))
    model = build_report_model(repo, dossier)
    changed = copy.deepcopy(model)
    changed["source_navigation"]["documents"][0]["href"] = "https://example.invalid/source"
    with pytest.raises(ValueError, match="navigation"):
        validate_report_model(changed, dossier)
    changed = copy.deepcopy(model)
    del changed["source_navigation"]
    with pytest.raises(ValueError, match="navigation"):
        validate_report_model(changed, dossier)


def test_historical_report_representation_does_not_require_new_navigation(workspace):
    repo, bundle_path, incoming, _, _ = workspace
    dossier = load_dossier(repo, import_reviewer(repo, bundle_path, incoming))
    model = build_report_model(repo, dossier)
    # A different archived renderer may predate navigation. Its archive/manifest
    # binding is separately checked by load_dossier; this exercises optional fields.
    del model["source_navigation"]
    model["renderer_source_sha256"] = "0" * 64
    frozen = copy.deepcopy(model)
    validate_report_model(model, dossier)
    assert model == frozen


def test_report_model_refuses_public_navigation_base(workspace):
    repo, bundle_path, incoming, _, _ = workspace
    dossier = load_dossier(repo, import_reviewer(repo, bundle_path, incoming))
    with pytest.raises(ValueError, match="private"):
        build_report_model(repo, dossier, output_root=Path("reports"))


@pytest.mark.parametrize("change", ["bytes", "symlink"])
def test_source_links_refuse_source_drift_after_dossier_loading(workspace, change):
    repo, bundle_path, incoming, bundle, _ = workspace
    dossier = load_dossier(repo, import_reviewer(repo, bundle_path, incoming))
    source = repo / bundle["documents"][0]["path"]
    if change == "bytes":
        source.write_text("Synthetic changed source bytes.\n")
    else:
        outside = repo.parent / "outside.txt"
        outside.write_bytes(source.read_bytes())
        source.unlink()
        source.symlink_to(outside)
    with pytest.raises(ValueError, match="hash mismatch|private boundary"):
        build_report_model(repo, dossier)


@pytest.mark.parametrize("page_index", [1, None], ids=["known-page", "unknown-page"])
def test_evidence_links_target_original_pdf_page_only_when_declared(workspace, page_index):
    from pypdf import PdfWriter

    from research_project.inspect_sr.records import evidence_id, source_version_id

    repo, bundle_path, incoming, bundle, upstream = workspace
    path = repo / "data/private/medical_reviews/synthetic/sources/original.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.add_blank_page(width=612, height=792)
    with path.open("xb") as stream:
        writer.write(stream)
    # Blank synthetic pages test navigation only; parsed text is a supplied fixture,
    # not a claim of faithful PDF extraction or human source-semantic verification.
    document = bundle["documents"][0]
    document.update(
        path=path.relative_to(repo).as_posix(), sha256=hashlib.sha256(path.read_bytes()).hexdigest()
    )
    document["source_version_id"] = source_version_id(document["source_id"], document["sha256"])
    row = bundle["evidence"][0]
    row.update(
        source_version_id=document["source_version_id"],
        page_index=page_index,
        upstream_page=page_index + 1 if page_index is not None else None,
        page_label="2" if page_index is not None else None,
        locator="page=2;paragraph=1" if page_index is not None else "section=Methods;paragraph=1",
    )
    row["evidence_id"] = evidence_id(
        row["source_version_id"],
        row["locator"],
        row["raw_value"],
        row["parser"]["id"],
        row["parser"]["version"],
    )
    for item in (upstream["findings"][0]["location"], upstream["findings"][0]["source_objects"][0]):
        item.update(page=row["upstream_page"], page_label=row["page_label"])
    write_json(bundle_path, bundle)
    write_json(incoming, upstream)
    dossier = load_dossier(repo, import_reviewer(repo, bundle_path, incoming))
    model = build_report_model(repo, dossier)
    href = model["source_navigation"]["documents"][0]["href"]
    target = href + "#page=2" if page_index is not None else href
    assert (
        f"**Source for cited evidence:** [Open original source]({target})"
        in model["rendered_markdown"]
    )
    if page_index is None:
        assert "#page=" not in model["rendered_markdown"]
