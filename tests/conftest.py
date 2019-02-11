import pytest
import connexion

from variationsandbox.app import create_app


@pytest.fixture(scope="module")
def client():
    app = create_app()
    with app.app.test_client() as c:
        yield c
