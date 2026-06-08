"""
AI chat service — Phase 2: LLM-powered with tool calling + rule-based fallback.

Flow:
1. If LLM is configured → send user message + tools to LLM
2. LLM decides: call a tool or respond directly
3. If tool called → execute handler → optionally let LLM summarize the result
4. If LLM unavailable or errors → fall back to rule-based matching
"""

import json
import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import IndicatorDefinition, IndicatorEvent
from app.ai.llm import chat_completion, is_llm_available

logger = logging.getLogger(__name__)

# ── System prompt ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """你是指标调度系统的智能助手，帮助用户查询和分析指标数据。

你可以使用以下工具获取数据：
- list_indicators: 查看所有指标列表（名称、编码、分类、单位）
- top_indicators: 查看平均值最高的前10个指标
- system_summary: 查看系统概览（指标总数、分类数、事件数等）
- search_indicators: 按关键词搜索指标

规则：
1. 根据用户问题选择合适的工具获取数据
2. 获取数据后，用简洁清晰的中文总结回答
3. 如果用户问题不需要工具，直接自然地回答
4. 不要编造数据，只使用工具返回的真实数据
5. 如果数据为空，如实告知用户"""

# ── Tool definitions (OpenAI function-calling format) ─────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_indicators",
            "description": "查询系统中所有指标定义列表，包括指标名称、编码、分类和单位",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "top_indicators",
            "description": "查询平均值最高的前10个指标，返回柱状图数据",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "system_summary",
            "description": "获取系统概览信息：指标总数、分类数、事件数据总数、最新更新时间",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_indicators",
            "description": "根据关键词搜索匹配的指标",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词",
                    },
                },
                "required": ["keyword"],
            },
        },
    },
]

# ── Tool execution ────────────────────────────────────────────────────────────

_TOOL_MAP: dict[str, Any] = {}  # populated below after handler definitions


async def _execute_tool(name: str, arguments: dict, db: AsyncSession) -> dict:
    """Execute a tool by name and return structured data."""
    handler = _TOOL_MAP.get(name)
    if handler is None:
        return {"type": "text", "content": f"未知工具: {name}"}

    try:
        if name == "search_indicators":
            return await handler(arguments.get("keyword", ""), db)
        return await handler(db)
    except Exception as e:
        logger.error(f"Tool execution error [{name}]: {e}", exc_info=True)
        return {"type": "text", "content": f"工具执行出错: {e}"}


# ── Main chat handler ─────────────────────────────────────────────────────────

async def ai_chat_handler(
    message: str,
    db: AsyncSession,
    history: list[dict[str, str]] | None = None,
) -> dict:
    """
    Handle AI chat — LLM first, rule-based fallback.

    Returns dict with keys:
      - intent: str  (tool name, "chat", "error", etc.)
      - data: dict   (structured data for frontend rendering)
      - answer: str  (optional, LLM-generated natural language summary)
    """
    if is_llm_available():
        try:
            return await _llm_chat(message, db, history)
        except Exception as e:
            logger.error(f"LLM chat failed, falling back to rules: {e}", exc_info=True)

    return await _rule_based_chat(message, db)


# ── LLM-powered chat ──────────────────────────────────────────────────────────

async def _llm_chat(
    message: str,
    db: AsyncSession,
    history: list[dict[str, str]] | None = None,
) -> dict:
    """Full LLM chat with tool calling support."""

    # 1. Build messages
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": message})

    # 2. First LLM call — let it decide whether to use tools
    response = await chat_completion(messages, tools=TOOLS)
    choice = response["choices"][0]
    assistant_msg = choice["message"]
    finish_reason = choice.get("finish_reason", "")

    # 3. No tool call — direct text response
    if finish_reason != "tool_calls" or not assistant_msg.get("tool_calls"):
        content = assistant_msg.get("content", "")
        return {
            "intent": "chat",
            "data": {"type": "text", "content": content or "（LLM 未返回内容）"},
        }

    # 4. Tool calls — execute each tool
    tool_results: list[dict] = []
    for tc in assistant_msg["tool_calls"]:
        func_name = tc["function"]["name"]
        func_args = json.loads(tc["function"]["arguments"])
        logger.info(f"LLM tool call: {func_name}({func_args})")

        data = await _execute_tool(func_name, func_args, db)
        tool_results.append({
            "tool_call_id": tc["id"],
            "name": func_name,
            "data": data,
        })

    # 5. Build follow-up messages for summarization
    messages.append(assistant_msg)
    for tr in tool_results:
        messages.append({
            "role": "tool",
            "tool_call_id": tr["tool_call_id"],
            "content": json.dumps(tr["data"], ensure_ascii=False, default=str),
        })

    # 6. Second LLM call — let LLM summarize the tool results
    try:
        summary_resp = await chat_completion(messages, tools=None)
        answer = summary_resp["choices"][0]["message"].get("content", "")
    except Exception as e:
        logger.warning(f"LLM summarization failed: {e}")
        answer = ""

    # 7. Return structured data + natural language answer
    if len(tool_results) == 1:
        return {
            "intent": tool_results[0]["name"],
            "data": tool_results[0]["data"],
            "answer": answer,
        }

    # Multiple tool calls — wrap as text
    return {
        "intent": "multi_tool",
        "data": {"type": "text", "content": answer or "查询完成"},
        "answer": answer,
    }


# ── Rule-based fallback (Phase 1) ─────────────────────────────────────────────

async def _rule_based_chat(message: str, db: AsyncSession) -> dict:
    """Original keyword-based intent matching."""
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
            data = await _handle_fallback(message_lower, db)

        return {"intent": intent, "data": data}

    except Exception as e:
        logger.error(f"Rule-based handler error: {e}", exc_info=True)
        return {"intent": "error", "data": {"type": "text", "content": str(e)}}


def _detect_intent(text: str) -> str:
    if any(w in text for w in ["有哪些指标", "list indicator", "show all", "指标列表"]):
        return "list_indicators"
    if any(w in text for w in ["top", "最高", "最大", "最多", "前"]):
        return "top_values"
    if any(w in text for w in ["总结", "overview", "summary", "总览", "概况"]):
        return "summary"
    return "query"


# ── Data handler functions (used by both LLM tools and rule-based fallback) ───

async def _handle_list_indicators(db: AsyncSession) -> dict:
    result = await db.execute(
        select(IndicatorDefinition).order_by(IndicatorDefinition.category)
    )
    indicators = result.scalars().all()
    return {
        "type": "table",
        "columns": ["name", "code", "category", "unit"],
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


async def _handle_search(keyword: str, db: AsyncSession) -> dict:
    """Search indicators by keyword."""
    result = await db.execute(
        select(IndicatorDefinition)
        .where(IndicatorDefinition.name.ilike(f"%{keyword}%"))
        .limit(10)
    )
    indicators = result.scalars().all()
    if indicators:
        return {
            "type": "table",
            "columns": ["name", "code", "category"],
            "rows": [
                {"name": ind.name, "code": ind.code, "category": ind.category}
                for ind in indicators
            ],
        }
    return {
        "type": "text",
        "content": f"未找到与「{keyword}」匹配的指标。",
    }


async def _handle_fallback(text: str, db: AsyncSession) -> dict:
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
            "rows": [
                {"name": ind.name, "code": ind.code, "category": ind.category}
                for ind in indicators
            ],
        }

    return {
        "type": "text",
        "content": (
            f"未找到与「{text}」匹配的指标数据。您可以尝试：\n"
            "1. 查看指标列表\n"
            "2. 查询特定指标的趋势\n"
            "3. 查看系统总览"
        ),
    }


# ── Tool map (must be after handler definitions) ──────────────────────────────

_TOOL_MAP = {
    "list_indicators": _handle_list_indicators,
    "top_indicators": _handle_top_values,
    "system_summary": _handle_summary,
    "search_indicators": _handle_search,
}
