import pytest

from app.services.simulation_ipc import CommandType, SimulationIPCClient


def test_send_command_timeout_cleans_ipc_files(tmp_path):
    client = SimulationIPCClient(str(tmp_path))

    with pytest.raises(TimeoutError):
        client.send_command(
            command_type=CommandType.INTERVIEW,
            args={"agent_id": 1, "prompt": "status?"},
            timeout=0.05,
            poll_interval=0.01,
        )

    assert list((tmp_path / "ipc_commands").glob("*.json")) == []
    assert list((tmp_path / "ipc_responses").glob("*.json")) == []
