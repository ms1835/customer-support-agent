from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes.agent_routes import router as agent_router
from app.api.routes.conversation_routes import router as conversation_router
from app.api.routes.escalation_routes import router as escalation_router
from app.api.routes.order_routes import router as order_router
from app.api.routes.product_routes import router as product_router
from app.api.routes.support_agent_routes import router as support_agent_router
from app.api.routes.ticket_routes import router as ticket_router
from app.api.routes.user_routes import router as user_router

app = FastAPI(title="Support Ticketing System API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agent_router)
app.include_router(order_router)
app.include_router(conversation_router)
app.include_router(escalation_router)
app.include_router(ticket_router)
app.include_router(support_agent_router)
app.include_router(user_router)
app.include_router(product_router)


@app.get("/health")
def health():
    return {"status": "ok"}