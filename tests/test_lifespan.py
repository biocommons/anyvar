from fastapi import FastAPI
from fastapi.testclient import TestClient

from anyvar.restapi.main import app_lifespan
from anyvar.storage import Storage


def test_lifespan(mocker):
    """Test the app_lifespan method in anyvar.restapi.main"""
    create_storage_mock = mocker.patch("anyvar.anyvar.create_storage")
    storage_mock = mocker.Mock(spec=Storage)
    create_storage_mock.return_value = storage_mock
    create_translator_mock = mocker.patch("anyvar.anyvar.create_translator")
    create_translator_mock.return_value = {}
    app = FastAPI(
        title="AnyVarTest",
        docs_url="/",
        openapi_url="/openapi.json",
        description="Test app",
        lifespan=app_lifespan,
    )
    with TestClient(app):
        create_storage_mock.assert_called_once()
        create_translator_mock.assert_called_once()
        assert app.state.anyvar is not None

    storage_mock.close.assert_called_once()
