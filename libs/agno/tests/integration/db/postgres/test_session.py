"""Integration tests for the Session related methods of the PostgresDb class"""

import time
from datetime import datetime

import pytest
from sqlalchemy import text

from agno.db.base import SessionType
from agno.db.postgres.postgres import PostgresDb
from agno.run.agent import RunOutput
from agno.run.base import RunStatus
from agno.run.team import TeamRunOutput
from agno.session.agent import AgentSession
from agno.session.summary import SessionSummary
from agno.session.team import TeamSession


@pytest.fixture(autouse=True)
def cleanup_sessions(postgres_db_real: PostgresDb):
    """Fixture to clean-up session rows after each test"""
    yield

    with postgres_db_real.Session() as session:
        try:
            sessions_table = postgres_db_real._get_table("sessions")
            session.execute(sessions_table.delete())
            session.commit()
        except Exception:
            session.rollback()


@pytest.fixture
def sample_agent_session() -> AgentSession:
    """Fixture returning a sample AgentSession"""
    agent_run = RunOutput(
        run_id="test_agent_run_1",
        agent_id="test_agent_1",
        user_id="test_user_1",
        status=RunStatus.completed,
        messages=[],
    )
    return AgentSession(
        session_id="test_agent_session_1",
        agent_id="test_agent_1",
        user_id="test_user_1",
        team_id="test_team_1",
        session_data={"session_name": "Test Agent Session", "key": "value"},
        agent_data={"name": "Test Agent", "model": "gpt-4"},
        metadata={"extra_key": "extra_value"},
        runs=[agent_run],
        summary=None,
        created_at=int(time.time()),
        updated_at=int(time.time()),
    )


@pytest.fixture
def sample_team_session() -> TeamSession:
    """Fixture returning a sample TeamSession"""
    team_run = TeamRunOutput(
        run_id="test_team_run_1",
        team_id="test_team_1",
        status=RunStatus.completed,
        messages=[],
        created_at=int(time.time()),
    )
    return TeamSession(
        session_id="test_team_session_1",
        team_id="test_team_1",
        user_id="test_user_1",
        session_data={"session_name": "Test Team Session", "key": "value"},
        team_data={"name": "Test Team", "model": "gpt-4"},
        metadata={"extra_key": "extra_value"},
        runs=[team_run],
        summary=None,
        created_at=int(time.time()),
        updated_at=int(time.time()),
    )


def test_session_table_constraint_exists(postgres_db_real: PostgresDb):
    """Ensure the session table has the expected unique constraint on session_id"""
    with postgres_db_real.Session() as session:
        # Dummy call to ensure schema and table creation
        postgres_db_real.get_sessions(session_type=SessionType.AGENT)

        result = session.execute(
            text(
                "SELECT constraint_name FROM information_schema.table_constraints "
                "WHERE table_schema = :schema AND table_name = :table AND constraint_type = 'UNIQUE'"
            ),
            {"schema": postgres_db_real.db_schema, "table": "test_sessions"},
        )
        constraint_names = [row[0] for row in result.fetchall()]
        expected_constraint = "test_sessions_uq_session_id"
        assert expected_constraint in constraint_names, (
            f"Session table missing unique constraint {expected_constraint}. Found: {constraint_names}"
        )


def test_insert_agent_session(postgres_db_real: PostgresDb, sample_agent_session: AgentSession):
    """Ensure the upsert method works as expected when inserting a new AgentSession"""
    result = postgres_db_real.upsert_session(sample_agent_session)

    assert result is not None
    assert isinstance(result, AgentSession)
    assert result.session_id == sample_agent_session.session_id
    assert result.agent_id == sample_agent_session.agent_id
    assert result.user_id == sample_agent_session.user_id
    assert result.session_data == sample_agent_session.session_data
    assert result.agent_data == sample_agent_session.agent_data


def test_update_agent_session(postgres_db_real: PostgresDb, sample_agent_session: AgentSession):
    """Ensure the upsert method works as expected when updating an existing AgentSession"""
    # Inserting
    postgres_db_real.upsert_session(sample_agent_session)

    # Updating
    sample_agent_session.session_data = {"session_name": "Updated Session", "updated": True}
    sample_agent_session.agent_data = {"foo": "bar"}

    result = postgres_db_real.upsert_session(sample_agent_session)

    assert result is not None
    assert isinstance(result, AgentSession)
    assert result.session_data is not None
    assert result.session_data["session_name"] == "Updated Session"
    assert result.agent_data is not None
    assert result.agent_data["foo"] == "bar"

    # Assert Agent runs
    assert result.runs is not None and result.runs[0] is not None
    assert sample_agent_session.runs is not None and sample_agent_session.runs[0] is not None
    assert result.runs[0].run_id == sample_agent_session.runs[0].run_id


def test_insert_team_session(postgres_db_real: PostgresDb, sample_team_session: TeamSession):
    """Ensure the upsert method works as expected when inserting a new TeamSession"""
    result = postgres_db_real.upsert_session(sample_team_session)

    assert result is not None
    assert isinstance(result, TeamSession)
    assert result.session_id == sample_team_session.session_id
    assert result.team_id == sample_team_session.team_id
    assert result.user_id == sample_team_session.user_id
    assert result.session_data == sample_team_session.session_data
    assert result.team_data == sample_team_session.team_data

    # Assert Team runs
    assert result.runs is not None and result.runs[0] is not None
    assert sample_team_session.runs is not None and sample_team_session.runs[0] is not None
    assert result.runs[0].run_id == sample_team_session.runs[0].run_id


def test_update_team_session(postgres_db_real: PostgresDb, sample_team_session: TeamSession):
    """Ensure the upsert method works as expected when updating an existing TeamSession"""
    # Inserting
    postgres_db_real.upsert_session(sample_team_session)

    # Update
    sample_team_session.session_data = {"session_name": "Updated Team Session", "updated": True}
    sample_team_session.team_data = {"foo": "bar"}

    result = postgres_db_real.upsert_session(sample_team_session)

    assert result is not None
    assert isinstance(result, TeamSession)
    assert result.session_data is not None
    assert result.session_data["session_name"] == "Updated Team Session"
    assert result.team_data is not None
    assert result.team_data["foo"] == "bar"


def test_upserting_without_deserialization(postgres_db_real: PostgresDb, sample_agent_session: AgentSession):
    """Ensure the upsert method works as expected when upserting a session without deserialization"""
    result = postgres_db_real.upsert_session(sample_agent_session, deserialize=False)

    assert result is not None
    assert isinstance(result, dict)
    assert result["session_id"] == sample_agent_session.session_id


def test_get_agent_session_by_id(postgres_db_real: PostgresDb, sample_agent_session: AgentSession):
    """Ensure the get_session method works as expected when retrieving an AgentSession by session_id"""
    # Insert session first
    postgres_db_real.upsert_session(sample_agent_session)

    # Retrieve session
    result = postgres_db_real.get_session(session_id=sample_agent_session.session_id, session_type=SessionType.AGENT)

    assert result is not None
    assert isinstance(result, AgentSession)
    assert result.session_id == sample_agent_session.session_id
    assert result.agent_id == sample_agent_session.agent_id


def test_get_team_session_by_id(postgres_db_real: PostgresDb, sample_team_session: TeamSession):
    """Ensure the get_session method works as expected when retrieving a TeamSession by session_id"""
    # Insert session first
    postgres_db_real.upsert_session(sample_team_session)

    # Retrieve session
    result = postgres_db_real.get_session(session_id=sample_team_session.session_id, session_type=SessionType.TEAM)

    assert result is not None
    assert isinstance(result, TeamSession)
    assert result.session_id == sample_team_session.session_id
    assert result.team_id == sample_team_session.team_id


def test_get_session_with_user_id_filter(postgres_db_real: PostgresDb, sample_agent_session: AgentSession):
    """Ensure the get_session method works as expected when retrieving a session with user_id filter"""
    # Insert session
    postgres_db_real.upsert_session(sample_agent_session)

    # Get with correct user_id
    result = postgres_db_real.get_session(
        session_id=sample_agent_session.session_id,
        user_id=sample_agent_session.user_id,
        session_type=SessionType.AGENT,
    )
    assert result is not None

    # Get with wrong user_id
    result = postgres_db_real.get_session(
        session_id=sample_agent_session.session_id,
        user_id="wrong_user",
        session_type=SessionType.AGENT,
    )
    assert result is None


def test_get_session_without_deserialization(postgres_db_real: PostgresDb, sample_agent_session: AgentSession):
    """Ensure the get_session method works as expected when retrieving a session without deserialization"""
    # Insert session
    postgres_db_real.upsert_session(sample_agent_session)

    # Retrieve as dict
    result = postgres_db_real.get_session(
        session_id=sample_agent_session.session_id, session_type=SessionType.AGENT, deserialize=False
    )

    assert result is not None
    assert isinstance(result, dict)
    assert result["session_id"] == sample_agent_session.session_id


def test_get_all_sessions(
    postgres_db_real: PostgresDb,
    sample_agent_session: AgentSession,
    sample_team_session: TeamSession,
):
    """Ensure the get_sessions method works as expected when retrieving all sessions"""
    # Insert both sessions
    postgres_db_real.upsert_session(sample_agent_session)
    postgres_db_real.upsert_session(sample_team_session)

    # Get all agent sessions
    agent_sessions = postgres_db_real.get_sessions(session_type=SessionType.AGENT)
    assert len(agent_sessions) == 1
    assert isinstance(agent_sessions[0], AgentSession)

    # Get all team sessions
    team_sessions = postgres_db_real.get_sessions(session_type=SessionType.TEAM)
    assert len(team_sessions) == 1
    assert isinstance(team_sessions[0], TeamSession)


def test_filtering_by_user_id(postgres_db_real: PostgresDb):
    """Ensure the get_sessions method works as expected when filtering by user_id"""
    # Create sessions with different user_ids
    session1 = AgentSession(session_id="session1", agent_id="agent1", user_id="user1", created_at=int(time.time()))
    session2 = AgentSession(session_id="session2", agent_id="agent2", user_id="user2", created_at=int(time.time()))

    postgres_db_real.upsert_session(session1)
    postgres_db_real.upsert_session(session2)

    # Filter by user1
    user1_sessions = postgres_db_real.get_sessions(session_type=SessionType.AGENT, user_id="user1")
    assert len(user1_sessions) == 1
    assert user1_sessions[0].user_id == "user1"


def test_filtering_by_component_id(postgres_db_real: PostgresDb):
    """Ensure the get_sessions method works as expected when filtering by component_id (agent_id/team_id)"""
    # Create sessions with different agent_ids
    session1 = AgentSession(session_id="session1", agent_id="agent1", user_id="user1", created_at=int(time.time()))
    session2 = AgentSession(session_id="session2", agent_id="agent2", user_id="user1", created_at=int(time.time()))

    postgres_db_real.upsert_session(session1)
    postgres_db_real.upsert_session(session2)

    # Filter by agent_id
    agent1_sessions = postgres_db_real.get_sessions(
        session_type=SessionType.AGENT,
        component_id="agent1",
    )
    assert len(agent1_sessions) == 1
    assert isinstance(agent1_sessions[0], AgentSession)
    assert agent1_sessions[0].agent_id == "agent1"


def test_get_sessions_with_pagination(postgres_db_real: PostgresDb):
    """Test retrieving sessions with pagination"""

    # Create multiple sessions
    sessions = []
    for i in range(5):
        session = AgentSession(
            session_id=f"session_{i}", agent_id=f"agent_{i}", user_id="test_user", created_at=int(time.time()) + i
        )
        sessions.append(session)
        postgres_db_real.upsert_session(session)

    # Test pagination
    page1 = postgres_db_real.get_sessions(session_type=SessionType.AGENT, limit=2, page=1)
    assert len(page1) == 2

    page2 = postgres_db_real.get_sessions(session_type=SessionType.AGENT, limit=2, page=2)
    assert len(page2) == 2

    # Verify no overlap
    assert isinstance(page1, list) and isinstance(page2, list)
    page1_ids = {s.session_id for s in page1}
    page2_ids = {s.session_id for s in page2}
    assert len(page1_ids & page2_ids) == 0


def test_get_sessions_with_sorting(postgres_db_real: PostgresDb):
    """Test retrieving sessions with sorting"""
    from agno.db.base import SessionType
    from agno.session.agent import AgentSession

    # Create sessions with different timestamps
    base_time = int(time.time())
    session1 = AgentSession(session_id="session1", agent_id="agent1", created_at=base_time + 100)
    session2 = AgentSession(session_id="session2", agent_id="agent2", created_at=base_time + 200)

    postgres_db_real.upsert_session(session1)
    postgres_db_real.upsert_session(session2)

    # Sort by created_at ascending
    sessions_asc = postgres_db_real.get_sessions(session_type=SessionType.AGENT, sort_by="created_at", sort_order="asc")
    assert sessions_asc is not None and isinstance(sessions_asc, list)
    assert sessions_asc[0].session_id == "session1"
    assert sessions_asc[1].session_id == "session2"

    # Sort by created_at descending
    sessions_desc = postgres_db_real.get_sessions(
        session_type=SessionType.AGENT, sort_by="created_at", sort_order="desc"
    )
    assert sessions_desc is not None and isinstance(sessions_desc, list)
    assert sessions_desc[0].session_id == "session2"
    assert sessions_desc[1].session_id == "session1"


def test_get_sessions_with_timestamp_filter(postgres_db_real: PostgresDb):
    """Test retrieving sessions with timestamp filters"""
    from agno.db.base import SessionType
    from agno.session.agent import AgentSession

    base_time = int(time.time())

    # Create sessions at different times
    session1 = AgentSession(
        session_id="session1",
        agent_id="agent1",
        created_at=base_time - 1000,  # Old session
    )
    session2 = AgentSession(
        session_id="session2",
        agent_id="agent2",
        created_at=base_time + 1000,  # New session
    )

    postgres_db_real.upsert_session(session1)
    postgres_db_real.upsert_session(session2)

    # Filter by start timestamp
    recent_sessions = postgres_db_real.get_sessions(session_type=SessionType.AGENT, start_timestamp=base_time)
    assert len(recent_sessions) == 1
    assert recent_sessions[0].session_id == "session2"

    # Filter by end timestamp
    old_sessions = postgres_db_real.get_sessions(session_type=SessionType.AGENT, end_timestamp=base_time)
    assert len(old_sessions) == 1
    assert old_sessions[0].session_id == "session1"


def test_get_sessions_with_session_name_filter(postgres_db_real: PostgresDb):
    """Test retrieving sessions filtered by session name"""
    from agno.db.base import SessionType
    from agno.session.agent import AgentSession

    # Create sessions with different names
    session1 = AgentSession(
        session_id="session1",
        agent_id="agent1",
        session_data={"session_name": "Test Session Alpha"},
        created_at=int(time.time()),
    )
    session2 = AgentSession(
        session_id="session2",
        agent_id="agent2",
        session_data={"session_name": "Test Session Beta"},
        created_at=int(time.time()),
    )

    postgres_db_real.upsert_session(session1)
    postgres_db_real.upsert_session(session2)

    # Search by partial name
    alpha_sessions = postgres_db_real.get_sessions(session_type=SessionType.AGENT, session_name="Alpha")
    assert len(alpha_sessions) == 1
    assert alpha_sessions[0].session_id == "session1"


def test_get_sessions_without_deserialize(postgres_db_real: PostgresDb, sample_agent_session: AgentSession):
    """Test retrieving sessions without deserialization"""
    from agno.db.base import SessionType

    # Insert session
    postgres_db_real.upsert_session(sample_agent_session)

    # Get as dicts
    sessions, total_count = postgres_db_real.get_sessions(session_type=SessionType.AGENT, deserialize=False)

    assert isinstance(sessions, list)
    assert len(sessions) == 1
    assert isinstance(sessions[0], dict)
    assert sessions[0]["session_id"] == sample_agent_session.session_id
    assert total_count == 1


def test_rename_agent_session(postgres_db_real: PostgresDb, sample_agent_session: AgentSession):
    """Test renaming an AgentSession"""
    from agno.db.base import SessionType

    # Insert session
    postgres_db_real.upsert_session(sample_agent_session)

    # Rename session
    new_name = "Renamed Agent Session"
    result = postgres_db_real.rename_session(
        session_id=sample_agent_session.session_id,
        session_type=SessionType.AGENT,
        session_name=new_name,
    )

    assert result is not None
    assert isinstance(result, AgentSession)
    assert result.session_data is not None
    assert result.session_data["session_name"] == new_name


def test_rename_team_session(postgres_db_real: PostgresDb, sample_team_session: TeamSession):
    """Test renaming a TeamSession"""
    from agno.db.base import SessionType

    # Insert session
    postgres_db_real.upsert_session(sample_team_session)

    # Rename session
    new_name = "Renamed Team Session"
    result = postgres_db_real.rename_session(
        session_id=sample_team_session.session_id,
        session_type=SessionType.TEAM,
        session_name=new_name,
    )

    assert result is not None
    assert isinstance(result, TeamSession)
    assert result.session_data is not None
    assert result.session_data["session_name"] == new_name


def test_rename_session_without_deserialize(postgres_db_real: PostgresDb, sample_agent_session: AgentSession):
    """Test renaming session without deserialization"""
    from agno.db.base import SessionType

    # Insert session
    postgres_db_real.upsert_session(sample_agent_session)

    # Rename session
    new_name = "Renamed Session Dict"
    result = postgres_db_real.rename_session(
        session_id=sample_agent_session.session_id,
        session_type=SessionType.AGENT,
        session_name=new_name,
        deserialize=False,
    )

    assert result is not None
    assert isinstance(result, dict)
    assert result["session_data"]["session_name"] == new_name


def test_delete_single_session(postgres_db_real: PostgresDb, sample_agent_session: AgentSession):
    """Test deleting a single session"""
    # Insert session
    postgres_db_real.upsert_session(sample_agent_session)

    # Verify it exists
    from agno.db.base import SessionType

    session = postgres_db_real.get_session(session_id=sample_agent_session.session_id, session_type=SessionType.AGENT)
    assert session is not None

    # Delete session
    success = postgres_db_real.delete_session(sample_agent_session.session_id)
    assert success is True

    # Verify it's gone
    session = postgres_db_real.get_session(session_id=sample_agent_session.session_id, session_type=SessionType.AGENT)
    assert session is None


def test_delete_multiple_sessions(postgres_db_real: PostgresDb):
    """Test deleting multiple sessions"""
    from agno.db.base import SessionType
    from agno.session.agent import AgentSession

    # Create and insert multiple sessions
    sessions = []
    session_ids = []
    for i in range(3):
        session = AgentSession(session_id=f"session_{i}", agent_id=f"agent_{i}", created_at=int(time.time()))
        sessions.append(session)
        session_ids.append(session.session_id)
        postgres_db_real.upsert_session(session)

    # Verify they exist
    all_sessions = postgres_db_real.get_sessions(session_type=SessionType.AGENT)
    assert len(all_sessions) == 3

    # Delete multiple sessions
    postgres_db_real.delete_sessions(session_ids[:2])  # Delete first 2

    # Verify deletion
    remaining_sessions = postgres_db_real.get_sessions(session_type=SessionType.AGENT)
    assert len(remaining_sessions) == 1
    assert remaining_sessions[0].session_id == "session_2"


def test_session_type_polymorphism(
    postgres_db_real: PostgresDb, sample_agent_session: AgentSession, sample_team_session: TeamSession
):
    """Ensuring session types propagate into types correctly into and out of the database"""

    # Insert both session types
    postgres_db_real.upsert_session(sample_agent_session)
    postgres_db_real.upsert_session(sample_team_session)

    # Verify agent session is returned as AgentSession
    agent_result = postgres_db_real.get_session(
        session_id=sample_agent_session.session_id, session_type=SessionType.AGENT
    )
    assert isinstance(agent_result, AgentSession)

    # Verify team session is returned as TeamSession
    team_result = postgres_db_real.get_session(session_id=sample_team_session.session_id, session_type=SessionType.TEAM)
    assert isinstance(team_result, TeamSession)

    # Verify wrong session type returns None
    wrong_type_result = postgres_db_real.get_session(
        session_id=sample_agent_session.session_id,
        # Wrong session type!
        session_type=SessionType.TEAM,
    )
    assert wrong_type_result is None


def test_upsert_session_handles_all_agent_session_fields(postgres_db_real: PostgresDb):
    """Ensure upsert_session correctly handles all AgentSession fields"""
    # Create comprehensive AgentSession with all possible fields populated
    agent_run = RunOutput(
        run_id="test_run_comprehensive",
        agent_id="comprehensive_agent",
        user_id="comprehensive_user",
        status=RunStatus.completed,
        messages=[],
    )

    comprehensive_agent_session = AgentSession(
        session_id="comprehensive_agent_session",
        agent_id="comprehensive_agent_id",
        user_id="comprehensive_user_id",
        session_data={
            "session_name": "Comprehensive Agent Session",
            "session_state": {"key": "value"},
            "images": ["image1.jpg", "image2.png"],
            "videos": ["video1.mp4"],
            "audio": ["audio1.wav"],
            "custom_field": "custom_value",
        },
        metadata={"extra_key1": "extra_value1", "extra_key2": {"nested": "data"}, "extra_list": [1, 2, 3]},
        agent_data={
            "name": "Comprehensive Agent",
            "model": "gpt-4",
            "description": "A comprehensive test agent",
            "capabilities": ["chat", "search", "analysis"],
        },
        runs=[agent_run],
        summary=None,
        created_at=int(time.time()),
        updated_at=int(time.time()),
    )

    # Insert session
    result = postgres_db_real.upsert_session(comprehensive_agent_session)
    assert result is not None
    assert isinstance(result, AgentSession)

    # Verify all fields are preserved
    assert result.session_id == comprehensive_agent_session.session_id
    assert result.agent_id == comprehensive_agent_session.agent_id
    assert result.team_id == comprehensive_agent_session.team_id
    assert result.user_id == comprehensive_agent_session.user_id
    assert result.session_data == comprehensive_agent_session.session_data
    assert result.metadata == comprehensive_agent_session.metadata
    assert result.agent_data == comprehensive_agent_session.agent_data
    assert result.created_at == comprehensive_agent_session.created_at
    assert result.updated_at == comprehensive_agent_session.updated_at
    assert result.runs is not None
    assert len(result.runs) == 1
    assert result.runs[0].run_id == agent_run.run_id


def test_upsert_session_handles_all_team_session_fields(postgres_db_real: PostgresDb):
    """Ensure upsert_session correctly handles all TeamSession fields"""
    # Create comprehensive TeamSession with all possible fields populated
    team_run = TeamRunOutput(
        run_id="test_team_run_comprehensive",
        team_id="comprehensive_team",
        status=RunStatus.completed,
        messages=[],
        created_at=int(time.time()),
    )
    team_summary = SessionSummary(
        summary="Comprehensive team session summary",
        topics=["tests", "fake"],
        updated_at=datetime.now(),
    )

    comprehensive_team_session = TeamSession(
        session_id="comprehensive_team_session",
        team_id="comprehensive_team_id",
        user_id="comprehensive_user_id",
        team_data={
            "name": "Comprehensive Team",
            "model": "gpt-4",
            "description": "A comprehensive test team",
            "members": ["agent1", "agent2", "agent3"],
            "strategy": "collaborative",
        },
        session_data={
            "session_name": "Comprehensive Team Session",
            "session_state": {"phase": "active"},
            "images": ["team_image1.jpg"],
            "videos": ["team_video1.mp4"],
            "audio": ["team_audio1.wav"],
            "team_custom_field": "team_custom_value",
        },
        metadata={
            "team_extra_key1": "team_extra_value1",
            "team_extra_key2": {"nested": "team_data"},
            "team_metrics": {"efficiency": 0.95},
        },
        runs=[team_run],
        summary=team_summary,
        created_at=int(time.time()),
        updated_at=int(time.time()),
    )

    # Insert session
    result = postgres_db_real.upsert_session(comprehensive_team_session)
    assert result is not None
    assert isinstance(result, TeamSession)

    # Verify all fields are preserved
    assert result.session_id == comprehensive_team_session.session_id
    assert result.team_id == comprehensive_team_session.team_id
    assert result.user_id == comprehensive_team_session.user_id
    assert result.team_data == comprehensive_team_session.team_data
    assert result.session_data == comprehensive_team_session.session_data
    assert result.metadata == comprehensive_team_session.metadata
    assert isinstance(result.summary, SessionSummary)
    assert result.summary == comprehensive_team_session.summary
    assert result.created_at == comprehensive_team_session.created_at
    assert result.updated_at == comprehensive_team_session.updated_at
    assert result.runs is not None
    assert len(result.runs) == 1
    assert result.runs[0].run_id == team_run.run_id
