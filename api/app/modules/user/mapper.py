from .models import Address, User
from .schemas import AddressCreate, AddressOut, UserCreate, UserOut


class UserMapper:
    @staticmethod
    def to_entity(schema: UserCreate, senha_hash: str) -> User:
        return User(
            nome=schema.nome,
            email=str(schema.email),
            cpf=schema.cpf,
            senha_hash=senha_hash,
        )

    @staticmethod
    def to_output(user: User) -> UserOut:
        return UserOut.model_validate(user)


class AddressMapper:
    @staticmethod
    def to_entity(schema: AddressCreate) -> Address:
        return Address(**schema.model_dump())

    @staticmethod
    def to_output(address: Address) -> AddressOut:
        return AddressOut.model_validate(address)
