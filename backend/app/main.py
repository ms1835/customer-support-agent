from fastapi import FastAPI
from app.api.routes.order_routes import router as order_router

app = FastAPI(title="Support Ticketing System API")

app.include_router(order_router)


@app.get("/health")
def health():
    return {"status": "ok"}