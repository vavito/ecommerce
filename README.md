# Ecommerce API

![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.116%2B-009688?style=flat-square&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![Tests](https://img.shields.io/badge/tests-210%20passing-brightgreen?style=flat-square)

API REST de e-commerce desenvolvida com FastAPI e PostgreSQL para demonstrar uma
arquitetura backend modular. O projeto cobre cadastro e autenticação de usuários,
catálogo, estoque concorrente, carrinho, checkout, pedidos e pagamentos simulados.

## Tecnologias

- Python 3.12+
- FastAPI e Pydantic v2
- SQLAlchemy 2.0 assíncrono e asyncpg
- PostgreSQL e Alembic
- JWT, pwdlib e Argon2
- pytest, pytest-asyncio e HTTPX
- Ruff, Taskipy e Docker Compose

## Funcionalidades

- Cadastro e login com JWT e senhas protegidas por Argon2
- Autorização por perfil `CUSTOMER` e `ADMIN`
- Catálogo público com busca, filtros, paginação e slug
- Administração de produtos e estoque
- Carrinho persistente e isolado por usuário
- Checkout com snapshot de itens e endereço
- Reserva de estoque com locks para operações concorrentes
- Pagamento mock com aprovação, recusa e webhook idempotente
- Erros padronizados e documentação OpenAPI automática
- Testes unitários e de integração organizados por módulo

## Arquitetura

```text
api/app/
├── core/          # Configuração, banco e segurança
├── migrations/    # Migrações Alembic
├── modules/
│   ├── auth/
│   ├── cart/
│   ├── order/
│   ├── payment/
│   ├── product/
│   │   ├── mapper.py       # Conversão entre entidades e DTOs
│   │   ├── models.py       # Category e Product
│   │   ├── repository.py   # Consultas e persistência
│   │   ├── router.py       # Endpoints públicos e administrativos
│   │   ├── schemas.py      # DTOs de entrada e saída
│   │   └── service.py      # Regras de negócio
│   ├── stock/
│   └── user/
├── scripts/       # Dados iniciais para demonstração
├── shared/        # Modelos base, exceções e utilitários
└── tests/         # Testes unitários e de integração
```

Cada módulo separa modelos SQLAlchemy, schemas Pydantic, repositórios, services,
mappers e rotas. As regras de negócio ficam nos services e o acesso ao banco nos
repositórios.

## Como executar

Pré-requisitos: Python 3.12+, Docker e Docker Compose.

```powershell
git clone https://github.com/vavito/ecommerce.git
cd ecommerce
Copy-Item .env.example .env
```

Atualize as credenciais do `.env` e use uma `JWT_SECRET_KEY` segura com pelo menos
32 caracteres.

### Com Docker

O Compose constrói a API, aguarda o PostgreSQL ficar saudável, aplica as migrations
e inicia o Uvicorn:

```powershell
docker compose up --build -d
docker compose exec api python -m app.scripts.seed
```

### API local e banco no Docker

Para executar o servidor diretamente no ambiente Python:

```powershell
docker compose up -d db
cd api
python -m pip install -e ".[dev]"
alembic upgrade head
task seed
uvicorn app.main:app --reload
```

A API estará disponível em `http://localhost:8000`:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Health check: `http://localhost:8000/health`

Use `docker compose down` para encerrar os containers sem apagar o volume do banco.

## Endpoints principais

### Autenticação

| Método | Rota | Descrição | Acesso |
|---|---|---|---|
| `POST` | `/auth/register` | Cadastrar usuário | Público |
| `POST` | `/auth/login` | Obter access token | Público |

### Usuários

| Método | Rota | Descrição | Acesso |
|---|---|---|---|
| `GET` | `/users/me` | Consultar usuário atual | Autenticado |
| `POST` | `/users/me/addresses` | Cadastrar endereço | Autenticado |

### Produtos

| Método | Rota | Descrição | Acesso |
|---|---|---|---|
| `GET` | `/products` | Listar produtos ativos | Público |
| `GET` | `/products/{product_id}` | Consultar produto por UUID | Público |
| `GET` | `/products/by-slug/{slug}` | Consultar produto por slug | Público |
| `POST` | `/admin/products` | Cadastrar produto | `ADMIN` |
| `PATCH` | `/admin/products/{product_id}` | Atualizar produto | `ADMIN` |

### Estoque

| Método | Rota | Descrição | Acesso |
|---|---|---|---|
| `POST` | `/admin/products/{product_id}/stock` | Criar estoque | `ADMIN` |
| `GET` | `/admin/products/{product_id}/stock` | Consultar estoque | `ADMIN` |
| `PATCH` | `/admin/products/{product_id}/stock` | Ajustar estoque | `ADMIN` |

### Carrinho

| Método | Rota | Descrição | Acesso |
|---|---|---|---|
| `GET` | `/cart` | Consultar carrinho aberto | Autenticado |
| `POST` | `/cart/items` | Adicionar item | Autenticado |
| `PATCH` | `/cart/items/{item_id}` | Alterar quantidade | Autenticado |
| `DELETE` | `/cart/items/{item_id}` | Remover item | Autenticado |

### Pedidos

| Método | Rota | Descrição | Acesso |
|---|---|---|---|
| `POST` | `/orders/checkout` | Finalizar checkout | Autenticado |
| `GET` | `/orders` | Listar pedidos do usuário | Autenticado |
| `GET` | `/orders/{order_id}` | Consultar pedido | Autenticado |

### Pagamentos

| Método | Rota | Descrição | Acesso |
|---|---|---|---|
| `POST` | `/payments/webhook/mock` | Simular retorno do gateway | Mock |
| `POST` | `/payments/{payment_id}/approve` | Aprovar pagamento | `ADMIN` |
| `POST` | `/payments/{payment_id}/refuse` | Recusar pagamento | `ADMIN` |

A relação completa de rotas e as decisões técnicas estão em
[`api/API_FUNCIONAMENTO.md`](api/API_FUNCIONAMENTO.md).

Para executar o fluxo manual completo, importe a
[`collection do Postman`](api/docs/postman/README.md).

## Qualidade

```powershell
cd api
task lint
task test
```

A suíte atual possui 210 testes: 113 unitários e 97 de integração.

## Próximos passos

- [x] Criar Dockerfile da API e finalizar o ambiente completo no Docker Compose
- [ ] Integrar um gateway de pagamento real com assinatura de webhooks
- [ ] Adicionar refresh token, recuperação de senha e revogação de acesso
- [ ] Configurar CORS e integrar um frontend ao fluxo de compra
- [ ] Criar pipeline de CI/CD, deploy e observabilidade da aplicação
- [ ] Expirar automaticamente reservas de pedidos que não forem pagos

## Autor

Desenvolvido por [João Victor](https://github.com/vavito).
