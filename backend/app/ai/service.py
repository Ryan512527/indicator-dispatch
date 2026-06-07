import logging
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from app.core.models import IndicatorDefinition, IndicatorEvent
from app.core.config import settings

logger = logging.getLogger(__name__)


async def ai_chat_handler(message: str, db: AsyncSession) -> dict:
    # Phase 1: rule-based intent matching (no LLM dependency)
    # Phase 2 will integrate LangChain for full NL understanding
    message_lower = message.lower()

    try:
        intent = _detect_intent(message_lower)
        if intent == "list_indicators":
            data = await _handle_list_indicators(db)
        elif intent == "top_values":
            data = await _handle_top_values(db)
        elif intent == "summary":
            data = await _handle_summary(db)
        else:
            # Fallback: return data that might match the query
            data = await _handle_fallback(message_lower, db)

        return {"intent": intent, "data": data}

    except Exception as e:
        logger.error(f"AI handler error: {e}", exc_info=True)
        return {"intent": "error", "data": str(e)}


def _detect_intent(text: str) -> str:
    if any(w in text for w in ["有哪些指标", "list indicator", "show all", "指标列表"]):
        return "list_indicators"
    if any(w in text for w in ["top", "最高", "最大", "最多", "前"]):
        return "top_values"
    if any(w in text for w in ["总结", "overview", "summary", "总览", "概况"]):
        return "summary"
    return "query"


async def _handle_list_indicators(db: AsyncSession) -> dict:
    result = await db.execute(select(IndicatorDefinition).order_by(IndicatorDefinition.category))
    indicators = result.scalars().all()
    return {
        "type": "table",
        "columns": ["name", "code", "category", "unit", "events_count"],
        "rows": [
            {
                "name": ind.name,
                "code": ind.code,
                "category": ind.category,
                "unit": ind.unit,
            }
            for ind in indicators
        ],
    }


async def _handle_top_values(db: AsyncSession) -> dict:
    subq = (
        select(
            IndicatorEvent.indicator_id,
            func.avg(IndicatorEvent.value).label("avg_value"),
        )
        .group_by(IndicatorEvent.indicator_id)
        .order_by(func.avg(IndicatorEvent.value).desc())
        .limit(10)
    ).subquery()

    stmt = (
        select(IndicatorDefinition.name, subq.c.avg_value)
        .join(subq, IndicatorDefinition.id == subq.c.indicator_id)
    )
    result = await db.execute(stmt)
    rows = result.all()
    return {
        "type": "bar",
        "title": "Top Indicators by Average Value",
        "categories": [r[0] for r in rows],
        "values": [round(float(r[1]), 2) for r in rows],
    }


async def _handle_summary(db: AsyncSession) -> dict:
    result = await db.execute(
        select(
            func.count(IndicatorDefinition.id),
            func.count(func.distinct(IndicatorDefinition.category)),
        )
    )
    total_indicators, total_categories = result.one()

    result = await db.execute(
        select(func.count(IndicatorEvent.id), func.max(IndicatorEvent.time))
    )
    total_events, latest_time = result.one()

    return {
        "type": "text",
        "content": (
            f"当前系统共有 **{total_indicators}** 个指标，"
            f"分布在 **{total_categories}** 个分类中。"
            f"已采集 **{total_events}** 条事件数据，"
            f"最新数据更新于 {latest_time.isoformat() if latest_time else '无'}。"
        ),
    }


async def _handle_fallback(text: str, db: AsyncSession) -> dict:
    # Try to match indicator names
    result = await db.execute(
        select(IndicatorDefinition)
        .where(IndicatorDefinition.name.ilike(f"%{text}%"))
        .limit(5)
    )
    indicators = result.scalars().all()
    if indicators:
        return {
            "type": "table",
            "columns": ["name", "code", "category"],
            "rows": [{"name": ind.name, "code": ind.code, "category": ind.category} for ind in indicators],
        }

    return {
        "type": "text",
        "content": f"未找到与" + text + "匹配的指标数据。您可以尝试：\\n1. 查看指标列表\\n2. 查询特定指标的趋势\\n3. 查看系统总览",
    }
