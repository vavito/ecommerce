from pydantic_settings import BaseSettings, SettingsConfigDict


class _Settings(BaseSettings):
    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str
    jwt_access_token_expire_minutes: int

    model_config = SettingsConfigDict(
        env_file="../.env",
        # ignora os campos do .env que nao foram declarados aqui => (Evita erro)
        extra="ignore",
    )


settings = _Settings()