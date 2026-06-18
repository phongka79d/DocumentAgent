import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def app_factory():
    def _factory():
        from app.main import create_app

        return create_app()

    return _factory


@pytest.fixture()
def client(app_factory):
    with TestClient(app_factory()) as test_client:
        yield test_client
