from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routes.health import router as health_router
from app.routes.memory import router as memory_router
from app.routes.mock import router as mock_router
from app.routes.reviews import router as reviews_router
from app.routes.sops import router as sops_router
from app.routes.tickets import router as tickets_router


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Customer support SOP workflow agent API.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(memory_router)
app.include_router(mock_router)
app.include_router(reviews_router)
app.include_router(sops_router)
app.include_router(tickets_router)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "status": "ok",
        "docs": "/docs",
    }
