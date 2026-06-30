def test_sitecustomize_module_exists():
    import importlib.util
    from pathlib import Path

    path = Path("scripts/sitecustomize.py")
    assert path.exists()
    spec = importlib.util.spec_from_file_location("sitecustomize", path)
    assert spec is not None
