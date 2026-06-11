import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db
from app.routers import health, live, modes, serial, sessions, stream
from app.services.serial_service import serial_service

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    serial_service.bind_event_loop(asyncio.get_running_loop())
    yield
    serial_service.disconnect()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Backend API for the pump data acquisition system.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(live.router, prefix=settings.api_prefix)
app.include_router(modes.router, prefix=settings.api_prefix)
app.include_router(serial.router, prefix=settings.api_prefix)
app.include_router(sessions.router, prefix=settings.api_prefix)
app.include_router(stream.router)


@app.get("/")
def root():
    return {
        "name": settings.app_name,
        "docs": "/docs",
        "health": f"{settings.api_prefix}/health",
        "live_websocket": "/ws/live",
    }
