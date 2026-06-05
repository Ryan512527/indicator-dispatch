from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import init_db, engine
from app.api.routes import router as api_router
import asyncio


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    task = asyncio.create_task(start_background_services())
    yield
    task.cancel()
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="指标调度系统 API",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix="/api/v1")
    return app


async def start_background_services():
    from app.watcher.service import FileWatcher
    from app.core.config import settings

    watcher = FileWatcher(settings.watch_dir)
    await watcher.start()


app = create_app()
