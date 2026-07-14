## Padrao de erros

Os erros da API seguem o formato:

```json
{
  "code": "PRODUCT_NOT_FOUND",
  "message": "Produto nao encontrado.",
  "details": {
    "product_id": "uuid"
  }
}
```