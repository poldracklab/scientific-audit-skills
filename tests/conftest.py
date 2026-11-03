import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "audit-prep" / "scripts"))


@pytest.fixture
def corpus_root(tmp_path):
    return tmp_path / "corpus"
