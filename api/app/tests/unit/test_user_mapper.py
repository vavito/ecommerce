from datetime import UTC, datetime
from uuid import uuid4

from app.modules.user.mapper import AddressMapper, UserMapper
from app.modules.user.models import Address, User
from app.modules.user.schemas import AddressCreate, UserCreate
from app.shared.enums import UserRole


def test_user_mapper_converts_create_schema_to_entity() -> None:
    schema = UserCreate(
        nome="Joao",
        email="joao@example.com",
        cpf="12345678901",
        senha="senha123",
    )

    user = UserMapper.to_entity(schema, senha_hash="hash-seguro")

    assert user.nome == schema.nome
    assert user.email == str(schema.email)
    assert user.cpf == schema.cpf
    assert user.senha_hash == "hash-seguro"
    assert not hasattr(user, "senha")


def test_user_mapper_converts_entity_to_output_without_sensitive_data() -> None:
    now = datetime.now(UTC)
    user = User(
        id=uuid4(),
        nome="Joao",
        email="joao@example.com",
        cpf="12345678901",
        senha_hash="hash-seguro",
        role=UserRole.CUSTOMER,
        ativo=True,
        criado_em=now,
        atualizado_em=now,
    )

    output = UserMapper.to_output(user)
    output_data = output.model_dump()

    assert output.id == user.id
    assert output.nome == user.nome
    assert output.email == user.email
    assert output.role == UserRole.CUSTOMER
    assert "cpf" not in output_data
    assert "senha_hash" not in output_data


def test_address_mapper_converts_create_schema_to_entity() -> None:
    schema = AddressCreate(
        cep="12345678",
        rua="Rua das Flores",
        numero="10",
        complemento=None,
        bairro="Centro",
        cidade="Sao Paulo",
        estado="sp",
        principal=False,
    )

    address = AddressMapper.to_entity(schema)

    assert address.cep == schema.cep
    assert address.rua == schema.rua
    assert address.numero == schema.numero
    assert address.estado == schema.estado
    assert address.principal is False
    assert address.usuario_id is None


def test_address_mapper_converts_entity_to_output() -> None:
    now = datetime.now(UTC)
    address = Address(
        id=uuid4(),
        usuario_id=uuid4(),
        cep="12345678",
        rua="Rua das Flores",
        numero="10",
        complemento=None,
        bairro="Centro",
        cidade="Sao Paulo",
        estado="SP",
        principal=True,
        criado_em=now,
        atualizado_em=now,
    )

    output = AddressMapper.to_output(address)

    assert output.id == address.id
    assert output.usuario_id == address.usuario_id
    assert output.cep == address.cep
    assert output.estado == "SP"
    assert output.principal is True
