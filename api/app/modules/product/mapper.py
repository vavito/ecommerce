from .models import Product
from .schemas import ProductCreate, ProductOut


class ProductMapper:
    @staticmethod
    def to_entity(schema: ProductCreate) -> Product:
        return Product(
            categoria_id=schema.categoria_id,
            nome=schema.nome,
            descricao=schema.descricao,
            sku=schema.sku,
            preco=schema.preco,
        )

    @staticmethod
    def to_output(product: Product) -> ProductOut:
        return ProductOut.model_validate(product)
