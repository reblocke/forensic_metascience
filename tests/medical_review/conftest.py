from pathlib import Path

import pytest
from support.medical_review_fixtures import create_workspace


@pytest.fixture
def workspace(tmp_path: Path):
    return create_workspace(tmp_path, Path(__file__).resolve().parents[2])
