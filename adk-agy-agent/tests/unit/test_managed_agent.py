from unittest.mock import MagicMock, patch

from app.managed_agent import (
    NO_AGENT_MESSAGE,
    PERMISSION_MESSAGE,
    TIMEOUT_MESSAGE,
    TRANSIENT_MESSAGE,
    classify_error,
    run_skill_task,
)


def test_classify_not_found():
    assert classify_error(404) == NO_AGENT_MESSAGE


def test_classify_permission():
    assert classify_error(403) == PERMISSION_MESSAGE


def test_classify_transient():
    assert classify_error(503) == TRANSIENT_MESSAGE


def test_run_skill_task_returns_message_when_credentials_fail():
    tc = MagicMock()
    tc.state = {}
    with patch("app.managed_agent._session", side_effect=RuntimeError("no ADC")):
        out = run_skill_task("do a thing", tc)
    assert out == PERMISSION_MESSAGE


def test_run_skill_task_returns_message_when_agent_missing():
    tc = MagicMock()
    tc.state = {}
    fake = MagicMock()
    fake.get.return_value = MagicMock(status_code=404)  # preflight: missing
    with patch("app.managed_agent._session", return_value=fake):
        out = run_skill_task("do a thing", tc)
    assert out == NO_AGENT_MESSAGE
    assert not fake.post.called  # never attempted the interaction


def test_run_skill_task_happy_path_polls_and_extracts():
    tc = MagicMock()
    tc.state = {}
    fake = MagicMock()
    preflight = MagicMock(status_code=200)  # agent exists
    poll = MagicMock(status_code=200)
    poll.json.return_value = {
        "id": "int-1",
        "status": "completed",
        "environment_id": "env-9",
        # Real REST shape: flat outputs; narration text, then a tool step, then
        # the final answer text after the last tool step.
        "outputs": [
            {"text": "I will look into this.", "type": "text"},
            {"type": "function_call", "name": "list_dir"},
            {"type": "function_result", "name": "list_dir"},
            {"text": "the answer", "type": "text"},
            {"text": "", "type": "text"},
        ],
    }
    fake.get.side_effect = [preflight, poll]  # 1st get = preflight, 2nd = poll
    create = MagicMock(status_code=200)
    create.json.return_value = {"id": "int-1", "status": "in_progress"}
    fake.post.return_value = create
    with patch("app.managed_agent._session", return_value=fake):
        out = run_skill_task("do a thing", tc)
    assert "the answer" in out  # all assistant text returned (narration + answer)
    assert tc.state["previous_interaction_id"] == "int-1"
    assert tc.state["environment_id"] == "env-9"
    # request used background=true and the agent id
    _, kwargs = fake.post.call_args
    assert kwargs["json"]["background"] is True
    assert kwargs["json"]["agent"] == "agy-skill-agent"
    # first turn had no prior state, so no continuity fields sent
    assert "previous_interaction_id" not in kwargs["json"]
    assert "environment" not in kwargs["json"]


def test_run_skill_task_reuses_interaction_and_environment_within_session():
    tc = MagicMock()
    # session state carried over from a previous turn
    tc.state = {"previous_interaction_id": "int-1", "environment_id": "env-9"}
    fake = MagicMock()
    preflight = MagicMock(status_code=200)
    poll = MagicMock(status_code=200)
    poll.json.return_value = {
        "id": "int-2",
        "status": "completed",
        "environment_id": "env-9",
        "outputs": [{"text": "ok", "type": "text"}],
    }
    fake.get.side_effect = [preflight, poll]
    create = MagicMock(status_code=200)
    create.json.return_value = {"id": "int-2", "status": "in_progress"}
    fake.post.return_value = create
    with patch("app.managed_agent._session", return_value=fake):
        run_skill_task("next turn", tc)
    _, kwargs = fake.post.call_args
    assert kwargs["json"]["previous_interaction_id"] == "int-1"  # chains conversation
    assert kwargs["json"]["environment"] == {"env_id": "env-9"}  # reuses sandbox
    assert tc.state["previous_interaction_id"] == "int-2"  # advances for next turn


def test_run_skill_task_times_out_without_terminal_status():
    tc = MagicMock()
    tc.state = {}
    fake = MagicMock()
    preflight = MagicMock(status_code=200)
    inprog = MagicMock(status_code=200)
    inprog.json.return_value = {"id": "int-2", "status": "in_progress", "steps": []}
    # preflight, then always in_progress while polling
    fake.get.side_effect = [preflight] + [inprog] * 50
    create = MagicMock(status_code=200)
    create.json.return_value = {"id": "int-2"}
    fake.post.return_value = create
    # make the loop exit immediately via a zero timeout and no sleep delay
    with patch("app.managed_agent._session", return_value=fake), \
         patch("app.managed_agent.config.INTERACT_TIMEOUT_S", 0), \
         patch("app.managed_agent.config.POLL_INTERVAL_S", 0):
        out = run_skill_task("do a thing", tc)
    assert out == TIMEOUT_MESSAGE
