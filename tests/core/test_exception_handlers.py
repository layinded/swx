import pytest
from unittest.mock import MagicMock, AsyncMock

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.testclient import TestClient

from swx_core.exceptions.handlers import (
    register_exception_handlers,
    swx_error_handler,
    generic_error_handler,
)
from swx_core.utils.errors import SwXError


class _TestError(SwXError):
    def __init__(self, code="TEST_001", message="test error", status_code=400):
        super().__init__(message=message, code=code, status_code=status_code)


class TestSwXErrorHandler:
    @pytest.mark.asyncio
    async def test_swx_error_returns_json(self):
        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/test-error")
        async def raise_error():
            raise _TestError(code="ERR_001", message="something broke", status_code=409)

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test-error")
        assert response.status_code == 409
        data = response.json()
        error = data.get("error", data)
        assert error["code"] == "ERR_001"
        assert "something broke" in error.get("message", "")


class TestGenericErrorHandler:
    @pytest.mark.asyncio
    async def test_generic_error_production_no_leak(self):
        app = FastAPI()
        app.state.environment = "production"
        register_exception_handlers(app)

        @app.get("/boom")
        async def boom():
            raise RuntimeError("secret internal detail")

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/boom")
        assert response.status_code == 500
        data = response.json()
        assert "secret internal detail" not in data.get("detail", "")
        assert data["error"] == "Internal Server Error"

    @pytest.mark.asyncio
    async def test_generic_error_non_production_shows_detail(self):
        app = FastAPI()
        app.state.environment = "local"
        register_exception_handlers(app)

        @app.get("/boom")
        async def boom():
            raise RuntimeError("visible detail")

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/boom")
        assert response.status_code == 500
        data = response.json()
        assert data["detail"] == "visible-detail" or "visible" in str(data)


class TestHTTPErrorHandler:
    def test_http_exception_returns_json(self):
        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/not-found")
        async def not_found():
            raise StarletteHTTPException(status_code=404, detail="Not here")

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/not-found")
        assert response.status_code == 404
        assert response.json()["error"] == "Not here"


class TestValidationErrorHandler:
    def test_validation_error_returns_422(self):
        app = FastAPI()
        register_exception_handlers(app)

        from pydantic import BaseModel

        class Item(BaseModel):
            name: str
            price: int

        @app.post("/items")
        async def create_item(item: Item):
            return item

        client = TestClient(app)
        response = client.post("/items", json={"name": 123, "price": "bad"})
        assert response.status_code == 422


class TestRegisterExceptionHandlers:
    def test_registers_four_handlers(self):
        app = FastAPI()
        register_exception_handlers(app)
        # FastAPI stores exception handlers internally
        assert SwXError in app.exception_handlers
        assert RequestValidationError in app.exception_handlers
        assert StarletteHTTPException in app.exception_handlers
        assert Exception in app.exception_handlers