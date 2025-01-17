"""
For pytest
initialise a text database and profile
"""

import pytest

pytest_plugins = ["aiida.manage.tests.pytest_fixtures"]


@pytest.fixture(scope="function", autouse=True)
def clear_database_auto(clear_database_before_test):
    """Automatically clear database in between tests."""
