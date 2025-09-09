from textwrap import dedent

import pytest
from pydantic import BaseModel

from agno.agent import RunEvent
from agno.agent.agent import Agent
from agno.models.openai.chat import OpenAIChat
from agno.team import Team, TeamRunEvent
from agno.tools.calculator import CalculatorTools
from agno.tools.decorator import tool
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.reasoning import ReasoningTools
from agno.tools.yfinance import YFinanceTools


def test_basic_events():
    team = Team(
        model=OpenAIChat(id="gpt-4o-mini"),
        members=[],
        telemetry=False,
    )

    response_generator = team.run("Hello, how are you?", stream=True, stream_intermediate_steps=False)

    event_counts = {}
    for run_response in response_generator:
        event_counts[run_response.event] = event_counts.get(run_response.event, 0) + 1

    assert event_counts.keys() == {TeamRunEvent.run_content}

    assert event_counts[TeamRunEvent.run_content] > 1


@pytest.mark.asyncio
async def test_async_basic_events():
    team = Team(
        model=OpenAIChat(id="gpt-4o-mini"),
        members=[],
        telemetry=False,
    )
    event_counts = {}
    async for run_response in team.arun("Hello, how are you?", stream=True, stream_intermediate_steps=False):
        event_counts[run_response.event] = event_counts.get(run_response.event, 0) + 1

    assert event_counts.keys() == {TeamRunEvent.run_content}

    assert event_counts[TeamRunEvent.run_content] > 1


def test_basic_intermediate_steps_events():
    team = Team(
        model=OpenAIChat(id="gpt-4o-mini"),
        members=[],
        telemetry=False,
    )

    response_generator = team.run("Hello, how are you?", stream=True, stream_intermediate_steps=True)

    events = {}
    for run_response_delta in response_generator:
        if run_response_delta.event not in events:
            events[run_response_delta.event] = []
        events[run_response_delta.event].append(run_response_delta)

    assert events.keys() == {TeamRunEvent.run_started, TeamRunEvent.run_content, TeamRunEvent.run_completed}

    assert len(events[TeamRunEvent.run_started]) == 1
    assert events[TeamRunEvent.run_started][0].model == "gpt-4o-mini"
    assert events[TeamRunEvent.run_started][0].model_provider == "OpenAI"
    assert events[TeamRunEvent.run_started][0].session_id is not None
    assert events[TeamRunEvent.run_started][0].team_id is not None
    assert events[TeamRunEvent.run_started][0].run_id is not None
    assert events[TeamRunEvent.run_started][0].created_at is not None
    assert len(events[TeamRunEvent.run_content]) > 1
    assert len(events[TeamRunEvent.run_completed]) == 1

    team_completed_event = events[TeamRunEvent.run_completed][0]
    assert hasattr(team_completed_event, "metadata")
    assert hasattr(team_completed_event, "metrics")

    assert team_completed_event.metrics is not None
    assert team_completed_event.metrics.total_tokens > 0


def test_basic_intermediate_steps_events_persisted(shared_db):
    """Test that the agent streams events."""
    team = Team(
        model=OpenAIChat(id="gpt-4o-mini"),
        members=[],
        db=shared_db,
        store_events=True,
        telemetry=False,
    )

    response_generator = team.run("Hello, how are you?", stream=True, stream_intermediate_steps=True)

    events = {}
    for run_response_delta in response_generator:
        if run_response_delta.event not in events:
            events[run_response_delta.event] = []
        events[run_response_delta.event].append(run_response_delta)

    assert events.keys() == {TeamRunEvent.run_started, TeamRunEvent.run_content, TeamRunEvent.run_completed}

    run_response_from_storage = team.get_last_run_output()

    assert run_response_from_storage is not None
    assert run_response_from_storage.events is not None
    assert len(run_response_from_storage.events) == 2, "We should only have the run started and run completed events"
    assert run_response_from_storage.events[0].event == TeamRunEvent.run_started
    assert run_response_from_storage.events[1].event == TeamRunEvent.run_completed

    persisted_team_completed_event = run_response_from_storage.events[1]
    assert hasattr(persisted_team_completed_event, "metadata")
    assert hasattr(persisted_team_completed_event, "metrics")

    assert persisted_team_completed_event.metrics is not None
    assert persisted_team_completed_event.metrics.total_tokens > 0


def test_intermediate_steps_with_tools():
    team = Team(
        model=OpenAIChat(id="o3-mini"),
        members=[],
        tools=[YFinanceTools(cache_results=True)],
        telemetry=False,
    )

    events = {}
    for run_response_delta in team.run(
        "What is the stock price of Apple?", stream=True, stream_intermediate_steps=True
    ):
        if run_response_delta.event not in events:
            events[run_response_delta.event] = []
        events[run_response_delta.event].append(run_response_delta)

    assert events.keys() == {
        TeamRunEvent.run_started,
        TeamRunEvent.tool_call_started,
        TeamRunEvent.tool_call_completed,
        TeamRunEvent.run_content,
        TeamRunEvent.run_completed,
    }

    assert len(events[TeamRunEvent.tool_call_started]) >= 1
    # The team may first try to delegate the task to a member, then call the tool directly
    tool_names = [event.tool.tool_name for event in events[TeamRunEvent.tool_call_started]]
    assert "get_current_stock_price" in tool_names or "delegate_task_to_member" in tool_names
    assert len(events[TeamRunEvent.tool_call_completed]) >= 1
    # Check that at least one tool call completed successfully
    completed_tools = [event for event in events[TeamRunEvent.tool_call_completed] if event.content is not None]
    assert len(completed_tools) >= 1
    assert any(event.tool.result is not None for event in events[TeamRunEvent.tool_call_completed])


def test_intermediate_steps_with_tools_events_persisted(shared_db):
    team = Team(
        model=OpenAIChat(id="o3-mini"),
        db=shared_db,
        store_events=True,
        members=[],
        tools=[YFinanceTools(cache_results=True)],
        telemetry=False,
    )

    events = {}
    for run_response_delta in team.run(
        "What is the stock price of Apple?", stream=True, stream_intermediate_steps=True
    ):
        if run_response_delta.event not in events:
            events[run_response_delta.event] = []
        events[run_response_delta.event].append(run_response_delta)

    assert events.keys() == {
        TeamRunEvent.run_started,
        TeamRunEvent.tool_call_started,
        TeamRunEvent.tool_call_completed,
        TeamRunEvent.run_content,
        TeamRunEvent.run_completed,
    }

    run_response_from_storage = team.get_last_run_output()

    assert run_response_from_storage is not None
    assert run_response_from_storage.events is not None
    assert len(run_response_from_storage.events) >= 4
    # Check that we have the essential events (may have more due to member delegation)
    event_types = [event.event for event in run_response_from_storage.events]
    assert TeamRunEvent.run_started in event_types
    assert TeamRunEvent.tool_call_started in event_types
    assert TeamRunEvent.tool_call_completed in event_types
    assert TeamRunEvent.run_completed in event_types


def test_intermediate_steps_with_reasoning():
    team = Team(
        model=OpenAIChat(id="gpt-4o-mini"),
        members=[],
        tools=[ReasoningTools(add_instructions=True)],
        instructions=dedent("""\
            You are an expert problem-solving assistant with strong analytical skills! 🧠
            Use step-by-step reasoning to solve the problem.
            \
        """),
        telemetry=False,
    )

    response_generator = team.run(
        "What is the sum of the first 10 natural numbers?",
        stream=True,
        stream_intermediate_steps=True,
    )

    events = {}
    for run_response_delta in response_generator:
        if run_response_delta.event not in events:
            events[run_response_delta.event] = []
        events[run_response_delta.event].append(run_response_delta)

    assert events.keys() == {
        TeamRunEvent.run_started,
        TeamRunEvent.tool_call_started,
        TeamRunEvent.tool_call_completed,
        TeamRunEvent.reasoning_started,
        TeamRunEvent.reasoning_completed,
        TeamRunEvent.reasoning_step,
        TeamRunEvent.run_content,
        TeamRunEvent.run_completed,
    }

    assert len(events[TeamRunEvent.run_started]) == 1
    assert len(events[TeamRunEvent.run_content]) > 1
    assert len(events[TeamRunEvent.run_completed]) == 1
    assert len(events[TeamRunEvent.tool_call_started]) > 1
    assert len(events[TeamRunEvent.tool_call_completed]) > 1
    assert len(events[TeamRunEvent.reasoning_started]) == 1
    assert len(events[TeamRunEvent.reasoning_completed]) == 1
    assert events[TeamRunEvent.reasoning_completed][0].content is not None
    assert events[TeamRunEvent.reasoning_completed][0].content_type == "ReasoningSteps"
    assert len(events[TeamRunEvent.reasoning_step]) > 1
    assert events[TeamRunEvent.reasoning_step][0].content is not None
    assert events[TeamRunEvent.reasoning_step][0].content_type == "ReasoningStep"
    assert events[TeamRunEvent.reasoning_step][0].reasoning_content is not None


@pytest.mark.skip(reason="Not yet implemented")
def test_intermediate_steps_with_user_confirmation():
    @tool(requires_confirmation=True)
    def get_the_weather(city: str):
        return f"It is currently 70 degrees and cloudy in {city}"

    team = Team(
        model=OpenAIChat(id="gpt-4o-mini"),
        members=[],
        tools=[get_the_weather],
        telemetry=False,
    )

    response_generator = team.run("What is the weather in Tokyo?", stream=True, stream_intermediate_steps=True)

    # First until we hit a pause
    events = {}
    for run_response_delta in response_generator:
        if run_response_delta.event not in events:
            events[run_response_delta.event] = []
        events[run_response_delta.event].append(run_response_delta)

    assert events.keys() == {TeamRunEvent.run_started, TeamRunEvent.run_paused}

    assert len(events[TeamRunEvent.run_started]) == 1
    assert len(events[TeamRunEvent.run_paused]) == 1
    assert events[TeamRunEvent.run_paused][0].tools[0].requires_confirmation is True

    assert team.is_paused

    assert team.run_response.tools[0].requires_confirmation

    # Mark the tool as confirmed
    updated_tools = team.run_response.tools
    run_id = team.run_response.run_id
    updated_tools[0].confirmed = True

    # Then we continue the run
    response_generator = team.continue_run(
        run_id=run_id, updated_tools=updated_tools, stream=True, stream_intermediate_steps=True
    )

    events = {}
    for run_response_delta in response_generator:
        if run_response_delta.event not in events:
            events[run_response_delta.event] = []
        events[run_response_delta.event].append(run_response_delta)

    assert team.run_response.tools[0].result == "It is currently 70 degrees and cloudy in Tokyo"

    assert events.keys() == {
        TeamRunEvent.run_continued,
        TeamRunEvent.tool_call_started,
        TeamRunEvent.tool_call_completed,
        TeamRunEvent.run_content,
        TeamRunEvent.run_completed,
    }

    assert len(events[TeamRunEvent.run_continued]) == 1
    assert len(events[TeamRunEvent.tool_call_started]) == 1
    assert events[TeamRunEvent.tool_call_started][0].tool.tool_name == "get_the_weather"
    assert len(events[TeamRunEvent.tool_call_completed]) == 1
    assert events[TeamRunEvent.tool_call_completed][0].content is not None
    assert events[TeamRunEvent.tool_call_completed][0].tool.result is not None
    assert len(events[TeamRunEvent.run_content]) > 1
    assert len(events[TeamRunEvent.run_completed]) == 1

    assert team.run_response.is_paused is False


def test_intermediate_steps_with_memory(shared_db):
    team = Team(
        model=OpenAIChat(id="gpt-4o-mini"),
        members=[],
        db=shared_db,
        enable_user_memories=True,
        telemetry=False,
    )

    response_generator = team.run("Hello, how are you?", stream=True, stream_intermediate_steps=True)

    events = {}
    for run_response_delta in response_generator:
        if run_response_delta.event not in events:
            events[run_response_delta.event] = []
        events[run_response_delta.event].append(run_response_delta)

    assert events.keys() == {
        TeamRunEvent.run_started,
        TeamRunEvent.run_content,
        TeamRunEvent.run_completed,
        TeamRunEvent.memory_update_started,
        TeamRunEvent.memory_update_completed,
    }

    assert len(events[TeamRunEvent.run_started]) == 1
    assert len(events[TeamRunEvent.run_content]) > 1
    assert len(events[TeamRunEvent.run_completed]) == 1
    assert len(events[TeamRunEvent.memory_update_started]) == 1
    assert len(events[TeamRunEvent.memory_update_completed]) == 1


def test_intermediate_steps_with_structured_output(shared_db):
    """Test that the agent streams events."""

    class Person(BaseModel):
        name: str
        description: str
        age: int

    team = Team(
        model=OpenAIChat(id="gpt-4o-mini"),
        members=[],
        db=shared_db,
        output_schema=Person,
        instructions="You have no members, answer directly",
        telemetry=False,
    )

    response_generator = team.run("Describe Elon Musk", stream=True, stream_intermediate_steps=True)

    events = {}
    for run_response_delta in response_generator:
        if run_response_delta.event not in events:
            events[run_response_delta.event] = []
        events[run_response_delta.event].append(run_response_delta)

    assert events.keys() == {
        TeamRunEvent.run_started,
        TeamRunEvent.run_content,
        TeamRunEvent.run_completed,
    }

    assert len(events[TeamRunEvent.run_started]) == 1
    assert len(events[TeamRunEvent.run_content]) == 1
    assert len(events[TeamRunEvent.run_completed]) == 1

    assert events[TeamRunEvent.run_content][0].content is not None
    assert events[TeamRunEvent.run_content][0].content_type == "Person"
    assert events[TeamRunEvent.run_content][0].content.name == "Elon Musk"
    assert len(events[TeamRunEvent.run_content][0].content.description) > 1

    assert events[TeamRunEvent.run_completed][0].content is not None
    assert events[TeamRunEvent.run_completed][0].content_type == "Person"
    assert events[TeamRunEvent.run_completed][0].content.name == "Elon Musk"
    assert len(events[TeamRunEvent.run_completed][0].content.description) > 1

    team_completed_event_structured = events[TeamRunEvent.run_completed][0]
    assert team_completed_event_structured.metrics is not None
    assert team_completed_event_structured.metrics.total_tokens > 0


def test_intermediate_steps_with_parser_model(shared_db):
    """Test that the agent streams events."""

    class Person(BaseModel):
        name: str
        description: str
        age: int

    team = Team(
        model=OpenAIChat(id="gpt-4o-mini"),
        members=[],
        db=shared_db,
        output_schema=Person,
        parser_model=OpenAIChat(id="gpt-4o-mini"),
        instructions="You have no members, answer directly",
        telemetry=False,
    )

    response_generator = team.run("Describe Elon Musk", stream=True, stream_intermediate_steps=True)

    events = {}
    for run_response_delta in response_generator:
        if run_response_delta.event not in events:
            events[run_response_delta.event] = []
        events[run_response_delta.event].append(run_response_delta)

    run_response = team.get_last_run_output()

    assert events.keys() == {
        TeamRunEvent.run_started,
        TeamRunEvent.parser_model_response_started,
        TeamRunEvent.parser_model_response_completed,
        TeamRunEvent.run_content,
        TeamRunEvent.run_completed,
    }

    assert len(events[TeamRunEvent.run_started]) == 1
    assert len(events[TeamRunEvent.parser_model_response_started]) == 1
    assert len(events[TeamRunEvent.parser_model_response_completed]) == 1
    assert (
        len(events[TeamRunEvent.run_content]) >= 2
    )  # The first model streams, then the parser model has a single content event
    assert len(events[TeamRunEvent.run_completed]) == 1

    assert events[TeamRunEvent.run_content][-1].content is not None
    assert events[TeamRunEvent.run_content][-1].content_type == "Person"
    # Handle both dict and Pydantic model cases
    content = events[TeamRunEvent.run_content][-1].content
    if isinstance(content, dict):
        assert content["name"] == "Elon Musk"
        assert len(content["description"]) > 1
    else:
        assert content.name == "Elon Musk"
        assert len(content.description) > 1

    assert events[TeamRunEvent.run_completed][0].content is not None
    assert events[TeamRunEvent.run_completed][0].content_type == "Person"
    # Handle both dict and Pydantic model cases
    completed_content = events[TeamRunEvent.run_completed][0].content
    if isinstance(completed_content, dict):
        assert completed_content["name"] == "Elon Musk"
        assert len(completed_content["description"]) > 1
    else:
        assert completed_content.name == "Elon Musk"
        assert len(completed_content.description) > 1

    assert run_response.content is not None
    assert run_response.content_type == "Person"
    # Handle both dict and Pydantic model cases
    response_content = run_response.content
    if isinstance(response_content, dict):
        assert response_content["name"] == "Elon Musk"
        assert len(response_content["description"]) > 1
    else:
        assert response_content.name == "Elon Musk"
        assert len(response_content.description) > 1


def test_intermediate_steps_with_member_agents():
    agent_1 = Agent(
        name="Analyst",
        model=OpenAIChat(id="gpt-4o-mini"),
        instructions="You are an expert problem-solving assistant with strong analytical skills! 🧠",
        tools=[ReasoningTools(add_instructions=True)],
    )
    agent_2 = Agent(
        name="Math Agent",
        model=OpenAIChat(id="gpt-4o-mini"),
        instructions="You can do Math!",
        tools=[CalculatorTools()],
    )
    team = Team(
        model=OpenAIChat(id="gpt-4o-mini"),
        members=[agent_1, agent_2],
        telemetry=False,
    )

    response_generator = team.run(
        "Analyse and then solve the problem: 'solve 10 factorial'", stream=True, stream_intermediate_steps=True
    )

    events = {}
    for run_response_delta in response_generator:
        if run_response_delta.event not in events:
            events[run_response_delta.event] = []
        events[run_response_delta.event].append(run_response_delta)

    assert events.keys() == {
        TeamRunEvent.run_started,
        TeamRunEvent.tool_call_started,
        RunEvent.run_started,
        RunEvent.tool_call_started,
        RunEvent.tool_call_completed,
        RunEvent.reasoning_started,
        RunEvent.reasoning_step,
        RunEvent.reasoning_completed,
        RunEvent.run_content,
        RunEvent.run_completed,
        TeamRunEvent.tool_call_completed,
        TeamRunEvent.run_content,
        TeamRunEvent.run_completed,
    }

    assert len(events[TeamRunEvent.run_started]) == 1
    # Transfer twice, from team to member agents
    assert len(events[TeamRunEvent.tool_call_started]) == 2
    assert events[TeamRunEvent.tool_call_started][0].tool.tool_name == "delegate_task_to_member"
    assert events[TeamRunEvent.tool_call_started][0].tool.tool_args["member_id"] == "analyst"
    assert events[TeamRunEvent.tool_call_started][1].tool.tool_name == "delegate_task_to_member"
    assert events[TeamRunEvent.tool_call_started][1].tool.tool_args["member_id"] == "math-agent"
    assert len(events[TeamRunEvent.tool_call_completed]) == 2
    assert events[TeamRunEvent.tool_call_completed][0].tool.tool_name == "delegate_task_to_member"
    assert events[TeamRunEvent.tool_call_completed][0].tool.result is not None
    assert events[TeamRunEvent.tool_call_completed][1].tool.tool_name == "delegate_task_to_member"
    assert events[TeamRunEvent.tool_call_completed][1].tool.result is not None
    assert len(events[TeamRunEvent.run_content]) > 1
    assert len(events[TeamRunEvent.run_completed]) == 1
    # Two member agents
    assert len(events[RunEvent.run_started]) == 2
    assert len(events[RunEvent.run_completed]) == 2
    # Lots of member tool calls
    assert len(events[RunEvent.tool_call_started]) > 1
    assert len(events[RunEvent.tool_call_completed]) > 1
    assert len(events[RunEvent.reasoning_started]) == 1
    assert len(events[RunEvent.reasoning_completed]) == 1
    assert len(events[RunEvent.reasoning_step]) > 1
    assert len(events[RunEvent.run_content]) > 1


def test_intermediate_steps_with_member_agents_nested_team():
    agent_1 = Agent(
        name="Finance Analyst",
        model=OpenAIChat(id="gpt-4o-mini"),
        instructions="You are an expert finance analyst with strong analytical skills! 🧠",
        tools=[YFinanceTools(cache_results=True)],
    )
    agent_2 = Agent(
        name="News Analyst",
        model=OpenAIChat(id="gpt-4o-mini"),
        instructions="You are an expert news analyst with strong analytical skills! 🧠",
        tools=[DuckDuckGoTools(cache_results=True)],
    )
    sub_team = Team(
        model=OpenAIChat(id="gpt-4o-mini"),
        name="News Team",
        members=[agent_2],
        telemetry=False,
    )
    team = Team(
        model=OpenAIChat(id="gpt-4o-mini"),
        members=[agent_1, sub_team],
        tools=[ReasoningTools(add_instructions=True)],
        telemetry=False,
    )

    response_generator = team.run("Do a stock market analysis for Apple.", stream=True, stream_intermediate_steps=True)

    events = {}
    for run_response_delta in response_generator:
        if run_response_delta.event not in events:
            events[run_response_delta.event] = []
        events[run_response_delta.event].append(run_response_delta)

    assert set(events.keys()) == {
        TeamRunEvent.run_started,
        TeamRunEvent.tool_call_started,
        TeamRunEvent.tool_call_completed,
        TeamRunEvent.reasoning_started,
        TeamRunEvent.reasoning_step,
        RunEvent.run_started,
        RunEvent.tool_call_started,
        RunEvent.tool_call_completed,
        RunEvent.run_content,
        RunEvent.run_completed,
        TeamRunEvent.run_content,
        TeamRunEvent.run_completed,
        TeamRunEvent.reasoning_completed,
    }


def test_intermediate_steps_with_member_agents_streaming_off():
    agent_1 = Agent(
        name="Analyst",
        model=OpenAIChat(id="gpt-4o-mini"),
        instructions="You are an expert problem-solving assistant with strong analytical skills! 🧠",
        tools=[ReasoningTools(add_instructions=True)],
    )
    agent_2 = Agent(
        name="Math Agent",
        model=OpenAIChat(id="gpt-4o-mini"),
        instructions="You can do Math!",
        tools=[CalculatorTools()],
    )
    team = Team(
        model=OpenAIChat(id="gpt-4o-mini"),
        members=[agent_1, agent_2],
        telemetry=False,
        stream_member_events=False,
    )

    response_generator = team.run(
        "Analyse and then solve the problem: 'solve 10 factorial'", stream=True, stream_intermediate_steps=True
    )

    events = {}
    for run_response_delta in response_generator:
        if run_response_delta.event not in events:
            events[run_response_delta.event] = []
        events[run_response_delta.event].append(run_response_delta)

    assert events.keys() == {
        TeamRunEvent.run_started,
        TeamRunEvent.tool_call_started,
        TeamRunEvent.tool_call_completed,
        TeamRunEvent.run_content,
        TeamRunEvent.run_completed,
    }

    assert len(events[TeamRunEvent.run_started]) == 1
    # Transfer twice, from team to member agents
    assert len(events[TeamRunEvent.tool_call_started]) == 2
    assert events[TeamRunEvent.tool_call_started][0].tool.tool_name == "delegate_task_to_member"
    assert events[TeamRunEvent.tool_call_started][0].tool.tool_args["member_id"] == "analyst"
    assert events[TeamRunEvent.tool_call_started][1].tool.tool_name == "delegate_task_to_member"
    assert events[TeamRunEvent.tool_call_started][1].tool.tool_args["member_id"] == "math-agent"
    assert len(events[TeamRunEvent.tool_call_completed]) == 2
    assert events[TeamRunEvent.tool_call_completed][0].tool.tool_name == "delegate_task_to_member"
    assert events[TeamRunEvent.tool_call_completed][0].tool.result is not None
    assert events[TeamRunEvent.tool_call_completed][1].tool.tool_name == "delegate_task_to_member"
    assert events[TeamRunEvent.tool_call_completed][1].tool.result is not None
    assert len(events[TeamRunEvent.run_content]) > 1
    assert len(events[TeamRunEvent.run_completed]) == 1


def test_create_team_run_completed_event_function():
    """Test that create_team_run_completed_event function properly transfers metadata and metrics."""
    from agno.models.metrics import Metrics
    from agno.run.team import TeamRunOutput
    from agno.utils.events import create_team_run_completed_event

    mock_metrics = Metrics(input_tokens=200, output_tokens=75, total_tokens=275, duration=3.2)
    mock_metadata = {"team_key": "team_value", "execution_mode": "collaborate"}

    mock_team_run_output = TeamRunOutput(
        session_id="test_team_session",
        team_id="test_team",
        team_name="Test Team",
        run_id="test_team_run",
        content="Team test content",
        metrics=mock_metrics,
        metadata=mock_metadata,
    )

    # Create the Completed Event
    completed_event = create_team_run_completed_event(mock_team_run_output)

    assert completed_event.metadata == mock_metadata
    assert completed_event.metrics == mock_metrics
    assert completed_event.metrics.total_tokens == 275
    assert completed_event.metrics.duration == 3.2
    assert completed_event.content == "Team test content"
    assert completed_event.session_id == "test_team_session"
    assert completed_event.team_id == "test_team"


# @pytest.mark.skip(reason="This test is flaky")
def test_intermediate_steps_with_member_agents_delegate_to_all_members():
    def get_news_from_hackernews(query: str):
        return "The best way to learn to code is to use the Hackernews API."

    def get_news_from_duckduckgo(query: str):
        return "The best way to learn to code is to use the DuckDuckGo API."

    agent_1 = Agent(
        name="Web Researcher",
        model=OpenAIChat(id="o3-mini"),
        instructions="You are an expert web researcher with strong analytical skills! Use your tools to find answers to questions.",
        tools=[get_news_from_duckduckgo],
        stream_intermediate_steps=True,
    )
    agent_2 = Agent(
        name="Hackernews Researcher",
        model=OpenAIChat(id="o3-mini"),
        instructions="You are an expert hackernews researcher with strong analytical skills! Use your tools to find answers to questions.",
        tools=[get_news_from_hackernews],
        stream_intermediate_steps=True,
    )
    team = Team(
        model=OpenAIChat(id="o3-mini"),
        members=[agent_1, agent_2],
        telemetry=False,
        delegate_task_to_all_members=True,
        instructions="You are a discussion master. Forward the task to the member agents.",
    )

    response_generator = team.run(
        input="Start the discussion on the topic: 'What is the best way to learn to code?'",
        stream=True,
        stream_intermediate_steps=True,
    )

    events = {}
    for run_response_delta in response_generator:
        if run_response_delta.event not in events:
            events[run_response_delta.event] = []
        events[run_response_delta.event].append(run_response_delta)

    assert len(events[TeamRunEvent.run_started]) == 1

    # Assert expected events from team
    assert len(events[TeamRunEvent.tool_call_started]) == 1
    assert len(events[TeamRunEvent.run_content]) > 1
    assert len(events[TeamRunEvent.run_completed]) == 1

    # Assert expected tool call events
    assert events[TeamRunEvent.tool_call_started][0].tool.tool_name == "delegate_task_to_members"
    assert len(events[TeamRunEvent.tool_call_completed]) == 1
    assert events[TeamRunEvent.tool_call_completed][0].tool.tool_name == "delegate_task_to_members"
    assert events[TeamRunEvent.tool_call_completed][0].tool.result is not None

    # Assert expected events from members
    assert len(events[RunEvent.run_started]) == 2
    assert len(events[RunEvent.run_completed]) == 2
    assert len(events[RunEvent.run_content]) > 1
