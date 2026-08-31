import os
import pytest
from app.db.session import init_db

@pytest.fixture(scope="session", autouse=True)
def initialize_test_database():
    """Ensure database schema and tables exist across all test suites."""
    os.environ.setdefault("USE_POSTGRES", "false")
    init_db()
