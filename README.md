# EdgeStelle — IoT 设备自动化测试与 AI Agent 分析系统

## 概述
EdgeStelle 是一个端到端的 IoT 设备自动化测试平台，由三大模块组成：
1. **云端管理服务** (FastAPI + PostgreSQL) — 管理测试模板与报告
2. **设备端 SDK** (Python / C++) — 拉取模板、执行测试、上报结果
3. **AI Agent 分析引擎** — 自动诊断异常，输出 Markdown 报告

## 快速开始

### 1. 启动基础设施
```bash
cd deploy
docker compose up -d
```
启动 PostgreSQL 和 MQTT Broker (Mosquitto)。

### 2. 安装依赖并启动后端
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
后端启动时会自动建表、启动 MQTT 监听、注册 AI Agent 回调。

### 3. 配置环境变量
```bash
cp .env.example .env
# 修改 .env 中的 DATABASE_URL、MQTT、OPENAI_API_KEY 等配置
```

### 4. 创建测试模板
```bash
curl -X POST http://<server>:8000/api/v1/templates \
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
  }'
```

### 5. 运行设备 SDK 模拟测试
```bash
# 设置环境变量（指向你的服务器）
export API_BASE_URL=http://<server>:8000
export MQTT_BROKER_HOST=<server>
export DEVICE_ID=edge-dev-001

cd device_sdk/python
pip install -r requirements.txt
python -m device_sdk.python.sdk <上一步返回的 template_id>
```

### 6. 查看 AI 分析结果
```bash
curl http://<server>:8000/api/v1/reports?status=analyzed
# 或手动触发分析
curl -X POST http://<server>:8000/api/v1/reports/<report_id>/analyze
```

### 7. 访问 Swagger UI
http://<server>:8000/docs

## 项目结构
```
edgestelle/
├── backend/                 # FastAPI 云端后端
│   ├── app/
│   │   ├── config.py        # 配置管理 (pydantic-settings)
│   │   ├── database.py      # 异步数据库引擎 (SQLAlchemy + asyncpg)
│   │   ├── models.py        # ORM 模型 (TestTemplate / TestReport)
│   │   ├── schemas.py       # Pydantic 请求/响应校验
│   │   ├── main.py          # FastAPI 入口 + 路由 + Lifespan
│   │   └── mqtt_listener.py # MQTT 订阅 + 入库 + 回调触发
│   └── requirements.txt
├── device_sdk/
│   ├── python/              # Python 模拟 SDK
│   │   ├── sdk.py           # 完整工作流 (拉取→测试→上报)
│   │   ├── test_runner.py   # 模拟硬件测试
│   │   └── device_config.py # 设备配置
│   └── cpp/                 # C++ SDK (Paho-MQTT + nlohmann/json)
│       ├── edgestelle_device.hpp  # 头文件 SDK
│       ├── main.cpp         # 示例程序
│       └── CMakeLists.txt   # CMake 构建配置
├── ai_agent/
│   └── agent.py             # AI 分析引擎 (LLM + 降级规则引擎)
├── deploy/
│   ├── docker-compose.yml   # PostgreSQL + Mosquitto
│   └── mosquitto/
│       └── mosquitto.conf
├── .env.example
└── README.md
```

## API 接口一览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/templates` | 创建测试模板 |
| GET  | `/api/v1/templates` | 模板列表 |
| GET  | `/api/v1/templates/{id}` | 模板详情 |
| GET  | `/api/v1/reports` | 报告列表 (支持 device_id / status 过滤) |
| GET  | `/api/v1/reports/{id}` | 报告详情 (含 AI 分析) |
| POST | `/api/v1/reports/{id}/analyze` | 手动触发 AI 分析 |
| GET  | `/health` | 健康检查 |

## 技术栈
- **后端**: Python 3.11+ · FastAPI · SQLAlchemy 2.0 (async) · asyncpg
- **数据库**: PostgreSQL 16 (JSONB)
- **消息代理**: Eclipse Mosquitto 2 (MQTT)
- **设备 SDK**: Python (paho-mqtt) · C++ (Paho MQTT C++ / nlohmann/json / libcurl)
- **AI Agent**: OpenAI API (GPT-4o) · 内置降级规则引擎
