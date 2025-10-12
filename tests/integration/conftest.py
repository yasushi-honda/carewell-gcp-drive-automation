"""
Integration test configuration and fixtures.
"""

import os
import pytest
import time
from google.cloud import firestore


@pytest.fixture(scope="session")
def emulator_client():
    """
    Create a Firestore client connected to the emulator.

    This fixture is session-scoped to avoid recreating the client
    for each test.
    """
    # Ensure we're using the emulator
    emulator_host = os.getenv("FIRESTORE_EMULATOR_HOST", "localhost:8080")
    os.environ["FIRESTORE_EMULATOR_HOST"] = emulator_host

    project_id = os.getenv("GCP_PROJECT", "demo-test")
    db = firestore.Client(project=project_id, database="carewell-native")

    yield db


@pytest.fixture(autouse=True)
def cleanup_firestore(emulator_client):
    """
    Clean up Firestore data after each test.

    This ensures test isolation.
    """
    yield

    # Clean up all collections after test
    collections = emulator_client.collections()
    for collection in collections:
        delete_collection(collection, batch_size=10)


def delete_collection(collection_ref, batch_size):
    """
    Delete all documents in a collection.

    Args:
        collection_ref: Firestore collection reference
        batch_size: Number of documents to delete in each batch
    """
    docs = collection_ref.limit(batch_size).stream()
    deleted = 0

    for doc in docs:
        # Delete subcollections recursively
        subcollections = doc.reference.collections()
        for subcollection in subcollections:
            delete_collection(subcollection, batch_size)

        doc.reference.delete()
        deleted += 1

    if deleted >= batch_size:
        # Continue deletion if there are more documents
        return delete_collection(collection_ref, batch_size)
