from fastapi import FastAPI

from .modules.auth.router import router as auth_router
from .modules.product.router import router as product_router
from .modules.user.router import router as user_router
from .shared.exception_handlers import register_exception_handlers

app = FastAPI(
    title="Ecommerce API",
    version="0.1.0",
    description="API de Ecommerce em FastAPI para portfolio backend.",
)

app.include_router(auth_router)
app.include_router(product_router)
app.include_router(user_router)
register_exception_handlers(app)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
