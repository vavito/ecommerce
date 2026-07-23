from decimal import Decimal

from .models import Cart, CartItem
from .schemas import CartItemOut, CartOut


class CartMapper:
    @staticmethod
    def _item_to_output(item: CartItem) -> CartItemOut:
        subtotal = item.preco_unitario_atual * item.quantidade

        return CartItemOut(
            id=item.id,
            produto_id=item.produto_id,
            quantidade=item.quantidade,
            preco_unitario_atual=item.preco_unitario_atual,
            subtotal=subtotal,
        )

    @staticmethod
    def to_output(cart: Cart) -> CartOut:
        items = [CartMapper._item_to_output(item) for item in cart.itens]
        estimated_total = sum(
            (item.subtotal for item in items),
            start=Decimal("0.00"),
        )

        return CartOut(
            id=cart.id,
            usuario_id=cart.usuario_id,
            status=cart.status,
            itens=items,
            total_estimado=estimated_total,
            criado_em=cart.criado_em,
            atualizado_em=cart.atualizado_em,
        )
