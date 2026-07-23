from decimal import Decimal

from sqlalchemy import CheckConstraint, Index, UniqueConstraint

from app.modules.cart.enums import CartStatus
from app.modules.cart.models import Cart, CartItem
from app.modules.product.models import Product
from app.modules.user.models import User


def test_cart_belongs_to_user_and_supports_planned_statuses() -> None:
    user = User(
        nome="Joao",
        email="joao@example.com",
        cpf="12345678901",
        senha_hash="hash",
    )
    cart = Cart(
        usuario=user,
        status=CartStatus.OPEN,
    )
    open_cart_index = next(
        index
        for index in Cart.__table__.indexes
        if index.name == "uq_carts_usuario_open"
    )

    assert cart.usuario is user
    assert cart.status is CartStatus.OPEN
    assert set(CartStatus) == {
        CartStatus.OPEN,
        CartStatus.CLOSED,
        CartStatus.ABANDONED,
    }
    assert isinstance(open_cart_index, Index)
    assert open_cart_index.unique is True


def test_cart_item_belongs_to_cart_and_product_with_domain_constraints() -> None:
    cart = Cart(status=CartStatus.OPEN)
    product = Product(
        nome="Teclado mecanico",
        slug="teclado-mecanico",
        descricao=None,
        sku="TEC-MEC-001",
        preco=Decimal("299.90"),
    )
    item = CartItem(
        carrinho=cart,
        produto=product,
        quantidade=2,
        preco_unitario_atual=product.preco,
    )
    check_constraint_names = {
        constraint.name
        for constraint in CartItem.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    unique_constraint_names = {
        constraint.name
        for constraint in CartItem.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert item.carrinho is cart
    assert item.produto is product
    assert item in cart.itens
    assert item.quantidade == 2
    assert item.preco_unitario_atual == Decimal("299.90")
    assert "ck_cart_items_quantidade_positive" in check_constraint_names
    assert "ck_cart_items_preco_unitario_atual_positive" in check_constraint_names
    assert "uq_cart_items_carrinho_produto" in unique_constraint_names
