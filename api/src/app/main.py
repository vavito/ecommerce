from fastapi import FastAPI

app = FastAPI(
    title="Ecommerce API",
    version="0.1.0",
    description="API de Ecommerce em FastAPI para portfolio backend.",
)

@app.get("/health")
async def health_check():
    return {"status": "ok"}