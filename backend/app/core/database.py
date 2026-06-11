from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from .config import settings

engine = create_async_engine(settings.database_url, echo=False, pool_size=20, max_overflow=10)
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
        # ── 迁移1: enterprise_broadband_backlog 表添加 cover_scene 列 ──
        result = await conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'enterprise_broadband_backlog'
            )
        """))
        table_exists = result.scalar()
        if table_exists:
            result = await conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'enterprise_broadband_backlog' 
                AND column_name = 'cover_scene'
            """))
            if result.first() is None:
                await conn.execute(text("""
                    ALTER TABLE enterprise_broadband_backlog 
                    ADD COLUMN IF NOT EXISTS cover_scene VARCHAR(50)
                """))
                print("Migration: Added cover_scene column to enterprise_broadband_backlog")

        # ── 迁移2: notifications 表添加 is_read 列 ──
        result = await conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'notifications'
            )
        """))
        if result.scalar():
            result = await conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'notifications' 
                AND column_name = 'is_read'
            """))
            if result.first() is None:
                await conn.execute(text("""
                    ALTER TABLE notifications 
                    ADD COLUMN IF NOT EXISTS is_read BOOLEAN DEFAULT FALSE
                """))
                print("Migration: Added is_read column to notifications")

        # ── 迁移3: five_category_withdrawal_detail 表添加 is_recovered 列 ──
        result = await conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'five_category_withdrawal_detail'
            )
        """))
        if result.scalar():
            result = await conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'five_category_withdrawal_detail'
                AND column_name = 'is_recovered'
            """))
            if result.first() is None:
                await conn.execute(text("""
                    ALTER TABLE five_category_withdrawal_detail
                    ADD COLUMN IF NOT EXISTS is_recovered VARCHAR(20)
                """))
                print("Migration: Added is_recovered column to five_category_withdrawal_detail")


async def init_db():
    from . import models  # noqa: F401
    # 先创建不存在的表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # 再运行迁移（表已存在时才执行ALTER）
    await migrate_db()
