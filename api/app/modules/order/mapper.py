from .models import Order, OrderItem
from .schemas import AddressSnapshotOut, OrderItemOut, OrderOut


class OrderMapper:
    @staticmethod
    def item_to_output(item: OrderItem) -> OrderItemOut:
        return OrderItemOut(
            id=item.id,
            produto_id=item.produto_id,
            nome_produto_snapshot=item.nome_produto_snapshot,
            sku_snapshot=item.sku_snapshot,
            quantidade=item.quantidade,
            preco_unitario_snapshot=item.preco_unitario_snapshot,
            preco_total=item.preco_total,
        )

    @staticmethod
    def to_output(order: Order) -> OrderOut:
        return OrderOut(
            id=order.id,
            usuario_id=order.usuario_id,
            status=order.status,
            valor_produtos=order.valor_produtos,
            valor_frete=order.valor_frete,
            valor_total=order.valor_total,
            endereco_snapshot=AddressSnapshotOut.model_validate(
                order.endereco_snapshot
            ),
            itens=[OrderMapper.item_to_output(item) for item in order.itens],
            criado_em=order.criado_em,
            atualizado_em=order.atualizado_em,
        )
