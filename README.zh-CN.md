# Support SOP Agent

[English](./README.en.md) | [中文](./README.zh-CN.md)

一个基于 LangGraph + RAG + Tool Calling 的客服工单 SOP 执行 Agent。

## 项目定位

客服 Agent 不应该只停留在聊天。真实客服工作通常需要查询订单、检查物流、检索 SOP、控制风险、进入人工审核，并保存可审计的执行轨迹。

本项目目标是提供一个实用的客服业务 Agent 模板，展示如何把 Agent 落到真实业务流程中。

## 计划功能

- 工单意图识别
- 基于 RAG 的 SOP 检索
- 订单、物流、用户 Mock 工具
- 工单 CRUD API
- 基于 LangGraph 的状态化工作流
- 高风险工单人工审核
- Agent 执行轨迹时间线
- 基于 YAML 的回归评估

## MVP 场景

- 已发货退款
- 物流异常
- 发票重开

## 计划技术栈

- Backend: FastAPI
- Frontend: React 或 Next.js
- Agent workflow: LangGraph
- Vector store: Chroma
- Database: 先用 SQLite，后续替换 PostgreSQL
- Evaluation: YAML cases + Python runner

## 本地开发

### 后端

```bash
cd apps/api
py -3.12 -m pip install -r requirements.txt
py -3.12 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

健康检查：

```text
http://localhost:8000/health
```

API 文档：

```text
http://localhost:8000/docs
```

工单 API：

```text
POST  /api/tickets
GET   /api/tickets
GET   /api/tickets/{ticket_id}
PATCH /api/tickets/{ticket_id}
POST  /api/tickets/{ticket_id}/run
GET   /api/tickets/{ticket_id}/trace
GET   /api/tickets/{ticket_id}/traces
```

SOP API：

```text
GET  /api/sops
POST /api/sops/reindex
POST /api/sops/search
```

人工审核 API：

```text
GET  /api/reviews/pending
POST /api/reviews/{ticket_id}
GET  /api/reviews/{ticket_id}
```

Mock 业务 API：

```text
GET  /mock/orders/{order_id}
GET  /mock/logistics/{order_id}
GET  /mock/users/{user_id}
GET  /mock/users/{user_id}/tickets
POST /mock/escalations
```

样例数据：

```text
OD2026001: 已发货退款场景
OD2026003: 高金额退款场景
OD2026004: 物流未更新场景
OD2026005: 发票重开场景
```

### 前端

```bash
cd apps/web
npm install
npm run dev
```

前端地址：

```text
http://localhost:3000
```

### Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

## 项目结构

```text
support-sop-agent/
  apps/
    api/
    web/
  knowledge_base/
  evals/
    cases/
  examples/
    tickets/
  .github/
    ISSUE_TEMPLATE/
  README.md
  README.en.md
  README.zh-CN.md
  .gitignore
  .env.example
  LICENSE
```

## Roadmap

- [x] 初始化后端和前端骨架
- [x] 添加 Mock 业务 API
- [x] 实现工单 CRUD
- [x] 构建 SOP 加载与检索
- [x] 实现 LangGraph 工作流
- [x] 添加执行轨迹持久化
- [x] 添加人工审核流程
- [ ] 添加评估 runner

## 当前状态

基础 API 已就绪：

- [x] 仓库骨架
- [x] FastAPI 后端入口
- [x] 健康检查 API
- [x] React/Vite 前端骨架
- [x] Docker 和 Docker Compose 骨架
- [x] Mock 业务 API
- [x] 工单 CRUD API
- [x] Markdown SOP 加载与检索 API
- [x] 面向退款、物流、发票场景的 LangGraph 工单工作流
- [x] 内存版执行轨迹持久化与查询 API
- [x] 支持 approve、edit、reject、escalate 的人工审核流程
