from fastapi import FastAPI
from app.api.routes.conversation_routes import router as conversation_router
from app.api.routes.order_routes import router as order_router
from app.api.routes.user_routes import router as user_router

app = FastAPI(title="Support Ticketing System API")

app.include_router(order_router)
app.include_router(conversation_router)
app.include_router(user_router)


@app.get("/health")
def health():
    return {"status": "ok"}