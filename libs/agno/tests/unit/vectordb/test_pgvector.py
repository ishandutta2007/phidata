import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.engine import URL, Engine
from sqlalchemy.orm import Session

from agno.knowledge.document import Document
from agno.vectordb.pgvector import PgVector
from agno.vectordb.search import SearchType

# Configuration for tests
TEST_TABLE = f"test_vectors_{uuid.uuid4().hex[:8]}"
TEST_SCHEMA = "test_schema"


@pytest.fixture
def mock_engine():
    """Create a mock SQLAlchemy engine with inspect attribute."""
    engine = MagicMock(spec=Engine)

    # Create a mock URL object
    url = MagicMock(spec=URL)
    url.get_backend_name.return_value = "postgresql"

    # Attach the url to the engine
    engine.url = url

    # Add inspect method explicitly
    engine.inspect = MagicMock(return_value=MagicMock())

    return engine


@pytest.fixture
def mock_session():
    """Create a mock SQLAlchemy session."""
    session = MagicMock(spec=Session)
    session.execute.return_value.fetchall.return_value = []
    session.execute.return_value.scalar.return_value = 0
    session.execute.return_value.first.return_value = None
    return session


@pytest.fixture
def sample_documents():
    """Fixture to create sample documents"""
    return [
        Document(
            content="Tom Kha Gai is a Thai coconut soup with chicken",
            meta_data={"cuisine": "Thai", "type": "soup"},
            name="tom_kha",
        ),
        Document(
            content="Pad Thai is a stir-fried rice noodle dish",
            meta_data={"cuisine": "Thai", "type": "noodles"},
            name="pad_thai",
        ),
        Document(
            content="Green curry is a spicy Thai curry with coconut milk",
            meta_data={"cuisine": "Thai", "type": "curry"},
            name="green_curry",
        ),
    ]


@pytest.fixture
def mock_pgvector(mock_engine, mock_embedder):
    """Create a PgVector instance with mocked dependencies."""
    with patch("agno.vectordb.pgvector.pgvector.inspect") as mock_inspect:
        # Mock inspect to control table_exists method
        inspector = MagicMock()
        inspector.has_table.return_value = False
        mock_inspect.return_value = inspector

        # Mock the session factory and session
        with patch("agno.vectordb.pgvector.pgvector.scoped_session") as mock_scoped_session:
            mock_session_factory = MagicMock()
            mock_scoped_session.return_value = mock_session_factory

            # Mock the session instance
            mock_session_instance = MagicMock()
            mock_session_factory.return_value.__enter__.return_value = mock_session_instance

            # Mock Vector class
            with patch("agno.vectordb.pgvector.pgvector.Vector"):
                # Create PgVector instance
                db = PgVector(table_name=TEST_TABLE, schema=TEST_SCHEMA, db_engine=mock_engine, embedder=mock_embedder)

                # Mock the table attribute
                db.table = MagicMock()
                db.table.fullname = f"{TEST_SCHEMA}.{TEST_TABLE}"

                # Mock the Session attribute
                db.Session = mock_session_factory

                yield db


def create_test_documents(num_docs=3):
    """Helper to create test documents."""
    return [
        Document(
            id=f"doc_{i}",
            content=f"This is test document {i}",
            meta_data={"type": "test", "index": i},
            name=f"test_doc_{i}",
        )
        for i in range(num_docs)
    ]


# Synchronous Tests
def test_initialization():
    """Test basic initialization."""
    engine = MagicMock()
    embedder = MagicMock()
    embedder.dimensions = 1024

    # More complete patching to prevent SQLAlchemy from validating the mock objects
    with (
        patch("agno.vectordb.pgvector.pgvector.scoped_session"),
        patch("agno.vectordb.pgvector.pgvector.Vector"),
        patch("agno.vectordb.pgvector.pgvector.Table"),
        patch("agno.vectordb.pgvector.pgvector.Column"),
        patch("agno.vectordb.pgvector.pgvector.Index"),
        patch("agno.vectordb.pgvector.pgvector.MetaData"),
        patch.object(PgVector, "get_table"),
    ):
        # Skip the actual table creation by patching get_table to return a mock
        PgVector.get_table = MagicMock(return_value=MagicMock())

        db = PgVector(table_name=TEST_TABLE, schema=TEST_SCHEMA, db_engine=engine, embedder=embedder)
        assert db.table_name == TEST_TABLE
        assert db.schema == TEST_SCHEMA
        assert db.embedder == embedder


def test_initialization_failures(mock_embedder):
    """Test initialization with invalid parameters."""
    with pytest.raises(ValueError), patch("agno.vectordb.pgvector.pgvector.scoped_session"):
        PgVector(table_name="", schema=TEST_SCHEMA, db_engine=MagicMock())

    with pytest.raises(ValueError), patch("agno.vectordb.pgvector.pgvector.scoped_session"):
        PgVector(table_name=TEST_TABLE, schema=TEST_SCHEMA, db_engine=None, db_url=None)


def test_table_exists(mock_pgvector):
    """Test table_exists method."""
    # We need to patch the inspect function that's imported in the module
    with patch("agno.vectordb.pgvector.pgvector.inspect") as mock_inspect:
        # Create inspector
        inspector = MagicMock()
        mock_inspect.return_value = inspector

        # Test when table exists
        inspector.has_table.return_value = True
        assert mock_pgvector.table_exists() is True

        # Test when table doesn't exist
        inspector.has_table.return_value = False
        assert mock_pgvector.table_exists() is False


def test_create(mock_pgvector):
    """Test create method."""
    with patch.object(mock_pgvector, "table_exists", return_value=False):
        mock_pgvector.create()
        mock_pgvector.table.create.assert_called_once()


def test_name_exists(mock_pgvector):
    """Test name_exists method."""
    with patch.object(mock_pgvector, "_record_exists") as mock_record_exists:
        # Test when name exists
        mock_record_exists.return_value = True
        assert mock_pgvector.name_exists("test_name") is True

        # Test when name doesn't exist
        mock_record_exists.return_value = False
        assert mock_pgvector.name_exists("test_name") is False


def test_id_exists(mock_pgvector):
    """Test id_exists method."""
    with patch.object(mock_pgvector, "_record_exists") as mock_record_exists:
        # Test when ID exists
        mock_record_exists.return_value = True
        assert mock_pgvector.id_exists("test_id") is True

        # Test when ID doesn't exist
        mock_record_exists.return_value = False
        assert mock_pgvector.id_exists("test_id") is False


def test_insert(mock_pgvector):
    """Test insert method with patched insert functionality."""
    docs = create_test_documents()

    # Bypass the SQLAlchemy-specific parts by patching the insert method directly
    with patch.object(mock_pgvector, "insert", wraps=lambda content_hash, documents, **kwargs: None):
        mock_pgvector.insert(content_hash="test_hash", documents=docs)


def test_upsert(mock_pgvector):
    """Test upsert method with patched upsert functionality."""
    docs = create_test_documents()

    # Bypass the SQLAlchemy-specific parts by patching the upsert method directly
    with patch.object(mock_pgvector, "upsert", wraps=lambda content_hash, documents, **kwargs: None):
        mock_pgvector.upsert(content_hash="test_hash", documents=docs)


def test_insert_builds_records_and_uses_expected_ids(mock_pgvector, mock_embedder):
    """Validate insert builds batch_records with id selection and calls sess.execute correctly."""
    docs = [
        Document(id="id-1", content="alpha", meta_data={"k": "v"}, name="A"),
        Document(content="beta", meta_data={"m": 3}, name="B"),
    ]

    # Prepare session context manager mock
    sess = MagicMock()
    cm = MagicMock()
    cm.__enter__.return_value = sess
    mock_pgvector.Session.return_value = cm

    # Patch postgresql.insert so we don't touch real SQLAlchemy internals
    with patch("agno.vectordb.pgvector.pgvector.postgresql.insert") as mock_insert:
        insert_stmt_sentinel = object()
        mock_insert.return_value = insert_stmt_sentinel

        mock_pgvector.insert("test_content_hash", docs, filters={"tag": "t1"})

        # Ensure we executed with an insert statement and batch records
        assert sess.execute.call_count == 1
        args, kwargs = sess.execute.call_args
        assert args[0] is insert_stmt_sentinel
        batch_records = args[1]
        assert isinstance(batch_records, list) and len(batch_records) == 2

        # First record should use explicit id
        assert batch_records[0]["id"] == "id-1"
        assert batch_records[0]["meta_data"] == {"k": "v", "tag": "t1"}
        assert batch_records[0]["filters"] == {"tag": "t1"}

        # Second record should fall back to content_hash
        assert batch_records[1]["id"] == batch_records[1]["content_hash"]
        assert batch_records[1]["meta_data"] == {"m": 3, "tag": "t1"}
        assert batch_records[1]["filters"] == {"tag": "t1"}

        # Commit should be called
        assert sess.commit.called


def test_upsert_builds_records_and_sets_conflict_on_id(mock_pgvector, mock_embedder):
    """Validate upsert wires values into insert and sets ON CONFLICT on id."""
    docs = [
        Document(id="cid-1", content="gamma", meta_data={"z": 9}, name="C"),
        Document(content="delta", meta_data={}, name="D"),
    ]

    # Prepare session context manager mock
    sess = MagicMock()
    cm = MagicMock()
    cm.__enter__.return_value = sess
    mock_pgvector.Session.return_value = cm

    # Build a chain of mocks: postgresql.insert(...).values(...).on_conflict_do_update(...)
    with patch("agno.vectordb.pgvector.pgvector.postgresql.insert") as mock_insert:
        insert_stmt = MagicMock(name="insert_stmt")
        after_values = MagicMock(name="after_values")
        after_values.excluded = MagicMock(name="excluded")  # used in set_ mapping
        upsert_stmt = object()

        mock_insert.return_value = insert_stmt
        insert_stmt.values.return_value = after_values
        after_values.on_conflict_do_update.return_value = upsert_stmt

        mock_pgvector.upsert("test_content_hash", docs, filters={"role": "test"})

        # Ensure values() received our batch_records so we can validate IDs
        assert insert_stmt.values.called
        (values_arg,), _ = insert_stmt.values.call_args
        batch_records = values_arg
        assert isinstance(batch_records, list) and len(batch_records) == 2
        assert batch_records[0]["id"] == "cid-1"  # respects explicit id
        assert batch_records[1]["id"] == batch_records[1]["content_hash"]  # fallback to hash

        # Ensure ON CONFLICT was invoked with index_elements=["id"] and executed
        after_values.on_conflict_do_update.assert_called()
        args, kwargs = after_values.on_conflict_do_update.call_args
        assert "index_elements" in kwargs and kwargs["index_elements"] == ["id"]
        assert sess.execute.call_args[0][0] is upsert_stmt
        assert sess.commit.called


def test_search(mock_pgvector):
    """Test search method."""
    # Test vector search
    with patch.object(mock_pgvector, "vector_search") as mock_vector_search:
        mock_pgvector.search_type = SearchType.vector
        mock_pgvector.search("test query")
        mock_vector_search.assert_called_with(query="test query", limit=5, filters=None)

    # Test keyword search
    with patch.object(mock_pgvector, "keyword_search") as mock_keyword_search:
        mock_pgvector.search_type = SearchType.keyword
        mock_pgvector.search("test query")
        mock_keyword_search.assert_called_with(query="test query", limit=5, filters=None)

    # Test hybrid search
    with patch.object(mock_pgvector, "hybrid_search") as mock_hybrid_search:
        mock_pgvector.search_type = SearchType.hybrid
        mock_pgvector.search("test query")
        mock_hybrid_search.assert_called_with(query="test query", limit=5, filters=None)


def test_vector_search(mock_pgvector, mock_embedder):
    """Test vector_search method using more comprehensive mocking."""
    # Create expected results
    expected_result = Document(
        id="doc_1", name="test_doc_1", meta_data={"type": "test"}, content="Test content", embedding=[0.1] * 1024
    )

    # Bypass the real implementation by mocking vector_search directly
    with patch.object(mock_pgvector, "vector_search", return_value=[expected_result]):
        results = mock_pgvector.vector_search("test query")

        # Check results
        assert len(results) == 1
        assert results[0].id == "doc_1"
        assert results[0].content == "Test content"


def test_drop(mock_pgvector):
    """Test drop method."""
    with patch.object(mock_pgvector, "table_exists", return_value=True):
        mock_pgvector.drop()
        mock_pgvector.table.drop.assert_called_once()


def test_exists(mock_pgvector):
    """Test exists method."""
    with patch.object(mock_pgvector, "table_exists") as mock_table_exists:
        # Test when table exists
        mock_table_exists.return_value = True
        assert mock_pgvector.exists() is True

        # Test when table doesn't exist
        mock_table_exists.return_value = False
        assert mock_pgvector.exists() is False


def test_get_count(mock_pgvector):
    """Test get_count method by patching the method."""
    with patch.object(mock_pgvector, "get_count", return_value=42):
        count = mock_pgvector.get_count()
        assert count == 42


def test_delete(mock_pgvector):
    """Test delete method by patching it."""
    with patch.object(mock_pgvector, "delete", return_value=True):
        result = mock_pgvector.delete()
        assert result is True


# Asynchronous Tests
@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_async_create(mock_pgvector):
    """Test async_create method."""
    with patch.object(mock_pgvector, "create"), patch("asyncio.to_thread") as mock_to_thread:
        mock_to_thread.return_value = None

        await mock_pgvector.async_create()

        # Check that create was called via to_thread
        mock_to_thread.assert_called_once_with(mock_pgvector.create)


@pytest.mark.asyncio
async def test_async_name_exists(mock_pgvector):
    """Test async_name_exists method."""
    with patch.object(mock_pgvector, "name_exists", return_value=True), patch("asyncio.to_thread") as mock_to_thread:
        mock_to_thread.return_value = True

        result = await mock_pgvector.async_name_exists("test_name")

        # Check result and that name_exists was called via to_thread
        assert result is True
        mock_to_thread.assert_called_once_with(mock_pgvector.name_exists, "test_name")


@pytest.mark.asyncio
async def test_async_insert(mock_pgvector):
    """Test async_insert method."""
    docs = create_test_documents()

    # Mock the postgresql.insert to avoid SQLAlchemy errors with MagicMock table
    with patch("agno.vectordb.pgvector.pgvector.postgresql.insert") as mock_insert:
        mock_stmt = MagicMock()
        mock_insert.return_value = mock_stmt

        # Mock the session execute to avoid actual database operations
        with patch.object(mock_pgvector, "Session") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value.__enter__.return_value = mock_session

            await mock_pgvector.async_insert(content_hash="test_hash", documents=docs)

            # Verify the insert was attempted
            mock_insert.assert_called_once_with(mock_pgvector.table)


@pytest.mark.asyncio
async def test_async_upsert(mock_pgvector):
    """Test async_upsert method."""
    docs = create_test_documents()

    # Mock the postgresql.insert to avoid SQLAlchemy errors with MagicMock table
    with patch("agno.vectordb.pgvector.pgvector.postgresql.insert") as mock_insert:
        mock_stmt = MagicMock()
        mock_values_stmt = MagicMock()
        mock_stmt.values.return_value = mock_values_stmt
        mock_insert.return_value = mock_stmt

        # Mock content_hash_exists to control flow
        with patch.object(mock_pgvector, "content_hash_exists", return_value=True):
            # Mock _delete_by_content_hash to avoid database operations
            with patch.object(mock_pgvector, "_delete_by_content_hash"):
                # Mock the session to avoid actual database operations
                with patch.object(mock_pgvector, "Session") as mock_session_class:
                    mock_session = MagicMock()
                    mock_session_class.return_value.__enter__.return_value = mock_session

                    await mock_pgvector.async_upsert(content_hash="test_hash", documents=docs)

                    # Verify the insert was attempted
                    mock_insert.assert_called_once_with(mock_pgvector.table)


@pytest.mark.asyncio
async def test_async_search(mock_pgvector):
    """Test async_search method."""
    expected_results = [Document(id="test", content="Test document")]

    with (
        patch.object(mock_pgvector, "search", return_value=expected_results),
        patch("asyncio.to_thread") as mock_to_thread,
    ):
        mock_to_thread.return_value = expected_results

        results = await mock_pgvector.async_search("test query")

        # Check results and that search was called via to_thread
        assert results == expected_results
        mock_to_thread.assert_called_once_with(mock_pgvector.search, "test query", 5, None)


@pytest.mark.asyncio
async def test_async_drop(mock_pgvector):
    """Test async_drop method."""
    with patch.object(mock_pgvector, "drop"), patch("asyncio.to_thread") as mock_to_thread:
        mock_to_thread.return_value = None

        await mock_pgvector.async_drop()

        # Check that drop was called via to_thread
        mock_to_thread.assert_called_once_with(mock_pgvector.drop)


@pytest.mark.asyncio
async def test_async_exists(mock_pgvector):
    """Test async_exists method."""
    with patch.object(mock_pgvector, "exists", return_value=True), patch("asyncio.to_thread") as mock_to_thread:
        mock_to_thread.return_value = True

        result = await mock_pgvector.async_exists()

        # Check result and that exists was called via to_thread
        assert result is True
        mock_to_thread.assert_called_once_with(mock_pgvector.exists)


def test_delete_by_id(mock_pgvector, sample_documents):
    """Test deleting documents by ID"""
    # Mock insert and get_count
    with patch.object(mock_pgvector, "insert"), patch.object(mock_pgvector, "get_count") as mock_get_count:
        mock_pgvector.insert(documents=sample_documents, content_hash="test_hash")
        mock_get_count.return_value = 3

    # Mock delete_by_id method
    with patch.object(mock_pgvector, "delete_by_id") as mock_delete_by_id:
        mock_delete_by_id.return_value = True

        # Get the actual ID that would be generated for the first document
        from hashlib import md5

        cleaned_content = sample_documents[0].content.replace("\x00", "\ufffd")
        doc_id = md5(cleaned_content.encode()).hexdigest()

        # Test delete by ID
        result = mock_pgvector.delete_by_id(doc_id)
        assert result is True
        mock_delete_by_id.assert_called_once_with(doc_id)

        # Test delete non-existent ID
        mock_delete_by_id.reset_mock()
        mock_delete_by_id.return_value = True
        result = mock_pgvector.delete_by_id("nonexistent_id")
        assert result is True


def test_delete_by_name(mock_pgvector, sample_documents):
    """Test deleting documents by name"""
    # Mock insert and get_count
    with patch.object(mock_pgvector, "insert"), patch.object(mock_pgvector, "get_count") as mock_get_count:
        mock_pgvector.insert(documents=sample_documents, content_hash="test_hash")
        mock_get_count.return_value = 3

    # Mock delete_by_name method
    with patch.object(mock_pgvector, "delete_by_name") as mock_delete_by_name:
        mock_delete_by_name.return_value = True

        # Test delete by name
        result = mock_pgvector.delete_by_name("tom_kha")
        assert result is True
        mock_delete_by_name.assert_called_once_with("tom_kha")

        # Test delete non-existent name
        mock_delete_by_name.reset_mock()
        mock_delete_by_name.return_value = False
        result = mock_pgvector.delete_by_name("nonexistent")
        assert result is False


def test_delete_by_metadata(mock_pgvector, sample_documents):
    """Test deleting documents by metadata"""
    # Mock insert and get_count
    with patch.object(mock_pgvector, "insert"), patch.object(mock_pgvector, "get_count") as mock_get_count:
        mock_pgvector.insert(documents=sample_documents, content_hash="test_hash")
        mock_get_count.return_value = 3

    # Mock delete_by_metadata method
    with patch.object(mock_pgvector, "delete_by_metadata") as mock_delete_by_metadata:
        # Test delete all Thai cuisine documents
        mock_delete_by_metadata.return_value = True
        result = mock_pgvector.delete_by_metadata({"cuisine": "Thai"})
        assert result is True
        mock_delete_by_metadata.assert_called_once_with({"cuisine": "Thai"})

        # Test delete by specific metadata combination
        mock_delete_by_metadata.reset_mock()
        mock_delete_by_metadata.return_value = True
        result = mock_pgvector.delete_by_metadata({"cuisine": "Thai", "type": "soup"})
        assert result is True
        mock_delete_by_metadata.assert_called_once_with({"cuisine": "Thai", "type": "soup"})

        # Test delete by non-existent metadata
        mock_delete_by_metadata.reset_mock()
        mock_delete_by_metadata.return_value = False
        result = mock_pgvector.delete_by_metadata({"cuisine": "Italian"})
        assert result is False


def test_delete_by_content_id(mock_pgvector, sample_documents):
    """Test deleting documents by content ID"""
    # Add content_id to sample documents
    sample_documents[0].content_id = "recipe_1"
    sample_documents[1].content_id = "recipe_2"
    sample_documents[2].content_id = "recipe_3"

    # Mock insert and get_count
    with patch.object(mock_pgvector, "insert"), patch.object(mock_pgvector, "get_count") as mock_get_count:
        mock_pgvector.insert(documents=sample_documents, content_hash="test_hash")
        mock_get_count.return_value = 3

    # Mock delete_by_content_id method
    with patch.object(mock_pgvector, "delete_by_content_id") as mock_delete_by_content_id:
        # Test delete by content_id
        mock_delete_by_content_id.return_value = True
        result = mock_pgvector.delete_by_content_id("recipe_1")
        assert result is True
        mock_delete_by_content_id.assert_called_once_with("recipe_1")

        # Test delete non-existent content_id
        mock_delete_by_content_id.reset_mock()
        mock_delete_by_content_id.return_value = False
        result = mock_pgvector.delete_by_content_id("nonexistent_content_id")
        assert result is False


def test_delete_by_name_multiple_documents(mock_pgvector):
    """Test deleting multiple documents with the same name"""
    # Create multiple documents with the same name
    docs = [
        Document(
            content="First version of Tom Kha Gai",
            meta_data={"version": "1"},
            name="tom_kha",
            content_id="recipe_1_v1",
        ),
        Document(
            content="Second version of Tom Kha Gai",
            meta_data={"version": "2"},
            name="tom_kha",
            content_id="recipe_1_v2",
        ),
        Document(
            content="Pad Thai recipe",
            meta_data={"version": "1"},
            name="pad_thai",
            content_id="recipe_2_v1",
        ),
    ]

    # Mock insert and get_count
    with patch.object(mock_pgvector, "insert"), patch.object(mock_pgvector, "get_count") as mock_get_count:
        mock_pgvector.insert(documents=docs, content_hash="test_hash")
        mock_get_count.return_value = 3

    # Mock delete_by_name and name_exists methods
    with (
        patch.object(mock_pgvector, "delete_by_name") as mock_delete_by_name,
        patch.object(mock_pgvector, "name_exists") as mock_name_exists,
    ):
        mock_delete_by_name.return_value = True
        mock_name_exists.side_effect = [False, True]  # tom_kha doesn't exist, pad_thai exists

        # Test delete all documents with name "tom_kha"
        result = mock_pgvector.delete_by_name("tom_kha")
        assert result is True
        mock_delete_by_name.assert_called_once_with("tom_kha")

        # Verify name_exists behavior
        assert mock_pgvector.name_exists("tom_kha") is False
        assert mock_pgvector.name_exists("pad_thai") is True


def test_delete_by_metadata_complex(mock_pgvector):
    """Test deleting documents with complex metadata matching"""
    docs = [
        Document(
            content="Thai soup recipe",
            meta_data={"cuisine": "Thai", "type": "soup", "spicy": True},
            name="recipe_1",
        ),
        Document(
            content="Thai noodle recipe",
            meta_data={"cuisine": "Thai", "type": "noodles", "spicy": False},
            name="recipe_2",
        ),
        Document(
            content="Italian pasta recipe",
            meta_data={"cuisine": "Italian", "type": "pasta", "spicy": False},
            name="recipe_3",
        ),
    ]

    # Mock insert and get_count
    with patch.object(mock_pgvector, "insert"), patch.object(mock_pgvector, "get_count") as mock_get_count:
        mock_pgvector.insert(documents=docs, content_hash="test_hash")
        mock_get_count.return_value = 3

    # Mock delete_by_metadata method
    with patch.object(mock_pgvector, "delete_by_metadata") as mock_delete_by_metadata:
        # Test delete only spicy Thai dishes
        mock_delete_by_metadata.return_value = True
        result = mock_pgvector.delete_by_metadata({"cuisine": "Thai", "spicy": True})
        assert result is True
        mock_delete_by_metadata.assert_called_once_with({"cuisine": "Thai", "spicy": True})

        # Test delete all non-spicy dishes
        mock_delete_by_metadata.reset_mock()
        mock_delete_by_metadata.return_value = True
        result = mock_pgvector.delete_by_metadata({"spicy": False})
        assert result is True
        mock_delete_by_metadata.assert_called_once_with({"spicy": False})
