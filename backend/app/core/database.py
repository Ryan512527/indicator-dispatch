from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from .config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session


async def migrate_db():
    """
    数据库迁移：添加新列到已存在的表。
    在 init_db 之前调用。
    """
    async with engine.begin() as conn:
        # 检查 enterprise_broadband_backlog 表是否有 cover_scene 列
        result = await conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'enterprise_broadband_backlog' 
            AND column_name = 'cover_scene'
        """))
        if result.first() is None:
            # 列不存在，添加它
            await conn.execute(text("""
                ALTER TABLE enterprise_broadband_backlog 
                ADD COLUMN IF NOT EXISTS cover_scene VARCHAR(50)
            """))
            print("Migration: Added cover_scene column to enterprise_broadband_backlog")


async def init_db():
    from . import models  # noqa: F401
    # 先运行迁移
    await migrate_db()
    # 再创建不存在的表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
