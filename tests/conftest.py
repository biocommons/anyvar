import pytest
import connexion

from variationsandbox.app import app


@pytest.fixture(scope="session")
def client():
    with app.app.test_client() as c:
        yield c
