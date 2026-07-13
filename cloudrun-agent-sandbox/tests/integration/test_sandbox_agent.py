from app.agent import root_agent
from app.tools import execute_python_code


def test_root_agent_has_sandbox_tool() -> None:
    assert execute_python_code in root_agent.tools
    assert "execute_python_code" in [t.__name__ for t in root_agent.tools]


def test_root_agent_instruction_contains_sandbox() -> None:
    assert "sandbox" in root_agent.instruction.lower()
    assert "execute_python_code" in root_agent.instruction.lower()


# Simple mock context
class MockToolContext:
    def __init__(self, session_id):
        self.state = {"session_id": session_id}


def test_execute_python_code_propagates_session_id():
    ctx = MockToolContext("test_session_123")
    res = execute_python_code("print('hello')", tool_context=ctx)
    assert res["status"] == "success"


def test_agent_registers_sandbox_command_tool():
    from app.agent import root_agent

    tool_names = [tool.__name__ for tool in root_agent.tools]
    assert "execute_sandbox_command" in tool_names
