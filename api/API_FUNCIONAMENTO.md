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

## Dados iniciais

Com o PostgreSQL em execucao e as migrations aplicadas, carregue as categorias e
os produtos de demonstracao a partir da pasta `api`:

```powershell
task seed
```

Se o executavel do Taskipy estiver bloqueado pelo Windows, execute diretamente:

```powershell
python -m app.scripts.seed
```

O comando pode ser executado novamente sem duplicar categorias ou produtos. As
categorias sao identificadas pelo `slug` e os produtos pelo `sku`.
