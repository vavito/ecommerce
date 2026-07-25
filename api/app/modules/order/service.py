from decimal import Decimal
from uuid import UUID

from app.modules.cart.enums import CartStatus
from app.modules.cart.models import Cart
from app.modules.cart.repository import CartRepository
from app.modules.payment.enums import PaymentMethod, PaymentStatus
from app.modules.payment.models import Payment
from app.modules.stock.service import StockService
from app.modules.user.models import Address
from app.modules.user.repository import UserRepository
from app.shared.exceptions import BusinessRuleException, NotFoundException

from .enums import OrderStatus
from .models import Order, OrderItem
from .repository import OrderRepository


class OrderService:
    def __init__(
        self,
        repository: OrderRepository,
        cart_repository: CartRepository,
        stock_service: StockService,
        user_repository: UserRepository,
    ) -> None:
        self.repository = repository
        self.cart_repository = cart_repository
        self.stock_service = stock_service
        self.user_repository = user_repository

    @staticmethod
    def _raise_empty_cart() -> None:
        raise BusinessRuleException(
            code="CART_EMPTY",
            message="Carrinho vazio nao pode finalizar checkout.",
        )

    @staticmethod
    def _validate_shipping_amount(shipping_amount: Decimal) -> None:
        if shipping_amount < 0:
            raise BusinessRuleException(
                code="INVALID_SHIPPING_AMOUNT",
                message="Valor do frete nao pode ser negativo.",
            )

    @staticmethod
    def _address_snapshot(address: Address) -> dict[str, object]:
        return {
            "cep": address.cep,
            "rua": address.rua,
            "numero": address.numero,
            "complemento": address.complemento,
            "bairro": address.bairro,
            "cidade": address.cidade,
            "estado": address.estado,
        }

    async def _get_checkout_address(
        self,
        user_id: UUID,
        address_id: UUID,
    ) -> Address:
        address = await self.user_repository.get_address_by_id_and_user_id(
            address_id,
            user_id,
        )

        if address is None:
            raise NotFoundException(
                code="ADDRESS_NOT_FOUND",
                message="Endereco nao encontrado.",
                details={"address_id": str(address_id)},
            )

        return address

    async def _get_open_cart_with_items(self, user_id: UUID) -> Cart:
        cart = await self.cart_repository.get_open_by_user_id_for_update(user_id)

        if cart is None or not cart.itens:
            self._raise_empty_cart()

        return cart

    async def checkout(
        self,
        user_id: UUID,
        address_id: UUID,
        payment_method: PaymentMethod,
        shipping_amount: Decimal = Decimal("0.00"),
    ) -> Order:
        self._validate_shipping_amount(shipping_amount)
        cart = await self._get_open_cart_with_items(user_id)
        address = await self._get_checkout_address(user_id, address_id)
        order_items: list[OrderItem] = []
        products_amount = Decimal("0.00")

        for cart_item in sorted(cart.itens, key=lambda item: str(item.produto_id)):
            product = cart_item.produto
            await self.stock_service.reserve_for_sale(
                product,
                cart_item.quantidade,
            )

            item_total = product.preco * cart_item.quantidade
            products_amount += item_total
            order_items.append(
                OrderItem(
                    produto_id=product.id,
                    nome_produto_snapshot=product.nome,
                    sku_snapshot=product.sku,
                    quantidade=cart_item.quantidade,
                    preco_unitario_snapshot=product.preco,
                    preco_total=item_total,
                )
            )

        total_amount = products_amount + shipping_amount
        order = Order(
            usuario_id=user_id,
            status=OrderStatus.PENDING_PAYMENT,
            valor_produtos=products_amount,
            valor_frete=shipping_amount,
            valor_total=total_amount,
            endereco_snapshot=self._address_snapshot(address),
            itens=order_items,
            pagamento=Payment(
                metodo=payment_method,
                status=PaymentStatus.PENDING,
                valor=total_amount,
                gateway="MOCK",
            ),
        )

        created_order = await self.repository.add(order)
        cart.status = CartStatus.CLOSED
        await self.cart_repository.update(cart)

        return created_order

    async def list_orders(
        self,
        user_id: UUID,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Order], int]:
        return await self.repository.list_by_user_id(
            user_id,
            offset=offset,
            limit=limit,
        )
