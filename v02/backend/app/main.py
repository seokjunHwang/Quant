from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.router import api_router
from app.db.dynamodb import init_dynamodb, close_dynamodb
from app.core.websocket_manager import manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    # DynamoDB is optional — skip if not configured
    try:
        app.state.dynamodb = await init_dynamodb(settings)
    except Exception:
        app.state.dynamodb = None
    app.state.ws_manager = manager
    yield
    if app.state.dynamodb:
        await close_dynamodb(app.state.dynamodb)


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.api_prefix)

    return app


app = create_app()
