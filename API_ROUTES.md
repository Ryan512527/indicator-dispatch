# 前后端接口与路由映射清单

> 生成时间：2026-06-05  
> 本文件汇总了指标调度系统（后端 FastAPI + 前端 React）全部 REST API 接口与前端页面路由的对应关系，方便后续修改与优化。

---

## 一、后端 REST API 接口清单

### 1.1 通用接口

| 方法 | 路径 | 说明 | 前端调用位置 |
|------|------|------|-------------|
| GET | `/api/v1/health` | 服务健康检查 | `api.health()` |

### 1.2 指标管理接口（原有）

| 方法 | 路径 | 说明 | 前端调用位置 |
|------|------|------|-------------|
| GET | `/api/v1/indicators` | 查询指标定义列表（支持 category / search 过滤） | `api.listIndicators()` |
| GET | `/api/v1/indicators/categories` | 获取所有指标分类 | `api.listCategories()` |

### 1.3 指标事件接口（原有）

| 方法 | 路径 | 说明 | 前端调用位置 |
|------|------|------|-------------|
| GET | `/api/v1/events` | 查询指标事件（支持 indicator_id / category / time / dimensions 过滤） | `api.queryEvents()` |
| GET | `/api/v1/events/aggregate` | 聚合统计（支持 time_window / indicator_id / dimension 分组） | `api.aggregateEvents()` |

### 1.4 AI 对话接口（原有）

| 方法 | 路径 | 说明 | 前端调用位置 |
|------|------|------|-------------|
| POST | `/api/v1/ai/chat` | AI 对话处理 | `api.aiChat()` |

### 1.5 文件源接口（原有）

| 方法 | 路径 | 说明 | 前端调用位置 |
|------|------|------|-------------|
| GET | `/api/v1/sources` | 列出监听目录中的文件（支持 pattern 过滤） | 暂无前端调用 |

### 1.6 报表解析接口（本次新增）

| 方法 | 路径 | 说明 | 前端调用位置 | 请求参数 |
|------|------|------|-------------|---------|
| POST | `/api/v1/reports/scan` | 扫描目录，识别出现≥3次的报表类型并注册 | `api.scanReports()` | `directory?: string` |
| POST | `/api/v1/reports/parse-all` | 解析所有已注册的报表类型 | `api.parseAllReports()` | `directory?: string` |
| POST | `/api/v1/reports/parse` | 解析指定报表类型的所有文件 | `api.parseReport()` | `report_type: string`（Query） |
| GET | `/api/v1/reports/types` | 获取所有报表类型及**最新文件数据预览** | `api.listReportTypes()` | 无 |
| GET | `/api/v1/reports/types/{type_id}/records` | 分页获取某报表类型的记录 | `api.getReportRecords()` | `page`, `page_size` |

> **GET /reports/types 返回字段说明**：
> - `latest_filename` — 最新解析的文件名
> - `latest_preview` — 最新文件的前 5 条记录（数组），用于卡片数据预览
> - `file_count` / `record_count` — 文件总数和记录总数（辅助信息）

---

## 二、前端页面路由映射

> 当前项目使用 React 状态路由（非 React Router），通过 `page.name` 切换页面。

| 前端页面标识 | 组件文件 | 说明 | 进入方式 |
|-------------|---------|------|---------|
| `dashboard` | `pages/Dashboard.tsx` | 横山网络指标通报看板（首页） | 默认进入 |
| `detail` | `pages/OutageDetail.tsx` | 退服/故障详情页 | 从 Dashboard 点击基站卡片 |
| `ai-chat` | `pages/AIChat.tsx` | AI 对话模块 | 左侧菜单导航 |
| `report-detail` | `pages/ReportDetail.tsx` | 报表详情页（分页展示记录） | 从 Dashboard 点击报表卡片 |

---

## 三、核心数据流

```
┌─────────────────────────────────────────────────────────────────────┐
│                        数据流向示意图                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   [监听目录]                                                          │
│   /Users/ryan/.../filerecv/2026-06                                  │
│        │                                                            │
│        ▼                                                            │
│   POST /reports/scan        ──►  扫描文件，注册 ReportType           │
│        │                                                            │
│        ▼                                                            │
│   POST /reports/parse-all   ──►  解析全部报表，入库 ReportRecord     │
│        │                                                            │
│        ▼                                                            │
│   GET  /reports/types       ◄──  前端拉取报表类型列表及统计          │
│        │                                                            │
│        ▼                                                            │
│   Dashboard (卡片看板)      ──►  展示各报表类型卡片                  │
│        │                                                            │
│        ▼                                                            │
│   GET /reports/types/{id}/records ◄── 点击卡片，分页加载记录         │
│        │                                                            │
│        ▼                                                            │
│   ReportDetail (详情页)     ──►  展示该报表全部记录                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 四、数据库表结构（本次新增）

| 表名 | 说明 | 核心字段 |
|------|------|---------|
| `report_types` | 报表类型定义 | `name`, `category`, `column_hint` |
| `report_files` | 已解析文件记录（幂等控制） | `report_type_id`, `filename`, `file_path`, `parse_status`, `record_count` |
| `report_records` | 报表数据行（JSON 存储） | `report_file_id`, `data` |

---

## 五、快速验证步骤

### 5.1 启动后端服务
```bash
cd /Users/ryan/Documents/New project/backend
docker-compose up --build -d
```

### 5.2 验证数据库表已创建
```bash
# 进入数据库容器
docker exec -it <db_container> psql -U postgres -d indicator_db -c "\dt"
# 应看到 report_types, report_files, report_records
```

### 5.3 执行扫描（识别报表类型）
```bash
curl -X POST http://localhost:8000/api/v1/reports/scan
```

### 5.4 执行解析（数据入库）
```bash
curl -X POST http://localhost:8000/api/v1/reports/parse-all
```

### 5.5 验证数据
```bash
curl http://localhost:8000/api/v1/reports/types
```

### 5.6 启动前端
```bash
cd /Users/ryan/Documents/New project/frontend
npm run dev
# 访问 http://localhost:5173
```

---

## 六、文件清单

### 6.1 后端新增/修改文件

| 文件路径 | 说明 |
|---------|------|
| `backend/app/core/models.py` | 新增 ReportType / ReportFile / ReportRecord 模型 |
| `backend/app/services/report_scanner.py` | 新增报表扫描与解析服务 |
| `backend/app/api/routes.py` | 追加 5 个报表相关 API 路由 |

### 6.2 前端新增/修改文件

| 文件路径 | 说明 |
|---------|------|
| `frontend/src/types.ts` | 新增报表相关 TypeScript 类型 |
| `frontend/src/services/api.ts` | 新增报表 API 调用函数 |
| `frontend/src/pages/ReportDetail.tsx` | 新增报表详情页组件 |
| `frontend/src/pages/Dashboard.tsx` | 新增报表卡片看板区域 |
| `frontend/src/App.tsx` | 新增 `report-detail` 路由支持 |
| `frontend/src/components/Layout.tsx` | 微调 onNavigate 类型签名 |

---

> 后续如需扩展（如 WxPusher 推送、定时自动扫描、图表可视化），可在此清单基础上追加接口与路由。
