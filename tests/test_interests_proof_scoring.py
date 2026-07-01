import importlib.util
from pathlib import Path


def test_sitecustomize_marks_interests_as_proof_only():
    text = Path("scripts/sitecustomize.py").read_text(encoding="utf-8")
    assert "interests_api_records_count" in text
    assert "interests_api_categories" in text
    assert "Proof only" in text
    assert "record_scores" not in text


def test_sitecustomize_imports():
    path = Path("scripts/sitecustomize.py")
    spec = importlib.util.spec_from_file_location("sitecustomize", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
