"""Unit and integration tests for Porchline Adversarial Evaluation Harness."""

import pytest
from fastapi.testclient import TestClient

from porchline.main import app
from porchline.eval.harness import EvaluationHarness, BenchmarkReport
from porchline.simulator.simulator_engine import ScenarioCatalog

client = TestClient(app)


def test_adversarial_scenario_catalog_coverage():
    """Verify scenario catalog includes adversarial and benign test cases."""
    scenarios = ScenarioCatalog.get_preset_scenarios()
    scenario_ids = [s["id"] for s in scenarios]

    assert "theft_porch_pirate" in scenario_ids
    assert "adversarial_package_swap" in scenario_ids
    assert "adversarial_tailgating" in scenario_ids
    assert "benign_false_alarm_wind" in scenario_ids
    assert len(scenarios) >= 9


def test_evaluation_harness_scoring():
    """Verify EvaluationHarness computes detection recall, false-positive rate, and QA accuracy."""
    harness = EvaluationHarness()
    report = harness.run_benchmark()

    assert isinstance(report, BenchmarkReport)
    assert report.scenarios_evaluated >= 9
    assert report.detection_recall >= 90.0  # High recall on threats
    assert report.false_positive_rate <= 10.0  # Low false positive rate on benign
    assert report.qa_accuracy >= 90.0  # High NL QA precision
    assert report.status == "BENCHMARK_GREEN"
    assert len(report.scenario_results) >= 9
    assert len(report.qa_results) >= 5


def test_evaluation_benchmark_api_endpoints():
    """Test /api/evaluation/benchmark and /api/evaluation/run endpoints."""
    # 1. Fetch cached/pre-computed benchmark
    res = client.get("/api/evaluation/benchmark")
    assert res.status_code == 200
    data = res.json()
    assert "detection_recall" in data
    assert "false_positive_rate" in data
    assert "qa_accuracy" in data
    assert data["status"] == "BENCHMARK_GREEN"

    # 2. Trigger live re-run
    res_run = client.post("/api/evaluation/run")
    assert res_run.status_code == 200
    run_data = res_run.json()
    assert run_data["detection_recall"] >= 90.0
    assert "summary_verdict" in run_data
