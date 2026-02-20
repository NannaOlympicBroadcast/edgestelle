# EdgeStelle — IoT 设备自动化测试与 AI Agent 分析平台

## 概述

EdgeStelle 是一个端到端的 IoT 设备自动化测试平台，支持模板化指标定义、设备 SDK 自动化上报、AI 智能诊断分析、飞书生态集成与现代化 Web 管理 UI。

| 模块 | 技术栈 | 职责 |
|------|--------|------|
| 云端后端 | FastAPI + PostgreSQL + SQLAlchemy 2 | API、鉴权、模板/报告管理 |
| Web 管理端 | React 19 + Vite 6 + TailwindCSS v4 | 仪表盘、报告查看、模板/Key 管理 |
| 设备 SDK | Python / C++ | 拉取模板、执行测试、MQTT / HTTP 上报 |
| MQTT 监听 | paho-mqtt | 订阅设备 Topic、校验入库 |
| AI Agent | OpenAI-compatible API | 异常分析、Markdown 诊断报告 |
| 飞书集成 | Feishu Open API | OAuth 登录、云文档创建、群消息卡片推送 |

---

## 项目结构

```
edgestelle/
├── backend/
│   ├── app/
│   │   ├── config.py              # 配置管理 (pydantic-settings)
│   │   ├── database.py            # 异步 DB 引擎 (asyncpg)
│   │   ├── models.py              # ORM: TestTemplate / TestReport / User / ApiKey / SystemConfig
│   │   ├── schemas.py             # Pydantic v2 请求/响应 Schema
│   │   ├── security.py            # JWT 签发/验证 + API Key 哈希
│   │   ├── dependencies.py        # 鉴权依赖 (Bearer JWT + X-API-Key)
│   │   ├── main.py                # FastAPI 入口 (Router 注册 + CORS + Lifespan)
│   │   ├── mqtt_listener.py       # MQTT 订阅 + 入库 + AI 回调
│   │   ├── routers/
│   │   │   ├── auth.py            # 飞书 OAuth 登录 / callback / /me
│   │   │   ├── api_keys.py        # API Key 创建/查看/撤销
│   │   │   ├── templates.py       # 测试模板 CRUD
│   │   │   ├── reports.py         # 报告列表/详情/手动分析
│   │   │   └── system_config.py   # 系统配置 (管理员)
│   │   └── integrations/
│   │       └── feishu.py          # 飞书 API: 文档创建 + 消息卡片
│   └── requirements.txt
├── web/                           # React 前端
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── App.tsx                # 路由配置
│   │   ├── index.css              # 暗色主题设计系统
│   │   ├── stores/authStore.ts    # Zustand JWT 持久化
│   │   ├── lib/api.ts             # Axios + 自动鉴权拦截器
│   │   ├── components/Layout.tsx  # 侧边栏布局
│   │   └── pages/                 # 登录/仪表盘/报告/模板/Key/设置
│   └── index.html
├── ai_agent/
│   ├── agent.py                   # AI 分析引擎 + 飞书推送
│   └── requirements.txt
├── device_sdk/
│   ├── python/                    # Python SDK
│   └── cpp/                       # C++ SDK
├── deploy/
│   ├── docker-compose.yml         # PostgreSQL + Mosquitto
│   └── mosquitto/mosquitto.conf
├── .env.example
└── README.md
```

---

## 一、环境准备

### 1.1 系统要求

- Python 3.11+
- Node.js 20+ (前端)
- Docker & Docker Compose
- (可选) C++ 编译环境

### 1.2 克隆项目

```bash
git clone <your-repo-url> edgestelle
cd edgestelle
```

### 1.3 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填入以下配置：

```env
# ─── 数据库（与 docker-compose 一致即可）───
POSTGRES_USER=edgestelle
POSTGRES_PASSWORD=edgestelle_secret
POSTGRES_DB=edgestelle
DATABASE_URL=postgresql+asyncpg://edgestelle:edgestelle_secret@localhost:5432/edgestelle

# ─── MQTT ───
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883

# ─── AI Agent（必须配置才能使用 LLM 分析，否则降级为规则引擎）───
OPENAI_API_KEY=sk-your-real-key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o

# ─── JWT（生产环境请使用强随机密钥）───
JWT_SECRET_KEY=change-me-to-a-random-secret
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440

# ─── 飞书 OAuth（从飞书开放平台获取）───
FEISHU_APP_ID=cli_xxxxx
FEISHU_APP_SECRET=xxxxx
FEISHU_REDIRECT_URI=http://localhost:8000/api/v1/auth/feishu/callback
FEISHU_BOT_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxx

# ─── 前端 ───
FRONTEND_URL=http://localhost:5173
```

> **提示：** `JWT_SECRET_KEY` 在生产环境中应使用 `openssl rand -hex 32` 生成。  
> 飞书凭证从 [飞书开放平台](https://open.feishu.cn) 创建应用后获取。

---

## 二、部署基础设施

### 2.1 启动 PostgreSQL + Mosquitto

```bash
cd deploy
docker compose up -d
```

验证：

```bash
docker compose ps
# edgestelle-postgres    running (healthy)
# edgestelle-mosquitto   running

docker exec edgestelle-postgres pg_isready -U edgestelle
# → accepting connections
```

### 2.2 安装后端依赖

```bash
cd edgestelle

# 建议使用虚拟环境
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r backend/requirements.txt
pip install -r ai_agent/requirements.txt
```

### 2.3 安装前端依赖

```bash
cd web
npm install
```

---

## 三、启动服务

### 3.1 启动后端

```bash
cd edgestelle
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

启动时自动完成：**自动建表** → **启动 MQTT 监听** → **注册 AI Agent 回调**。

```
✅ MQTT 已连接并订阅 iot/test/report/#
🚀 MQTT 监听已启动 — localhost:1883
INFO:     Uvicorn running on http://0.0.0.0:8000
```

验证：
```bash
curl http://localhost:8000/health
# → {"status":"ok","service":"edgestelle-backend"}
```

**Swagger UI：** 浏览器打开 `http://<server>:8000/docs`

### 3.2 启动前端

```bash
cd web
npm run dev
```

```
VITE v6.x.x ready in xxx ms
➜ Local:   http://localhost:5173/
```

浏览器打开 `http://localhost:5173`，通过飞书 OAuth 登录后进入管理面板。

> **开发模式提示：** Vite 已配置 API 代理，所有 `/api` 请求自动转发到 `localhost:8000`，无需手动处理跨域。

---

## 四、鉴权体系

EdgeStelle 采用**双重鉴权**机制：

| 方式 | 头部 | 适用场景 |
|------|------|---------|
| JWT Bearer Token | `Authorization: Bearer <token>` | Web UI 用户登录后的 API 访问 |
| API Key | `X-API-Key: esk_xxxx...` | 设备端 SDK / 无人值守脚本 |

### 4.1 飞书 OAuth 登录（Web UI 用户）

1. 前端跳转至 `/api/v1/auth/feishu/login` 获取飞书授权 URL
2. 用户在飞书中授权后，飞书回调到 `/api/v1/auth/feishu/callback`
3. 后端自动注册/更新用户信息，签发 JWT，重定向至前端
4. 前端存储 JWT，后续请求自动附加 `Bearer` 头

### 4.2 API Key（设备 SDK）

登录 Web UI 后，在 **「API Key」** 页面生成密钥：

```bash
# 或通过 CLI (需已登录，拿到 JWT)
curl -X POST http://localhost:8000/api/v1/api-keys \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"name": "生产线A设备"}'
```

> **⚠️ 重要：** 密钥仅在创建时返回一次，请立即保存。后端仅存储 SHA-256 哈希。

SDK 使用时附加 `X-API-Key` 头：

```bash
export EDGESTELLE_API_KEY=esk_xxxxxxxxxxxxxxxx
```

---

## 五、创建测试模板

### 5.1 基础模板

```bash
curl -s -X POST http://localhost:8000/api/v1/templates \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "边缘设备标准测试",
    "version": "1.0",
    "schema_definition": {
      "metrics": [
        {"name": "cpu_temperature", "unit": "°C", "threshold_max": 60},
        {"name": "memory_usage", "unit": "%", "threshold_max": 80},
        {"name": "network_latency", "unit": "ms", "threshold_max": 100},
        {"name": "packet_loss_rate", "unit": "%", "threshold_max": 2}
      ]
    }
  }' | python -m json.tool
```

### 5.2 高级模板（含 AI 自定义分析）

```bash
curl -s -X POST http://localhost:8000/api/v1/templates \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "智能摄像头深度测试",
    "version": "2.0",
    "description": "针对安防摄像头的全面硬件健康检测",
    "schema_definition": {
      "metrics": [
        {
          "name": "npu_temp",
          "unit": "°C",
          "threshold_max": 80,
          "description": "NPU 核心温度，决定了 AI 视觉算法的算力释放"
        },
        {
          "name": "memory_usage",
          "unit": "%",
          "threshold_max": 85,
          "description": "系统内存占用，过高会导致视频流缓冲溢出"
        },
        {
          "name": "packet_loss_rate",
          "unit": "%",
          "threshold_max": 2,
          "description": "网络丢包率，影响云端视频回传的连续性"
        }
      ],
      "analysis_config": {
        "custom_system_prompt": "你是安防摄像头领域的资深排障专家。",
        "workflow_steps": [
          "1. 排查 npu_temp 与画面卡顿的关联。",
          "2. 检查散热系统。",
          "3. 分析 memory_usage 与温度的关联性。",
          "4. 评估网络指标，给出整体诊断。"
        ],
        "focus_areas": ["散热系统", "NPU 算力", "网络稳定性"]
      }
    }
  }' | python -m json.tool
```

> **说明：** `analysis_config` 中的字段均为可选，不填则使用 AI Agent 默认行为。

---

## 六、使用 Python SDK 测试上报

### 6.1 快速运行

```bash
export API_BASE_URL=http://localhost:8000
export MQTT_BROKER_HOST=localhost
export DEVICE_ID=edge-cam-001
# (可选) export EDGESTELLE_API_KEY=esk_xxxx  # SDK 鉴权

python -m device_sdk.python.sdk <TEMPLATE_ID>
```

### 6.2 代码集成

```python
import os
os.environ["API_BASE_URL"] = "http://your-server:8000"
os.environ["DEVICE_ID"] = "edge-cam-001"

from device_sdk.python.device_config import DeviceConfig
from device_sdk.python.sdk import EdgeStelleSDK

sdk = EdgeStelleSDK(DeviceConfig())

# 完整流程：拉取模板 → 执行测试 → MQTT 上报
report = sdk.run("<TEMPLATE_ID>")
print(f"异常: {report['anomaly_summary']}")

sdk.disconnect()
```

### 6.3 批量模拟

```bash
for dev in cam-001 cam-002 cam-003 cam-004 cam-005; do
  DEVICE_ID="edge-$dev" python -m device_sdk.python.sdk <TEMPLATE_ID> &
done
wait
echo "全部设备测试完成"
```

---

## 七、查看分析结果

### 7.1 Web UI

登录 `http://localhost:5173`：

- **仪表盘**：报告统计卡片 + 最新报告列表
- **报告详情**：原始数据 JSON + AI 分析 Markdown 渲染
- **模板管理**：模板列表 + 创建
- **API Key**：密钥生成 / 撤销
- **系统设置**：飞书 Webhook 等配置

### 7.2 API 查询

```bash
# 已分析的报告
curl -s "http://localhost:8000/api/v1/reports?status=analyzed" \
  -H "Authorization: Bearer <JWT>" | python -m json.tool

# 单份详情 (ai_analysis 字段含 Markdown 诊断)
curl -s http://localhost:8000/api/v1/reports/<REPORT_ID> \
  -H "Authorization: Bearer <JWT>" | python -m json.tool

# 手动触发重新分析
curl -s -X POST http://localhost:8000/api/v1/reports/<REPORT_ID>/analyze \
  -H "Authorization: Bearer <JWT>" | python -m json.tool
```

---

## 八、飞书集成

### 8.1 OAuth 登录

在 [飞书开放平台](https://open.feishu.cn) 创建应用，配置：
- **重定向 URL**：`http://<your-domain>:8000/api/v1/auth/feishu/callback`
- **权限**：`contact:user.base:readonly`
- 将 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET` 填入 `.env`

### 8.2 AI 报告自动推送

当 AI Agent 分析完成后，自动执行：

1. **创建飞书云文档** — 将 Markdown 诊断报告写入飞书文档
2. **发送消息卡片** — 通过 Bot Webhook 推送到指定群，包含：
   - 综合评分
   - 异常摘要
   - 快速跳转按钮（飞书文档 / WebUI）

配置方式：
- **环境变量**：`.env` 中设置 `FEISHU_BOT_WEBHOOK_URL`
- **运行时**：Web UI「系统设置」中配置 `feishu_bot_webhook_url`

> 未配置飞书凭证时该功能静默跳过，不影响核心分析流程。

---

## 九、数据流示意

```
Device SDK               Cloud Backend                    AI Agent       飞书
    │                         │                              │            │
    │  ① GET /templates/{id}  │                              │            │
    │────────────────────────>│                              │            │
    │  ← 模板 JSON            │                              │            │
    │                         │                              │            │
    │  ② 执行测试             │                              │            │
    │  ③ 生成报告             │                              │            │
    │                         │                              │            │
    │  ④ MQTT Publish ───────>│  MQTT Listener              │            │
    │  (iot/test/report/xxx)  │  ⑤ 校验 → 入库              │            │
    │                         │  ⑥ 触发回调 ────────────────>│            │
    │                         │                   ⑦ 读取报告+模板         │
    │                         │                   ⑧ 动态组装 Prompt      │
    │                         │                   ⑨ 调用 LLM             │
    │                         │  ⑩ 分析存库  <───────────────│            │
    │                         │                   ⑪ 创建文档 ───────────>│
    │                         │                   ⑫ 推送卡片 ───────────>│
```

---

## API 端点一览

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/health` | ❌ | 健康检查 |
| GET | `/api/v1/auth/feishu/login` | ❌ | 获取飞书授权 URL |
| GET | `/api/v1/auth/feishu/callback` | ❌ | 飞书 OAuth 回调 → JWT |
| GET | `/api/v1/auth/me` | ✅ JWT | 当前用户信息 |
| POST | `/api/v1/api-keys` | ✅ | 创建 API Key |
| GET | `/api/v1/api-keys` | ✅ | 列出 API Key |
| DELETE | `/api/v1/api-keys/{id}` | ✅ | 撤销 API Key |
| GET | `/api/v1/templates` | ❌ | 模板列表 |
| GET | `/api/v1/templates/{id}` | ❌ | 模板详情 (SDK 拉取) |
| POST | `/api/v1/templates` | ✅ | 创建模板 |
| GET | `/api/v1/reports` | ✅ | 报告列表 (`?device_id=` / `?status=`) |
| GET | `/api/v1/reports/{id}` | ✅ | 报告详情 (含 `ai_analysis`) |
| POST | `/api/v1/reports/{id}/analyze` | ✅ | 手动触发 AI 分析 |
| GET | `/api/v1/system/config` | 🔒 Admin | 系统配置列表 |
| PUT | `/api/v1/system/config` | 🔒 Admin | 批量更新系统配置 |

> **鉴权说明：** ✅ = Bearer JWT 或 X-API-Key 均可；🔒 Admin = 仅管理员 JWT

---

## 生产部署建议

| 事项 | 建议 |
|------|------|
| **JWT 密钥** | `openssl rand -hex 32` 生成强密钥 |
| **数据库** | 使用 Alembic 管理迁移；生产环境启用 SSL |
| **HTTPS** | Nginx/Caddy 反代，配置 Let's Encrypt |
| **前端构建** | `cd web && npm run build`，产物位于 `web/dist/`，静态托管或 Nginx 服务 |
| **进程管理** | Systemd / Supervisor / PM2 管理后端进程 |
| **日志** | 配置 `logging` 输出到文件 + 日志轮转 |
| **飞书回调** | 替换 `FEISHU_REDIRECT_URI` 为公网域名 |

```bash
# 前端生产构建
cd web && npm run build
# 产物在 web/dist/，可用 Nginx 或 CDN 托管

# 后端生产启动 (示例)
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 4
```
