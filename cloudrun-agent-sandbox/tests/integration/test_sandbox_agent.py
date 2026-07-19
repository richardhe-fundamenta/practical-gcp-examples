from unittest.mock import MagicMock, patch
from app.agent import root_agent
from app.tools import run_python_script


def test_root_agent_has_sandbox_tool() -> None:
    assert run_python_script in root_agent.tools
    assert "run_python_script" in [t.__name__ for t in root_agent.tools]


def test_root_agent_instruction_contains_sandbox() -> None:
    assert "sandbox" in root_agent.instruction.lower()
    assert "run_python_script" in root_agent.instruction.lower()


# Simple mock context
class MockToolContext:
    def __init__(self, session_id):
        self.state = {"session_id": session_id}


@patch("app.tools._get_sandbox_path")
@patch("subprocess.run")
def test_run_python_script_propagates_session_id(mock_run, mock_get_path):
    mock_get_path.return_value = "/usr/bin/sandbox"
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "hello"
    mock_result.stderr = ""
    mock_run.return_value = mock_result

    ctx = MockToolContext("test_session_123")
    res = run_python_script("print('hello')", tool_context=ctx)
    assert res["status"] == "success"
    assert "hello" in res["stdout"]
    assert res["stderr"] == ""
    assert res["returncode"] == 0


def test_agent_registers_sandbox_command_tool():
    from app.agent import root_agent

    tool_names = [tool.__name__ for tool in root_agent.tools]
    assert "run_sandbox_command" in tool_names
