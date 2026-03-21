import json

from app.config import Config
from app.api.simulation import _check_simulation_prepared
from app.utils.api_errors import strip_debug_error_fields
from app.utils.retry import retry_with_backoff


def test_check_simulation_prepared_accepts_single_platform_files(monkeypatch, tmp_path):
    monkeypatch.setattr(Config, "OASIS_SIMULATION_DATA_DIR", str(tmp_path))

    simulation_id = "sim_twitter_only"
    sim_dir = tmp_path / simulation_id
    sim_dir.mkdir(parents=True, exist_ok=True)

    (sim_dir / "state.json").write_text(
        json.dumps(
            {
                "status": "ready",
                "config_generated": True,
                "enable_twitter": True,
                "enable_reddit": False,
                "profiles_count": 2,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (sim_dir / "simulation_config.json").write_text("{}", encoding="utf-8")
    (sim_dir / "twitter_profiles.csv").write_text("agent_id,name\n0,Alice\n1,Bob\n", encoding="utf-8")

    prepared, info = _check_simulation_prepared(simulation_id)

    assert prepared is True
    assert info["profiles_count"] == 2
    assert "twitter_profiles.csv" in info["existing_files"]
    assert "reddit_profiles.json" not in info["existing_files"]


def test_strip_debug_error_fields_always_removes_traceback():
    payload = {
        "success": False,
        "error": "boom",
        "traceback": "secret",
        "nested": {
            "traceback": "nested-secret",
            "details": {"line": 1},
        },
    }

    sanitized = strip_debug_error_fields(payload, include_debug=True)

    assert "traceback" not in sanitized
    assert "traceback" not in sanitized["nested"]
    assert sanitized["nested"]["details"] == {"line": 1}


def test_retry_callback_failure_does_not_break_retry_flow():
    attempts = {"count": 0}

    @retry_with_backoff(
        max_retries=1,
        initial_delay=0,
        max_delay=0,
        jitter=False,
        on_retry=lambda error, retry_count: (_ for _ in ()).throw(RuntimeError("observer boom")),
    )
    def flaky_call():
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("first failure")
        return "ok"

    assert flaky_call() == "ok"
    assert attempts["count"] == 2
