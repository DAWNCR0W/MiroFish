import json

import pytest

from app.services.graph_memory_updater import GraphMemoryManager
from app.services.simulation_runner import RunnerStatus, SimulationRunner


def test_start_simulation_cleans_resources_when_process_spawn_fails(tmp_path, monkeypatch):
    simulation_id = "sim_spawn_fail"
    sim_dir = tmp_path / simulation_id
    sim_dir.mkdir()
    (sim_dir / "simulation_config.json").write_text(json.dumps({
        "time_config": {
            "total_simulation_hours": 1,
            "minutes_per_round": 30,
        }
    }), encoding="utf-8")

    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "run_parallel_simulation.py").write_text("# placeholder\n", encoding="utf-8")

    monkeypatch.setattr(SimulationRunner, "RUN_STATE_DIR", str(tmp_path))
    monkeypatch.setattr(SimulationRunner, "SCRIPTS_DIR", str(scripts_dir))
    monkeypatch.setattr(SimulationRunner, "_run_states", {})
    monkeypatch.setattr(SimulationRunner, "_processes", {})
    monkeypatch.setattr(SimulationRunner, "_action_queues", {})
    monkeypatch.setattr(SimulationRunner, "_monitor_threads", {})
    monkeypatch.setattr(SimulationRunner, "_stdout_files", {})
    monkeypatch.setattr(SimulationRunner, "_stderr_files", {})
    monkeypatch.setattr(SimulationRunner, "_graph_memory_enabled", {})

    updater_state = {"active": False, "events": []}

    def fake_create_updater(cls, sim_id, graph_id):
        updater_state["active"] = True
        updater_state["events"].append(("create", sim_id, graph_id))
        return object()

    def fake_get_updater(cls, sim_id):
        if updater_state["active"] and sim_id == simulation_id:
            return object()
        return None

    def fake_stop_updater(cls, sim_id):
        updater_state["active"] = False
        updater_state["events"].append(("stop", sim_id))

    monkeypatch.setattr(GraphMemoryManager, "create_updater", classmethod(fake_create_updater))
    monkeypatch.setattr(GraphMemoryManager, "get_updater", classmethod(fake_get_updater))
    monkeypatch.setattr(GraphMemoryManager, "stop_updater", classmethod(fake_stop_updater))
    monkeypatch.setattr("app.services.simulation_runner.subprocess.Popen", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("spawn failed")))

    with pytest.raises(RuntimeError, match="spawn failed"):
        SimulationRunner.start_simulation(
            simulation_id=simulation_id,
            platform="parallel",
            enable_graph_memory_update=True,
            graph_id="graph_test",
        )

    state = SimulationRunner.get_run_state(simulation_id)

    assert state is not None
    assert state.runner_status == RunnerStatus.FAILED
    assert state.error == "spawn failed"
    assert updater_state["events"] == [
        ("create", simulation_id, "graph_test"),
        ("stop", simulation_id),
    ]
    assert updater_state["active"] is False
    assert simulation_id not in SimulationRunner._action_queues
    assert simulation_id not in SimulationRunner._stdout_files
    assert simulation_id not in SimulationRunner._stderr_files
    assert simulation_id not in SimulationRunner._graph_memory_enabled


def test_start_simulation_rejects_invalid_minutes_per_round(tmp_path, monkeypatch):
    simulation_id = "sim_bad_config"
    sim_dir = tmp_path / simulation_id
    sim_dir.mkdir()
    (sim_dir / "simulation_config.json").write_text(json.dumps({
        "time_config": {
            "total_simulation_hours": 1,
            "minutes_per_round": 0,
        }
    }), encoding="utf-8")

    monkeypatch.setattr(SimulationRunner, "RUN_STATE_DIR", str(tmp_path))

    with pytest.raises(ValueError, match="minutes_per_round"):
        SimulationRunner.start_simulation(simulation_id=simulation_id)
