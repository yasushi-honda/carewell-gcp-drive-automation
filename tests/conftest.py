"""
Pytest configuration and shared fixtures.
"""

import os

import pytest
from google.cloud import firestore


@pytest.fixture
def firestore_client():
    """
    Create a Firestore client for testing.

    Uses Firestore Emulator if FIRESTORE_EMULATOR_HOST is set,
    otherwise uses the real Firestore (for local manual testing only).
    """
    project_id = os.getenv("GCP_PROJECT", "demo-test")
    db = firestore.Client(project=project_id, database="carewell-native")
    return db


@pytest.fixture
def emulator_client():
    """
    Create a Firestore client for integration testing with emulator.

    This fixture:
    1. Creates a client pointing to the emulator
    2. Yields the client for test use
    3. Cleans up all test data after each test

    The cleanup ensures tests run in isolation without data contamination.
    """
    project_id = os.getenv("GCP_PROJECT", "demo-test")
    db = firestore.Client(project=project_id, database="carewell-native")

    yield db

    # Cleanup: Delete all documents created during the test
    # We clean the submissions collection which is used in integration tests
    try:
        submissions_ref = db.collection("submissions")
        delete_collection(submissions_ref, batch_size=100)
    except Exception as e:
        print(f"Warning: Failed to cleanup Firestore data: {e}")


def delete_collection(coll_ref, batch_size):
    """
    Delete all documents in a collection recursively.

    Args:
        coll_ref: Collection reference to delete
        batch_size: Number of documents to delete per batch
    """
    docs = coll_ref.limit(batch_size).stream()
    deleted = 0

    for doc in docs:
        # Delete subcollections recursively
        for subcoll in doc.reference.collections():
            delete_collection(subcoll, batch_size)

        # Delete the document
        doc.reference.delete()
        deleted += 1

    if deleted >= batch_size:
        # Recursively delete remaining documents
        return delete_collection(coll_ref, batch_size)


@pytest.fixture
def sample_class_name():
    """Sample class name for testing."""
    return "テストクラス"


@pytest.fixture
def sample_task_id():
    """Sample task ID for testing."""
    return "課題①"


@pytest.fixture
def sample_task_pattern():
    """Sample task pattern for testing."""
    return "課題①業務分析　※～11/3〆切"


@pytest.fixture
def sample_file_data():
    """Sample file data for testing."""
    return {
        "student_id": "N9902913",
        "student_name": "テスト太郎",
        "filename": "test_document.pdf",
        "drive_file_id": "test_file_id_123",
        "drive_folder_id": "test_folder_id_456",
        "submit_date": "2025-10-12 10:00:00",
        "metadata": {"size": 1024},
    }
