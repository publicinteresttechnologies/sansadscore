from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BEST_PRACTICE_TEXT = (ROOT / "scripts" / "commons_score" / "best_practice.py").read_text(encoding="utf-8")

PUBLIC_METRICS = ["Activity", "Local Focus", "Delivery", "Public Value", "Proof"]


def test_public_metric_names_are_declared_in_source():
    assert "PUBLIC_METRIC_ORDER" in BEST_PRACTICE_TEXT
    for metric in PUBLIC_METRICS:
        assert metric in BEST_PRACTICE_TEXT


def test_public_metrics_do_not_include_confidence_marker():
    public_metric_order_line = next(
        line for line in BEST_PRACTICE_TEXT.splitlines() if line.startswith("PUBLIC_METRIC_ORDER")
    )
    assert "Confidence" not in public_metric_order_line
    assert "Proof" in public_metric_order_line


def test_public_metric_mapper_is_attached_to_each_mp():
    assert "def attach_public_metrics" in BEST_PRACTICE_TEXT
    assert "mp[\"public_metrics\"]" in BEST_PRACTICE_TEXT
    assert "mp[\"boost_url\"]" in BEST_PRACTICE_TEXT
