"""
飞书电子表格（Sheet）对接服务
使用 tenant_access_token（应用身份，无需用户授权）

环境变量（均可留空使用默认值）:
  FEISHU_APP_ID      默认 cli_aaa28b0b95f89bda
  FEISHU_APP_SECRET  默认 R4Ny6VuhD04LnmcZNcQ9IfRke8CAd776
  FEISHU_FOLDER_TOKEN 默认 F14Vf8gQNl5kC4dkzxwcbZD0nPb
"""
import os
import time
import requests
from typing import Optional, List, Dict, Any


# ── 配置（优先读环境变量，缺省用用户提供的默认值）──────────────────────
APP_ID      = os.getenv("FEISHU_APP_ID",      "cli_aaa28b0b95f89bda")
APP_SECRET  = os.getenv("FEISHU_APP_SECRET",  "R4Ny6VuhD04LnmcZNcQ9IfRke8CAd776")
FOLDER_TOKEN = os.getenv("FEISHU_FOLDER_TOKEN", "F14Vf8gQNl5kC4dkzxwcbZD0nPb")

# ── Token 缓存 ────────────────────────────────────────────────────────────
_cache = {"token": None, "expire_at": 0}


def get_tenant_access_token() -> str:
    """获取 tenant_access_token，自动缓存（有效期 2h）"""
    global _cache
    now = time.time()
    if _cache["token"] and _cache["expire_at"] > now + 60:
        return _cache["token"]

    resp = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/",
        json={"app_id": APP_ID, "app_secret": APP_SECRET},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"获取飞书 token 失败: {data.get('msg')}")

    _cache["token"] = data["tenant_access_token"]
    _cache["expire_at"] = now + data.get("expire", 7200) - 60
    return _cache["token"]


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {get_tenant_access_token()}",
        "Content-Type": "application/json; charset=utf-8",
    }


# ── 工具函数 ──────────────────────────────────────────────────────────────

def _mask_account(acc: Any) -> str:
    """
    宽带账号脱敏：只显示前3位和后4位，中间用 XXXX 代替
    例：13474220470 → 134XXXX0470
    账号长度不足7位时：前1位 + XXXX + 后1位
    """
    if not acc:
        return ""
    s = str(acc).strip()
    n = len(s)
    if n <= 7:
        # 短账号：前1位 + XXXX + 后1位
        if n <= 2:
            return s
        return s[0] + "XXXX" + s[-1]
    return s[:3] + "XXXX" + s[-4:]


def _col_letter(n: int) -> str:
    """1→A, 2→B, … 27→AA, 28→AB, …"""
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s or "A"


# ── 飞书 API 封装 ─────────────────────────────────────────────────────────

def create_spreadsheet(title: str, folder_token: Optional[str] = None) -> Dict[str, Any]:
    """
    创建飞书电子表格
    返回: {"spreadsheet_token": ..., "url": ..., "sheet_id": ...}
    """
    body: Dict[str, Any] = {"title": title}
    if folder_token:
        body["folder_token"] = folder_token

    resp = requests.post(
        "https://open.feishu.cn/open-apis/sheets/v3/spreadsheets",
        headers=_headers(),
        json=body,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"创建飞书表格失败: {data.get('msg')}")

    sp = data["data"]["spreadsheet"]
    sheet_id = _get_first_sheet_id(sp["spreadsheet_token"])
    return {
        "spreadsheet_token": sp["spreadsheet_token"],
        "url": sp["url"],
        "sheet_id": sheet_id,
    }


def _get_first_sheet_id(spreadsheet_token: str) -> str:
    """查询电子表格下第一个 sheet 的 ID"""
    resp = requests.get(
        f"https://open.feishu.cn/open-apis/sheets/v3/spreadsheets/{spreadsheet_token}/sheets/query",
        headers=_headers(),
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"查询 sheet 列表失败: {data.get('msg')}")
    sheets = data["data"].get("sheets", [])
    if not sheets:
        raise RuntimeError("表格中没有找到 sheet")
    return sheets[0]["sheet_id"]


def write_values(
    spreadsheet_token: str,
    sheet_id: str,
    values: List[List[str]],
) -> None:
    """
    用 v2 ValueRange API 覆盖写入数据
    values[0] = 表头, values[1:] = 数据行
    """
    if not values:
        return
    end_col  = _col_letter(len(values[0]))
    end_row  = len(values)
    range_ref = f"{sheet_id}!A1:{end_col}{end_row}"

    body = {"valueRange": {"range": range_ref, "values": values}}

    resp = requests.put(
        f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values",
        headers=_headers(),
        json=body,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"写入飞书表格失败: {data.get('msg')}")


def append_values(
    spreadsheet_token: str,
    sheet_id: str,
    rows: List[List[str]],
    col_count: int,
) -> None:
    """
    追加行（不含表头）
    rows: 数据行列表，每行是一个 list[str]
    """
    if not rows:
        return
    end_col = _col_letter(col_count)
    range_ref = f"{sheet_id}!A1:{end_col}"   # append 只需列范围，行号自动追加

    body = {"valueRange": {"range": range_ref, "values": rows}}

    resp = requests.post(
        f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values_append",
        headers=_headers(),
        json=body,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"追加写入飞书表格失败: {data.get('msg')}")


def set_header_style(spreadsheet_token: str, sheet_id: str, col_count: int) -> None:
    """设置首行表头样式：蓝色背景 + 白色粗体 + 居中"""
    end_col = _col_letter(col_count)
    range_ref = f"{sheet_id}!A1:{end_col}1"

    body = {
        "appendStyle": {
            "range": range_ref,
            "style": {
                "backColor": "#4472C4",
                "font": {
                    "bold": True,
                    "color": "#FFFFFF",
                    "size": 11,
                },
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE",
            },
        }
    }

    resp = requests.put(
        f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/style",
        headers=_headers(),
        json=body,
        timeout=15,
    )
    # 样式设置失败不抛异常（非致命）
    print(f"[debug] set_header_style resp.status_code={resp.status_code}, resp.text={resp.text[:300]}", flush=True)
    try:
        data = resp.json()
        if data.get("code") != 0:
            print(f"[warn] 设置表头样式失败: {data.get('msg')}", flush=True)
        else:
            print(f"[info] 表头样式设置成功", flush=True)
    except Exception as e:
        print(f"[warn] 设置表头样式失败（响应解析错误）: {e}, resp.text={resp.text[:300]}", flush=True)


def set_spreadsheet_public_edit(spreadsheet_token: str) -> None:
    """
    设置电子表格为「互联网上获得链接的任何人可编辑」
    通过 Drive API v1 更新文档权限设置
    """
    url = f"https://open.feishu.cn/open-apis/drive/v1/permissions/{spreadsheet_token}/public?type=sheet"

    body = {
        "link_share_entity": "anyone_editable",   # 互联网上获得链接的任何人可编辑
        "share_entity": "anyone",
        "comment_entity": "anyone_can_edit",
    }

    resp = requests.patch(url, headers=_headers(), json=body, timeout=15)
    try:
        data = resp.json()
        if data.get("code") != 0:
            print(f"[warn] 设置表格公开编辑权限失败: {data.get('msg')} (code={data.get('code')})")
        else:
            print(f"[info] 已设置表格为「互联网上获得链接的任何人可编辑」")
    except Exception as e:
        print(f"[warn] 设置表格权限失败（响应解析错误）: {e}, resp.text={resp.text[:300]}")


# ── 业务入口 ────────────────────────────────────────────────────────────────

def export_daily_report_to_feishu(
    records: List[Dict[str, Any]],
    folder_token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    将日报-装机积压清单完整导出到飞书电子表格
    返回: {"url": ..., "rows_written": ...}
    """
    if not records:
        return {"url": "", "rows_written": 0, "spreadsheet_token": ""}

    # 1. 字段顺序（去掉 id）
    field_names = [k for k in records[0].keys() if k != "id"]

    # 2. 创建表格（不指定 folder_token，创建到应用自己工作空间，避免权限问题）
    ts = time.strftime("%Y%m%d_%H%M%S")
    result = create_spreadsheet(
        title=f"日报-装机积压清单_{ts}",
        folder_token=None,
    )
    spreadsheet_token = result["spreadsheet_token"]
    sheet_id = result["sheet_id"]
    url = result["url"]

    # 3. 构造 values（表头 + 数据行），账号字段脱敏
    # 字段名可能是中文"宽带账号"或英文"account"
    values: List[List[str]] = [field_names]
    for rec in records:
        row = []
        for f in field_names:
            v = rec.get(f, "")
            # 账号字段脱敏：支持中文"宽带账号"和英文"account"
            if (f == "account" or "账号" in f) and v:
                row.append(_mask_account(v))
            else:
                row.append(str(v) if v is not None else "")
        values.append(row)

    # 4. 写入（单次最多 5000 行，超出则分批）
    MAX_WRITE = 5000
    if len(values) <= MAX_WRITE:
        write_values(spreadsheet_token, sheet_id, values)
    else:
        # 第一批（含表头）
        write_values(spreadsheet_token, sheet_id, values[:MAX_WRITE])
        # 后续批次（不含表头，用 append）
        for i in range(MAX_WRITE, len(values), MAX_WRITE):
            chunk = values[i:i + MAX_WRITE]
            append_values(spreadsheet_token, sheet_id, chunk, len(field_names))

    # 5. 设置表格为「获得链接的任何人可编辑」
    set_spreadsheet_public_edit(spreadsheet_token)

    # 6. 设置表头样式
    set_header_style(spreadsheet_token, sheet_id, len(field_names))

    return {
        "url": url,
        "rows_written": len(values) - 1,
        "spreadsheet_token": spreadsheet_token,
    }
