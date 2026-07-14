from fastapi import FastAPI

from .shared.exception_handlers import register_exception_handlers

app = FastAPI(
    title="Ecommerce API",
    version="0.1.0",
    description="API de Ecommerce em FastAPI para portfolio backend.",
)

register_exception_handlers(app)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
