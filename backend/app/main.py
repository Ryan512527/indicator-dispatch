from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import init_db, engine
from app.api.routes import router as api_router
import asyncio
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    task = asyncio.create_task(start_background_services())
    logger.info("后台服务启动任务已创建")
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

    logger.info(f"正在启动文件监听服务，监听目录: {settings.watch_dir}")
    watcher = FileWatcher(settings.watch_dir)

    # ── 启动定时reparse（不阻塞，后台运行）──
    asyncio.create_task(periodic_reparse())
    logger.info("定时reparse任务已启动（每小时）")

    # ── 启动文件监听（阻塞，直到shutdown）──
    await watcher.start()


async def periodic_reparse():
    """每小时对受NOW()影响的报表执行reparse，确保数据实时更新"""
    import httpx

    # 等待30秒让服务完全启动
    await asyncio.sleep(30)

    while True:
        await asyncio.sleep(3600)  # 1小时
        logger.info("开始定时reparse（NOW()依赖报表）...")

        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            for api_name in ["complaint-10086", "complaint-2200000", "offline-dispatch"]:
                try:
                    resp = await client.post(f"http://localhost:8000/api/v1/reports/{api_name}/reparse")
                    if resp.status_code == 200:
                        logger.info(f"定时reparse成功 [{api_name}]: {resp.json()}")
                    else:
                        logger.warning(f"定时reparse返回非200 [{api_name}]: {resp.status_code} {resp.text[:200]}")
                except Exception as e:
                    logger.error(f"定时reparse失败 [{api_name}]: {e}", exc_info=True)


app = create_app()
