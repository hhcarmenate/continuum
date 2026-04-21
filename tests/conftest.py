"""Pytest configuration and fixtures for integration tests.

All tests use real PostgreSQL and Redis instances via Docker.
Each test gets a dedicated project_id to avoid conflicts.
"""

from __future__ import annotations

import pytest
import uuid


@pytest.fixture
def test_project_id() -> str:
    """Generates a unique project ID for test isolation."""
    return f"test-project-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def test_agent_id() -> str:
    """Generates a unique agent ID for test isolation."""
    return f"test-agent-{uuid.uuid4().hex[:8]}"
