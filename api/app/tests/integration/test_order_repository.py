from decimal import Decimal
from uuid import uuid4

from app.core.database import async_session_maker
from app.modules.order.models import Order, OrderItem
from app.modules.order.repository import OrderRepository
from app.modules.product.models import Category, Product
from app.modules.user.models import User


async def test_order_repository_persists_and_finds_orders() -> None:
    unique_value = uuid4().hex

    async with async_session_maker() as session:
        try:
            user = User(
                nome="Joao",
                email=f"joao-order-{unique_value}@example.com",
                cpf=unique_value[:11],
                senha_hash="hash",
            )
            other_user = User(
                nome="Maria",
                email=f"maria-order-{unique_value}@example.com",
                cpf=unique_value[11:22],
                senha_hash="hash",
            )
            category = Category(
                nome="Informatica",
                slug=f"informatica-order-{unique_value}",
                ativo=True,
            )
            session.add_all([user, other_user, category])
            await session.flush()

            first_product = Product(
                categoria_id=category.id,
                nome="Teclado mecanico",
                slug=f"teclado-order-{unique_value}",
                descricao=None,
                sku=f"TEC-ORDER-{unique_value}",
                preco=Decimal("200.00"),
                ativo=True,
            )
            second_product = Product(
                categoria_id=category.id,
                nome="Mouse sem fio",
                slug=f"mouse-order-{unique_value}",
                descricao=None,
                sku=f"MOU-ORDER-{unique_value}",
                preco=Decimal("100.00"),
                ativo=True,
            )
            session.add_all([first_product, second_product])
            await session.flush()

            repository = OrderRepository(session)
            order = Order(
                usuario_id=user.id,
                valor_produtos=Decimal("400.00"),
                valor_frete=Decimal("20.00"),
                valor_total=Decimal("420.00"),
                endereco_snapshot={
                    "cep": "01001000",
                    "rua": "Praca da Se",
                    "numero": "1",
                    "bairro": "Se",
                    "cidade": "Sao Paulo",
                    "estado": "SP",
                },
                itens=[
                    OrderItem(
                        produto_id=first_product.id,
                        nome_produto_snapshot=first_product.nome,
                        sku_snapshot=first_product.sku,
                        quantidade=1,
                        preco_unitario_snapshot=Decimal("200.00"),
                        preco_total=Decimal("200.00"),
                    ),
                    OrderItem(
                        produto_id=second_product.id,
                        nome_produto_snapshot=second_product.nome,
                        sku_snapshot=second_product.sku,
                        quantidade=2,
                        preco_unitario_snapshot=Decimal("100.00"),
                        preco_total=Decimal("200.00"),
                    ),
                ],
            )
            other_order = Order(
                usuario_id=other_user.id,
                valor_produtos=Decimal("200.00"),
                valor_frete=Decimal("0.00"),
                valor_total=Decimal("200.00"),
                endereco_snapshot={"cidade": "Campinas", "estado": "SP"},
                itens=[
                    OrderItem(
                        produto_id=first_product.id,
                        nome_produto_snapshot=first_product.nome,
                        sku_snapshot=first_product.sku,
                        quantidade=1,
                        preco_unitario_snapshot=Decimal("200.00"),
                        preco_total=Decimal("200.00"),
                    )
                ],
            )

            created_order = await repository.add(order)
            await repository.add(other_order)

            order_id = order.id
            user_id = user.id
            session.expunge_all()

            found_order = await repository.get_by_id(order_id)
            user_orders, total = await repository.list_by_user_id(
                user_id,
                offset=0,
                limit=20,
            )

            assert created_order.id == order_id
            assert found_order is not None
            assert found_order.id == order_id
            assert len(found_order.itens) == 2
            assert {item.nome_produto_snapshot for item in found_order.itens} == {
                "Teclado mecanico",
                "Mouse sem fio",
            }
            assert [listed_order.id for listed_order in user_orders] == [order_id]
            assert len(user_orders[0].itens) == 2
            assert total == 1
        finally:
            await session.rollback()


async def test_order_repository_returns_empty_results_when_orders_do_not_exist() -> (
    None
):
    async with async_session_maker() as session:
        repository = OrderRepository(session)

        assert await repository.get_by_id(uuid4()) is None
        orders, total = await repository.list_by_user_id(uuid4())

        assert orders == []
        assert total == 0
