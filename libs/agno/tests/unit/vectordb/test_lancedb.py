import os
import shutil
from typing import List

import pytest

from agno.knowledge.document import Document
from agno.vectordb.lancedb import LanceDb
from agno.vectordb.search import SearchType

TEST_TABLE = "test_table"
TEST_PATH = "tmp/test_lancedb"


@pytest.fixture
def lance_db(mock_embedder):
    """Fixture to create and clean up a LanceDb instance"""
    os.makedirs(TEST_PATH, exist_ok=True)
    if os.path.exists(TEST_PATH):
        shutil.rmtree(TEST_PATH)
        os.makedirs(TEST_PATH)

    db = LanceDb(uri=TEST_PATH, table_name=TEST_TABLE, embedder=mock_embedder)
    db.create()
    yield db

    try:
        db.drop()
    except Exception:
        pass

    if os.path.exists(TEST_PATH):
        shutil.rmtree(TEST_PATH)


@pytest.fixture
def sample_documents() -> List[Document]:
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


def test_create_table(lance_db):
    """Test creating a table"""
    assert lance_db.exists() is True
    assert lance_db.get_count() == 0


def test_insert_documents(lance_db, sample_documents):
    """Test inserting documents"""
    lance_db.insert(documents=sample_documents, content_hash="test_hash")
    assert lance_db.get_count() == 3


def test_vector_search(lance_db, sample_documents):
    """Test vector search"""
    lance_db.insert(documents=sample_documents, content_hash="test_hash")
    results = lance_db.vector_search("coconut dishes", limit=2)
    assert len(results) == 2
    # results is a DataFrame, so check the 'payload' column for content
    # Each payload is a JSON string, so parse it and check for 'coconut'
    import json

    found = False
    for _, row in results.iterrows():
        payload = json.loads(row["payload"])
        if "coconut" in payload["content"].lower():
            found = True
            break
    assert found


def test_keyword_search(lance_db, sample_documents):
    """Test keyword search"""
    lance_db.search_type = SearchType.keyword
    lance_db.insert(documents=sample_documents, content_hash="test_hash")
    results = lance_db.search("spicy curry", limit=1)
    assert len(results) == 1
    assert "curry" in results[0].content.lower()


def test_hybrid_search(lance_db, sample_documents):
    """Test hybrid search"""
    lance_db.search_type = SearchType.hybrid
    lance_db.insert(documents=sample_documents, content_hash="test_hash")
    results = lance_db.search("Thai soup", limit=2)
    assert len(results) == 2
    assert any("thai" in doc.content.lower() for doc in results)


def test_upsert_documents(lance_db, sample_documents):
    """Test upserting documents"""
    lance_db.insert(documents=[sample_documents[0]], content_hash="test_hash")
    assert lance_db.get_count() == 1

    modified_doc = Document(
        content="Tom Kha Gai is a spicy and sour Thai coconut soup",
        meta_data={"cuisine": "Thai", "type": "soup"},
        name="tom_kha",
    )
    lance_db.upsert(documents=[modified_doc], content_hash="test_hash")
    results = lance_db.search("spicy and sour", limit=1)
    assert len(results) == 1
    assert results[0].content is not None


def test_name_exists(lance_db, sample_documents):
    """Test name existence check"""
    lance_db.insert(documents=[sample_documents[0]], content_hash="test_hash")
    assert lance_db.name_exists("tom_kha") is True
    assert lance_db.name_exists("nonexistent") is False


def test_id_exists(lance_db, sample_documents):
    """Test ID existence check"""
    lance_db.insert(documents=[sample_documents[0]], content_hash="test_hash")

    # Get the actual ID that was generated (MD5 hash of content)
    from hashlib import md5

    cleaned_content = sample_documents[0].content.replace("\x00", "\ufffd")
    expected_id = md5(cleaned_content.encode()).hexdigest()

    assert lance_db.id_exists(expected_id) is True
    assert lance_db.id_exists("nonexistent_id") is False


def test_delete_by_id(lance_db, sample_documents):
    """Test deleting documents by ID"""
    lance_db.insert(documents=sample_documents, content_hash="test_hash")
    assert lance_db.get_count() == 3

    # Get the actual ID that was generated for the first document
    from hashlib import md5

    cleaned_content = sample_documents[0].content.replace("\x00", "\ufffd")
    doc_id = md5(cleaned_content.encode()).hexdigest()

    # Delete by ID
    result = lance_db.delete_by_id(doc_id)
    assert result is True
    assert lance_db.get_count() == 2
    assert lance_db.id_exists(doc_id) is False

    # Try to delete non-existent ID
    result = lance_db.delete_by_id("nonexistent_id")
    assert result is True  # LanceDB delete doesn't fail for non-existent IDs
    assert lance_db.get_count() == 2


def test_delete_by_name(lance_db, sample_documents):
    """Test deleting documents by name"""
    lance_db.insert(documents=sample_documents, content_hash="test_hash")
    assert lance_db.get_count() == 3

    # Delete by name
    result = lance_db.delete_by_name("tom_kha")
    assert result is True
    assert lance_db.get_count() == 2
    assert lance_db.name_exists("tom_kha") is False

    # Try to delete non-existent name
    result = lance_db.delete_by_name("nonexistent")
    assert result is False
    assert lance_db.get_count() == 2


def test_delete_by_metadata(lance_db, sample_documents):
    """Test deleting documents by metadata"""
    lance_db.insert(documents=sample_documents, content_hash="test_hash")
    assert lance_db.get_count() == 3

    # Delete by metadata - should delete all Thai cuisine documents
    result = lance_db.delete_by_metadata({"cuisine": "Thai"})
    assert result is True
    assert lance_db.get_count() == 0

    # Insert again and test partial metadata match
    lance_db.insert(documents=sample_documents, content_hash="test_hash")
    assert lance_db.get_count() == 3

    # Delete by specific metadata combination
    result = lance_db.delete_by_metadata({"cuisine": "Thai", "type": "soup"})
    assert result is True
    assert lance_db.get_count() == 2  # Should only delete tom_kha

    # Try to delete by non-existent metadata
    result = lance_db.delete_by_metadata({"cuisine": "Italian"})
    assert result is False
    assert lance_db.get_count() == 2


def test_delete_by_content_id(lance_db, sample_documents):
    """Test deleting documents by content ID"""
    # Add content_id to sample documents
    sample_documents[0].content_id = "recipe_1"
    sample_documents[1].content_id = "recipe_2"
    sample_documents[2].content_id = "recipe_3"

    lance_db.insert(documents=sample_documents, content_hash="test_hash")
    assert lance_db.get_count() == 3

    # Delete by content_id
    result = lance_db.delete_by_content_id("recipe_1")
    assert result is True
    assert lance_db.get_count() == 2

    # Try to delete non-existent content_id
    result = lance_db.delete_by_content_id("nonexistent_content_id")
    assert result is False
    assert lance_db.get_count() == 2


def test_delete_by_name_multiple_documents(lance_db):
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

    lance_db.insert(documents=docs, content_hash="test_hash")
    assert lance_db.get_count() == 3

    # Delete all documents with name "tom_kha"
    result = lance_db.delete_by_name("tom_kha")
    assert result is True
    assert lance_db.get_count() == 1
    assert lance_db.name_exists("tom_kha") is False
    assert lance_db.name_exists("pad_thai") is True


def test_delete_by_metadata_complex(lance_db):
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

    lance_db.insert(documents=docs, content_hash="test_hash")
    assert lance_db.get_count() == 3

    # Delete only spicy Thai dishes
    result = lance_db.delete_by_metadata({"cuisine": "Thai", "spicy": True})
    assert result is True
    assert lance_db.get_count() == 2

    # Delete all non-spicy dishes
    result = lance_db.delete_by_metadata({"spicy": False})
    assert result is True
    assert lance_db.get_count() == 0


def test_get_count(lance_db, sample_documents):
    """Test document count"""
    assert lance_db.get_count() == 0
    lance_db.insert(documents=sample_documents, content_hash="test_hash")
    assert lance_db.get_count() == 3


def test_error_handling(lance_db):
    """Test error handling scenarios"""
    results = lance_db.search("")
    assert len(results) == 0
    lance_db.insert(documents=[], content_hash="test_hash")
    assert lance_db.get_count() == 0


def test_bad_vectors_handling(mock_embedder):
    """Test handling of bad vectors"""
    db = LanceDb(
        uri=TEST_PATH, table_name="test_bad_vectors", on_bad_vectors="fill", fill_value=0.0, embedder=mock_embedder
    )
    db.create()
    try:
        doc = Document(content="Test document", meta_data={}, name="test")
        db.insert(documents=[doc], content_hash="test_hash")
        assert db.get_count() == 1
    finally:
        db.drop()
        if os.path.exists(TEST_PATH):
            shutil.rmtree(TEST_PATH)
