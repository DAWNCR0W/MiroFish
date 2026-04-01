import json

import app.api.simulation as simulation_api_module
from app import create_app
from app.config import Config
from app.api.simulation import _check_simulation_prepared
from app.models.task import TaskManager, TaskStatus
from app.services.simulation_manager import SimulationState, SimulationStatus
from app.utils.api_errors import strip_debug_error_fields
from app.utils.retry import retry_with_backoff


class TestConfig:
    DEBUG = True
    TESTING = True
    SECRET_KEY = "test"


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


def test_prepare_status_recovers_active_task_by_simulation_id(monkeypatch):
    app = create_app(TestConfig)
    monkeypatch.setattr(
        simulation_api_module,
        "_check_simulation_prepared",
        lambda simulation_id: (False, {}),
    )

    task_manager = TaskManager()
    with task_manager._task_lock:
        original_tasks = dict(task_manager._tasks)
        task_manager._tasks = {}

    try:
        task_id = task_manager.create_task(
            task_type="simulation_prepare",
            metadata={"simulation_id": "sim_resume"},
        )
        task_manager.update_task(
            task_id,
            status=TaskStatus.PROCESSING,
            progress=42,
            message="프로필 생성 중...",
        )

        client = app.test_client()
        response = client.post(
            "/api/simulation/prepare/status",
            json={"simulation_id": "sim_resume"},
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["success"] is True
        assert payload["data"]["task_id"] == task_id
        assert payload["data"]["status"] == "processing"
        assert payload["data"]["progress"] == 42
        assert payload["data"]["already_prepared"] is False
    finally:
        with task_manager._task_lock:
            task_manager._tasks = original_tasks


def test_prepare_status_reports_interrupted_when_preparing_without_task(monkeypatch):
    app = create_app(TestConfig)
    monkeypatch.setattr(
        simulation_api_module,
        "_check_simulation_prepared",
        lambda simulation_id: (False, {}),
    )
    monkeypatch.setattr(
        simulation_api_module.SimulationManager,
        "get_simulation",
        lambda self, simulation_id: SimulationState(
            simulation_id=simulation_id,
            project_id="proj_test",
            graph_id="graph_test",
            status=SimulationStatus.PREPARING,
        ),
    )

    task_manager = TaskManager()
    with task_manager._task_lock:
        original_tasks = dict(task_manager._tasks)
        task_manager._tasks = {}

    try:
        client = app.test_client()
        response = client.post(
            "/api/simulation/prepare/status",
            json={"simulation_id": "sim_interrupted"},
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["success"] is True
        assert payload["data"]["status"] == "interrupted"
        assert payload["data"]["already_prepared"] is False
    finally:
        with task_manager._task_lock:
            task_manager._tasks = original_tasks
