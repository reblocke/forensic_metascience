from __future__ import annotations

import hashlib
import os
import shutil
import sys
from pathlib import Path

import pytest

# Ensure `src/` is on the import path when running tests without installing the package.
REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture
def preserve_synthetic_artifact():
    allowed = {
        "native-method-receipts.csv",
        "native-standardized-results.csv",
        "inspect-sr-review.html",
        "inspect-sr-review.pdf",
        "inspect-sr-early-stop.html",
        "inspect-sr-early-stop.pdf",
        "private-prediction-review.html",
        "private-prediction-review.pdf",
        "medical-review.md",
        "medical-review.html",
        "medical-review.pdf",
        "medical-report-model.json",
        "medical-native-handoffs.json",
        "medical-native-review.html",
        "medical-native-review.pdf",
        "medical-native-report-model.json",
        "medical-evaluation.md",
        "medical-evaluation.html",
        "medical-evaluation.pdf",
        "medical-evaluation-report-model.json",
        "medical-evaluation-qualification.json",
    }

    def preserve(name: str, source: Path) -> Path | None:
        if name not in allowed:
            raise ValueError(f"Artifact is not in the synthetic allowlist: {name}")
        target_root = os.environ.get("FM_TEST_ARTIFACT_DIR")
        if not target_root:
            return None
        destination = Path(target_root).resolve()
        destination.mkdir(parents=True, exist_ok=True)
        target = destination / name
        with target.open("xb") as destination, source.open("rb") as artifact:
            shutil.copyfileobj(artifact, destination)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        target.with_suffix(target.suffix + ".sha256").write_text(
            f"{digest}  {name}\n", encoding="utf-8"
        )
        return target

    return preserve
