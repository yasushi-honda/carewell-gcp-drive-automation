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
