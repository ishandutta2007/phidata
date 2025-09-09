from typing import Any, Dict, Optional

from agno.agent.agent import Agent
from agno.models.openai.chat import OpenAIChat
from agno.team.team import Team


def team_factory(shared_db, session_id: Optional[str] = None, session_state: Optional[Dict[str, Any]] = None):
    return Team(
        model=OpenAIChat(id="gpt-4o-mini"),
        session_id=session_id,
        session_state=session_state,
        members=[],
        db=shared_db,
        enable_user_memories=True,
        markdown=True,
        telemetry=False,
    )


def test_team_default_state(shared_db):
    session_id = "session_1"
    session_state = {"test_key": "test_value"}

    team = team_factory(shared_db, session_id, session_state)

    response = team.run("Hello, how are you?")

    assert response.run_id is not None
    assert team.session_id == session_id
    assert team.session_state == session_state

    session_from_storage = team.get_session(session_id=session_id)
    assert session_from_storage is not None
    assert session_from_storage.session_id == session_id
    assert session_from_storage.session_data is not None
    assert session_from_storage.session_data["session_state"] == session_state


def test_team_set_session_name(shared_db):
    session_id = "session_1"
    session_state = {"test_key": "test_value"}

    team = team_factory(shared_db, session_id, session_state)

    team.run("Hello, how are you?")

    team.set_session_name(session_id=session_id, session_name="my_test_session")

    session_from_storage = team.get_session(session_id=session_id)
    assert session_from_storage is not None
    assert session_from_storage.session_id == session_id
    assert session_from_storage.session_data is not None
    assert session_from_storage.session_data["session_name"] == "my_test_session"


def test_team_get_session_name(shared_db):
    session_id = "session_1"
    team = team_factory(shared_db, session_id)
    team.run("Hello, how are you?")
    team.set_session_name(session_id=session_id, session_name="my_test_session")
    assert team.get_session_name() == "my_test_session"


def test_team_get_session_state(shared_db):
    session_id = "session_1"
    team = team_factory(shared_db, session_id, session_state={"test_key": "test_value"})
    team.run("Hello, how are you?")
    assert team.get_session_state() == {"test_key": "test_value"}


def test_team_get_session_metrics(shared_db):
    session_id = "session_1"
    team = team_factory(shared_db, session_id)
    team.run("Hello, how are you?")
    metrics = team.get_session_metrics()
    assert metrics is not None
    assert metrics.total_tokens > 0
    assert metrics.input_tokens > 0
    assert metrics.output_tokens > 0
    assert metrics.total_tokens == metrics.input_tokens + metrics.output_tokens


def test_team_session_state_switch_session_id(shared_db):
    session_id_1 = "session_1"
    session_id_2 = "session_2"
    session_state = {"test_key": "test_value"}

    team = team_factory(shared_db, session_id_1, session_state)

    # First run with a different session ID
    team.run("What can you do?", session_id=session_id_1)
    session_from_storage = team.get_session(session_id=session_id_1)
    assert session_from_storage is not None
    assert session_from_storage.session_id == session_id_1
    assert session_from_storage.session_data is not None
    assert session_from_storage.session_data["session_state"] == session_state

    # Second run with different session ID
    team.run("What can you do?", session_id=session_id_2)
    session_from_storage = team.get_session(session_id=session_id_2)
    assert session_from_storage is not None
    assert session_from_storage.session_id == session_id_2
    assert session_from_storage.session_data is not None
    assert session_from_storage.session_data["session_state"] == session_state

    # Third run with the original session ID
    team.run("What can you do?", session_id=session_id_1)
    session_from_storage = team.get_session(session_id=session_id_1)
    assert session_from_storage is not None
    assert session_from_storage.session_id == session_id_1
    assert session_from_storage.session_data is not None
    assert session_from_storage.session_data["session_state"]["test_key"] == session_state["test_key"]


def test_team_with_state_on_team(shared_db):
    # Define a tool that increments our counter and returns the new value
    def add_item(session_state: Dict[str, Any], item: str) -> str:
        """Add an item to the shopping list."""
        session_state["shopping_list"].append(item)
        return f"The shopping list is now {session_state['shopping_list']}"

    # Create an Agent that maintains state
    team = Team(
        db=shared_db,
        session_state={"shopping_list": []},
        members=[],
        tools=[add_item],
        instructions="Current state (shopping list) is: {shopping_list}",
        markdown=True,
    )
    team.run("Add oranges to my shopping list")
    response = team.run(
        'Current shopping list: {shopping_list}. Other random json ```json { "properties": { "title": { "title": "a" } } }```'
    )

    assert response is not None
    assert response.messages is not None
    assert (
        response.messages[1].content
        == 'Current shopping list: [\'oranges\']. Other random json ```json { "properties": { "title": { "title": "a" } } }```'
    )


def test_team_with_state_on_team_stream(shared_db):
    # Define a tool that increments our counter and returns the new value
    def add_item(session_state: Dict[str, Any], item: str) -> str:
        """Add an item to the shopping list."""
        session_state["shopping_list"].append(item)
        return f"The shopping list is now {session_state['shopping_list']}"

    # Create an Agent that maintains state
    team = Team(
        db=shared_db,
        session_state={"shopping_list": []},
        members=[],
        tools=[add_item],
        instructions="Current state (shopping list) is: {shopping_list}",
        markdown=True,
    )
    for _ in team.run("Add oranges to my shopping list", stream=True):
        pass

    session_from_storage = team.get_session(session_id=team.session_id)
    assert session_from_storage is not None
    assert session_from_storage.session_data is not None
    assert session_from_storage.session_data["session_state"] == {"shopping_list": ["oranges"]}

    for _ in team.run(
        'Current shopping list: {shopping_list}. Other random json ```json { "properties": { "title": { "title": "a" } } }```',
        stream=True,
    ):
        pass

    run_response = team.get_last_run_output()
    assert run_response is not None
    assert run_response.messages is not None
    assert (
        run_response.messages[1].content
        == 'Current shopping list: [\'oranges\']. Other random json ```json { "properties": { "title": { "title": "a" } } }```'
    )


def test_team_with_state_on_run(shared_db):
    # Define a tool that increments our counter and returns the new value
    def add_item(session_state: Dict[str, Any], item: str) -> str:
        """Add an item to the shopping list."""
        session_state["shopping_list"].append(item)
        return f"The shopping list is now {session_state['shopping_list']}"

    # Create an Agent that maintains state
    team = Team(
        db=shared_db,
        tools=[add_item],
        members=[],
        instructions="Current state (shopping list) is: {shopping_list}",
        markdown=True,
    )
    team.run("Add oranges to my shopping list", session_id="session_1", session_state={"shopping_list": []})

    session_from_storage = team.get_session(session_id="session_1")
    assert session_from_storage is not None
    assert session_from_storage.session_data is not None
    assert session_from_storage.session_data["session_state"] == {"shopping_list": ["oranges"]}

    response = team.run(
        'Current shopping list: {shopping_list}. Other random json ```json { "properties": { "title": { "title": "a" } } }```',
        session_id="session_1",
    )

    assert response is not None
    assert response.messages is not None
    assert (
        response.messages[1].content
        == 'Current shopping list: [\'oranges\']. Other random json ```json { "properties": { "title": { "title": "a" } } }```'
    )


def test_team_with_state_on_run_stream(shared_db):
    # Define a tool that increments our counter and returns the new value
    def add_item(session_state: Dict[str, Any], item: str) -> str:
        """Add an item to the shopping list."""
        session_state["shopping_list"].append(item)
        return f"The shopping list is now {session_state['shopping_list']}"

    # Create an Agent that maintains state
    team = Team(
        db=shared_db,
        tools=[add_item],
        members=[],
        instructions="Current state (shopping list) is: {shopping_list}",
        markdown=True,
    )
    for response in team.run(
        "Add oranges to my shopping list", session_id="session_1", session_state={"shopping_list": []}, stream=True
    ):
        pass

    session_from_storage = team.get_session(session_id="session_1")
    assert session_from_storage is not None
    assert session_from_storage.session_data is not None
    assert session_from_storage.session_data["session_state"] == {"shopping_list": ["oranges"]}

    for response in team.run(
        'Current shopping list: {shopping_list}. Other random json ```json { "properties": { "title": { "title": "a" } } }```',
        session_id="session_1",
        stream=True,
    ):
        pass

    run_response = team.get_last_run_output(session_id="session_1")
    assert run_response is not None
    assert run_response.messages is not None
    assert (
        run_response.messages[1].content
        == 'Current shopping list: [\'oranges\']. Other random json ```json { "properties": { "title": { "title": "a" } } }```'
    )


async def test_team_with_state_on_run_async(shared_db):
    # Define a tool that increments our counter and returns the new value
    async def add_item(session_state: Dict[str, Any], item: str) -> str:
        """Add an item to the shopping list."""
        session_state["shopping_list"].append(item)
        return f"The shopping list is now {session_state['shopping_list']}"

    # Create an Agent that maintains state
    team = Team(
        db=shared_db,
        tools=[add_item],
        members=[],
        instructions="Current state (shopping list) is: {shopping_list}",
        markdown=True,
    )
    await team.arun("Add oranges to my shopping list", session_id="session_1", session_state={"shopping_list": []})

    session_from_storage = team.get_session(session_id="session_1")
    assert session_from_storage is not None
    assert session_from_storage.session_data is not None
    assert session_from_storage.session_data["session_state"] == {"shopping_list": ["oranges"]}

    response = await team.arun(
        'Current shopping list: {shopping_list}. Other random json ```json { "properties": { "title": { "title": "a" } } }```',
        session_id="session_1",
    )

    assert response is not None
    assert response.messages is not None
    assert (
        response.messages[1].content
        == 'Current shopping list: [\'oranges\']. Other random json ```json { "properties": { "title": { "title": "a" } } }```'
    )


async def test_team_with_state_on_run_stream_async(shared_db):
    # Define a tool that increments our counter and returns the new value
    async def add_item(session_state: Dict[str, Any], item: str) -> str:
        """Add an item to the shopping list."""
        session_state["shopping_list"].append(item)
        return f"The shopping list is now {session_state['shopping_list']}"

    # Create an Agent that maintains state
    team = Team(
        db=shared_db,
        tools=[add_item],
        members=[],
        instructions="Current state (shopping list) is: {shopping_list}",
        markdown=True,
    )
    async for response in team.arun(
        "Add oranges to my shopping list", session_id="session_1", session_state={"shopping_list": []}, stream=True
    ):
        pass

    session_from_storage = team.get_session(session_id="session_1")
    assert session_from_storage is not None
    assert session_from_storage.session_data is not None
    assert session_from_storage.session_data["session_state"] == {"shopping_list": ["oranges"]}

    async for response in team.arun(
        'Current shopping list: {shopping_list}. Other random json ```json { "properties": { "title": { "title": "a" } } }```',
        session_id="session_1",
        stream=True,
    ):
        pass

    run_response = team.get_last_run_output(session_id="session_1")
    assert run_response is not None
    assert run_response.messages is not None
    assert (
        run_response.messages[1].content
        == 'Current shopping list: [\'oranges\']. Other random json ```json { "properties": { "title": { "title": "a" } } }```'
    )


def test_team_with_state_shared_with_members(shared_db):
    # Define a tool that increments our counter and returns the new value
    def add_item(session_state: Dict[str, Any], item: str) -> str:
        """Add an item to the shopping list."""
        session_state["shopping_list"].append(item)
        return f"The shopping list is now {session_state['shopping_list']}"

    shopping_agent = Agent(
        tools=[add_item],
    )

    # Create an Agent that maintains state
    team = Team(
        db=shared_db,
        members=[shopping_agent],
    )
    team.run("Add oranges to my shopping list", session_id="session_1", session_state={"shopping_list": []})

    session_from_storage = team.get_session(session_id="session_1")
    assert session_from_storage is not None
    assert session_from_storage.session_data is not None
    assert session_from_storage.session_data["session_state"] == {"shopping_list": ["oranges"]}
