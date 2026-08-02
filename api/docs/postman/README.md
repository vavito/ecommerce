# Collection Postman

Esta collection executa o fluxo principal da Ecommerce API e mantém tokens e IDs
no environment local. Os diretórios estão numerados na ordem recomendada para a
demonstração.

## Importação

Importe no Postman os dois arquivos desta pasta:

1. `Ecommerce API.postman_collection.json`
2. `Ecommerce API - Local.postman_environment.json`

Selecione o environment **Ecommerce API - Local** antes de enviar as requisições.
A API deve estar disponível em `http://localhost:8000`.

## Ordem do fluxo

1. Execute `00 - Health`.
2. Em `01 - Cliente`, registre e autentique o cliente.
3. Em `02 - Usuário`, consulte a conta e crie um endereço.
4. Em `03 - Catálogo`, liste os produtos; a collection guarda uma categoria.
5. Em `04 - Administrador`, registre o candidato, promova-o no banco e faça login.
6. Em `05 - Produto e estoque`, crie um produto e seu estoque.
7. Em `06 - Carrinho`, execute as requisições na ordem apresentada.
8. Em `07 - Checkout`, crie o pedido.
9. Preencha `payment_id` conforme a seção de pagamento abaixo.
10. Em `08 - Pagamento`, escolha webhook, aprovação ou recusa.
11. Em `09 - Pedidos`, consulte o pedido atualizado.

Os scripts da collection salvam automaticamente `customer_token`, `admin_token`,
`address_id`, `category_id`, `product_id`, `product_slug`, `cart_item_id` e
`order_id`.

## Preparar o administrador

O cadastro público sempre cria um `CUSTOMER`. Depois de executar **Registrar
candidato a admin**, promova a conta local pelo PostgreSQL:

```powershell
docker exec ecommerce_postgres psql -U ecommerce_user -d ecommerce_db -c "UPDATE users SET role = 'ADMIN' WHERE email = 'admin.portfolio@example.com';"
```

Se as credenciais do seu `.env` forem diferentes, ajuste usuário, banco e e-mail no
comando. Depois execute **Login admin**; o script salvará `admin_token`.

## Obter o payment_id

O endpoint de checkout ainda não devolve os dados do pagamento. Depois do checkout,
copie o valor de `order_id` salvo no environment e consulte:

```powershell
docker exec ecommerce_postgres psql -U ecommerce_user -d ecommerce_db -t -A -c "SELECT id FROM payments WHERE pedido_id = '<ORDER_ID>';"
```

Cole o UUID retornado em `payment_id`. Essa etapa está registrada como limitação no
`API_FUNCIONAMENTO.md`.

## Pagamento e idempotência

O webhook cria automaticamente `idempotency_key` e `gateway_transaction_id` na
primeira execução. Repetir a mesma request demonstra a idempotência: a API devolve
o mesmo pagamento sem aplicar novamente a baixa ou a liberação de estoque.

Para processar outro pagamento, limpe essas duas variáveis no environment. Aprovar,
recusar e processar webhook são alternativas; um mesmo pagamento não pode seguir
por mais de uma delas.

## Dados locais

As senhas do environment são apenas dados de demonstração. Tokens e UUIDs ficam no
environment local depois das requests e não devem ser reutilizados em produção.
