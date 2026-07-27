from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

_RESOURCE_ID = uuid4()
_ADMIN_ROUTE_CASES = [
    (
        "POST",
        "/admin/products",
        {
            "categoria_id": str(_RESOURCE_ID),
            "nome": "Produto administrativo",
            "descricao": None,
            "sku": f"AUTH-{_RESOURCE_ID.hex}",
            "preco": "99.90",
        },
        "CATEGORY_NOT_FOUND",
    ),
    (
        "PATCH",
        f"/admin/products/{_RESOURCE_ID}",
        {"preco": "89.90"},
        "PRODUCT_NOT_FOUND",
    ),
    (
        "POST",
        f"/admin/products/{_RESOURCE_ID}/stock",
        {"quantidade": 10},
        "PRODUCT_NOT_FOUND",
    ),
    (
        "PATCH",
        f"/admin/products/{_RESOURCE_ID}/stock",
        {"operacao": "ENTRADA", "quantidade": 5},
        "STOCK_NOT_FOUND",
    ),
    (
        "GET",
        f"/admin/products/{_RESOURCE_ID}/stock",
        None,
        "STOCK_NOT_FOUND",
    ),
    (
        "POST",
        f"/payments/{_RESOURCE_ID}/approve",
        None,
        "PAYMENT_NOT_FOUND",
    ),
    (
        "POST",
        f"/payments/{_RESOURCE_ID}/refuse",
        None,
        "PAYMENT_NOT_FOUND",
    ),
]
_ADMIN_ROUTE_IDS = [
    "create-product",
    "update-product",
    "create-stock",
    "adjust-stock",
    "get-stock",
    "approve-payment",
    "refuse-payment",
]


@pytest.mark.parametrize(
    ("method", "path", "payload", "_admin_error_code"),
    _ADMIN_ROUTE_CASES,
    ids=_ADMIN_ROUTE_IDS,
)
async def test_customer_cannot_access_admin_routes(
    method: str,
    path: str,
    payload: dict[str, object] | None,
    _admin_error_code: str,
    customer_headers: dict[str, str],
) -> None:
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.request(
            method,
            path,
            json=payload,
            headers=customer_headers,
        )

    assert response.status_code == 403
    assert response.json() == {
        "code": "FORBIDDEN",
        "message": "Acesso permitido apenas para administradores.",
        "details": {},
    }


@pytest.mark.parametrize(
    ("method", "path", "payload", "expected_error_code"),
    _ADMIN_ROUTE_CASES,
    ids=_ADMIN_ROUTE_IDS,
)
async def test_admin_reaches_protected_route_business_logic(
    method: str,
    path: str,
    payload: dict[str, object] | None,
    expected_error_code: str,
    admin_headers: dict[str, str],
) -> None:
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.request(
            method,
            path,
            json=payload,
            headers=admin_headers,
        )

    assert response.status_code == 404
    assert response.json()["code"] == expected_error_code


@pytest.mark.parametrize(
    ("path", "expected_status"),
    [
        ("/products", 200),
        (f"/products/{_RESOURCE_ID}", 404),
        ("/products/by-slug/produto-inexistente-auth", 404),
    ],
    ids=["list-products", "get-product", "get-product-by-slug"],
)
async def test_public_product_routes_do_not_require_token(
    path: str,
    expected_status: int,
) -> None:
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(path)

    assert response.status_code == expected_status
    assert response.status_code not in {401, 403}
