from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Resposta padrao para erros da API."""

    code: str
    message: str
    details: dict[str, object] = Field(default_factory=dict)
