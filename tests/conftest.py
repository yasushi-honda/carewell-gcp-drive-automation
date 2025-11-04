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
    1. Cleans all emulator data before test (ensures clean state)
    2. Creates a client pointing to the emulator
    3. Yields the client for test use

    The cleanup ensures tests run in isolation without data contamination.
    """
    import requests

    project_id = os.getenv("GCP_PROJECT", "demo-test")

    # Clear emulator data BEFORE test using official REST API
    emulator_host = os.getenv("FIRESTORE_EMULATOR_HOST", "localhost:8080")
    try:
        # Use Firestore Emulator's clear endpoint for carewell-native database
        clear_url = f"http://{emulator_host}/emulator/v1/projects/{project_id}/databases/carewell-native/documents"
        response = requests.delete(clear_url)
        if response.status_code == 200:
            print(f"✓ Firestore emulator cleared for project: {project_id}")
        else:
            print(f"Warning: Failed to clear emulator (status {response.status_code})")
    except Exception as e:
        print(f"Warning: Could not clear Firestore emulator: {e}")

    # Create client using carewell-native database (as per original design)
    db = firestore.Client(project=project_id, database="carewell-native")

    yield db

    # No cleanup needed here - next test will clear before starting


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
