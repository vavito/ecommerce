from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.shared.exception_handlers import register_exception_handlers
from app.shared.exceptions import ConflictException, NotFoundException

application = FastAPI()
register_exception_handlers(application)


@application.get("/not-found")
async def not_found_route() -> None:
    raise NotFoundException(
        code="PRODUCT_NOT_FOUND",
        message="Produto nao encontrado.",
        details={"product_id": "test-id"},
    )


@application.post("/conflict")
async def conflict_route() -> None:
    raise ConflictException(
        code="EMAIL_ALREADY_EXISTS",
        message="Email ja cadastrado.",
        details={"email": "teste@example.com"},
    )


@application.get("/validation/{item_id}")
async def validation_route(item_id: int) -> dict[str, int]:
    return {"item_id": item_id}


async def test_not_found_exception_returns_standard_error() -> None:
    transport = ASGITransport(app=application)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get("/not-found")

    assert response.status_code == 404
    assert response.json() == {
        "code": "PRODUCT_NOT_FOUND",
        "message": "Produto nao encontrado.",
        "details": {"product_id": "test-id"},
    }


async def test_conflict_exception_returns_standard_error() -> None:
    transport = ASGITransport(app=application)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.post("/conflict")

    assert response.status_code == 409
    assert response.json() == {
        "code": "EMAIL_ALREADY_EXISTS",
        "message": "Email ja cadastrado.",
        "details": {"email": "teste@example.com"},
    }


async def test_validation_exception_returns_standard_error() -> None:
    transport = ASGITransport(app=application)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get("/validation/not-an-integer")

    body = response.json()

    assert response.status_code == 422
    assert body["code"] == "VALIDATION_ERROR"
    assert body["message"] == "Dados de entrada invalidos."
    assert "errors" in body["details"]
    assert body["details"]["errors"][0]["loc"] == ["path", "item_id"]
