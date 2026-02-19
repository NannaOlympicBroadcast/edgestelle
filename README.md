# EdgeStelle — IoT 设备自动化测试与 AI Agent 分析系统

## 概述

EdgeStelle 是一个端到端的 IoT 设备自动化测试平台：

| 模块 | 技术栈 | 职责 |
|------|--------|------|
| 云端后端 | FastAPI + PostgreSQL | 管理测试模板、存储报告、提供 API |
| 设备 SDK | Python / C++ | 拉取模板、执行测试、MQTT 上报 |
| MQTT 监听 | paho-mqtt | 订阅设备上报、校验入库 |
| AI Agent | OpenAI API | 智能分析异常、输出诊断报告 |

---

## 一、环境准备

### 1.1 系统要求

- Linux 服务器 (推荐 Ubuntu 22.04 / CentOS 8+)
- Python 3.11+
- Docker & Docker Compose
- (可选) C++ 编译环境 (g++ 10+, CMake 3.16+)

### 1.2 克隆项目

```bash
git clone <your-repo-url> edgestelle
cd edgestelle
```

### 1.3 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，按需修改以下关键配置：

```env
# 数据库（与 docker-compose 中一致即可）
POSTGRES_USER=edgestelle
POSTGRES_PASSWORD=edgestelle_secret
POSTGRES_DB=edgestelle
DATABASE_URL=postgresql+asyncpg://edgestelle:edgestelle_secret@localhost:5432/edgestelle

# MQTT
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883

# AI Agent（必须配置才能使用 LLM 分析，否则降级为规则引擎）
OPENAI_API_KEY=sk-your-real-key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o
```

---

## 二、部署基础设施

### 2.1 启动 PostgreSQL + Mosquitto

```bash
cd deploy
docker compose up -d
```

验证服务状态：

```bash
# 查看容器
docker compose ps

# 预期输出:
#   edgestelle-postgres    running (healthy)
#   edgestelle-mosquitto   running

# 验证数据库可连接
docker exec edgestelle-postgres pg_isready -U edgestelle
# → accepting connections
```

### 2.2 安装 Python 依赖

```bash
cd ~/edgestelle

# 建议使用虚拟环境
python -m venv .venv
source .venv/bin/activate

# 安装后端 + Agent 全部依赖
pip install -r backend/requirements.txt
pip install -r ai_agent/requirements.txt
pip install -r device_sdk/python/requirements.txt
```

---

## 三、启动后端服务

```bash
cd ~/edgestelle
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

**启动成功日志：**
```
✅ MQTT 已连接并订阅 iot/test/report/#
🚀 MQTT 监听已启动 — localhost:1883
INFO:     Uvicorn running on http://0.0.0.0:8000
```

> 启动时自动执行：建表 → 启动 MQTT 监听 → 注册 AI Agent 回调。
> 如果 Broker 未就绪，会打印警告但不影响 API 正常使用。

**验证健康状态：**
```bash
curl http://localhost:8000/health
# → {"status":"ok","service":"edgestelle-backend"}
```

**Swagger UI：** 浏览器打开 `http://<server>:8000/docs`

---

## 四、创建测试模板

模板定义了"测试哪些指标、阈值是多少、AI 如何分析"。

### 4.1 基础模板（最小化）

```bash
curl -s -X POST http://localhost:8000/api/v1/templates \
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

**返回示例（记下 `id`，后续步骤要用）：**
```json
{
    "id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
    "name": "边缘设备标准测试",
    "version": "1.0",
    ...
}
```

### 4.2 高级模板（含指标语义 + AI 分析配置）

```bash
curl -s -X POST http://localhost:8000/api/v1/templates \
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
        "custom_system_prompt": "你是安防摄像头领域的资深排障专家，语气严厉、专业，直接指出致命缺陷。",
        "workflow_steps": [
          "1. 首先排查 npu_temp 是否与画面推理卡顿有关联。",
          "2. 如果温度过高，优先建议检查散热硅脂或外壳结构设计。",
          "3. 检查 memory_usage 与 npu_temp 的关联性，判断是否存在内存泄漏。",
          "4. 最后评估网络指标，结合丢包率给出整体诊断。"
        ],
        "focus_areas": ["散热系统", "NPU 算力释放", "网络稳定性"]
      }
    }
  }' | python -m json.tool
```

> **要点：**
> - `description` — 告诉 AI Agent 这个指标的业务含义
> - `analysis_config.custom_system_prompt` — 覆盖默认专家角色
> - `analysis_config.workflow_steps` — 强制 Agent 按此顺序分析
> - `analysis_config.focus_areas` — Agent 优先关注的领域
> - 这些字段都是**可选的**，不填则使用默认行为

### 4.3 查询已创建的模板

```bash
# 列表
curl -s http://localhost:8000/api/v1/templates | python -m json.tool

# 详情（替换 <TEMPLATE_ID>）
curl -s http://localhost:8000/api/v1/templates/<TEMPLATE_ID> | python -m json.tool
```

---

## 五、使用 Python SDK 执行测试并上报

### 5.1 命令行快速运行

```bash
cd ~/edgestelle

# 设置设备参数
export API_BASE_URL=http://localhost:8000
export MQTT_BROKER_HOST=localhost
export MQTT_BROKER_PORT=1883
export DEVICE_ID=edge-cam-001

# 运行（替换 <TEMPLATE_ID> 为第四步返回的 id）
python -m device_sdk.python.sdk <TEMPLATE_ID>
```

**完整输出示例：**
```
📥 正在拉取模板 — http://localhost:8000/api/v1/templates/a1b2c3d4-...
✅ 模板已获取 — name=智能摄像头深度测试 version=2.0
🧪 开始执行测试 — 3 个指标
📊 测试完成 — 异常指标: ['npu_temp=83.21°C (> 80)']
✅ MQTT 已连接 — broker=localhost:1883
📡 发布到 iot/test/report/edge-cam-001 — payload_size=487 bytes
📤 报告已发布 — mid=1

✅ 测试报告已上报:
{
  "template_id": "a1b2c3d4-...",
  "device_id": "edge-cam-001",
  "timestamp": "2026-02-19T14:05:23+00:00",
  "results": [
    {"name": "npu_temp", "unit": "°C", "value": 83.21, "threshold_max": 80},
    ...
  ],
  "has_anomaly": true,
  "anomaly_summary": ["npu_temp=83.21°C (> 80)"]
}
```

**同时后端日志会显示：**
```
📩 收到消息 — topic=iot/test/report/edge-cam-001
💾 报告已入库 — id=xxxx
🔔 触发 AI 分析 — report_id=xxxx device=edge-cam-001
📋 analysis_config: 用户自定义
🤖 正在调用 LLM (gpt-4o) 进行分析…
✅ LLM 分析完成 — 输出 1523 字符
💾 分析结果已保存
```

### 5.2 在代码中集成 SDK

在自己的 Python 脚本中使用 SDK 执行测试：

```python
"""示例：在代码中使用 EdgeStelle SDK"""
import os

# 1. 配置
os.environ["API_BASE_URL"] = "http://your-server:8000"
os.environ["MQTT_BROKER_HOST"] = "your-server"
os.environ["DEVICE_ID"] = "edge-cam-001"

from device_sdk.python.device_config import DeviceConfig
from device_sdk.python.sdk import EdgeStelleSDK

# 2. 初始化 SDK
config = DeviceConfig()
sdk = EdgeStelleSDK(config)

# 3. 完整流程：拉取模板 → 执行测试 → 上报
template_id = "a1b2c3d4-5678-90ab-cdef-1234567890ab"
report = sdk.run(template_id)
print(f"上报完成，设备: {report['device_id']}")
print(f"异常: {report['anomaly_summary']}")

# 4. 断开连接
sdk.disconnect()
```

**也可以分步执行（适合需要自定义测试数据的场景）：**

```python
from device_sdk.python.device_config import DeviceConfig
from device_sdk.python.sdk import EdgeStelleSDK

sdk = EdgeStelleSDK(DeviceConfig())

# 步骤 A：拉取模板
template = sdk.fetch_template("a1b2c3d4-...")
print(f"模板: {template['name']}, 共 {len(template['schema_definition']['metrics'])} 个指标")

# 步骤 B：执行模拟测试（生成数据）
report = sdk.execute_test(template)

# ——— 可选：替换为真实传感器数据 ———
# report["results"][0]["value"] = read_real_npu_temp()
# report["results"][1]["value"] = get_real_memory_usage()

# 步骤 C：上报
sdk.publish_report(report)
sdk.disconnect()
```

### 5.3 模拟多台设备批量测试

```bash
for dev in cam-001 cam-002 cam-003 cam-004 cam-005; do
  DEVICE_ID="edge-$dev" python -m device_sdk.python.sdk <TEMPLATE_ID> &
done
wait
echo "全部设备测试完成"
```

---

## 六、查看分析结果

### 6.1 查看已分析的报告

```bash
# 列出所有已分析的报告
curl -s "http://localhost:8000/api/v1/reports?status=analyzed" | python -m json.tool

# 查看单份报告（ai_analysis 字段包含完整的 Markdown 诊断）
curl -s http://localhost:8000/api/v1/reports/<REPORT_ID> | python -m json.tool
```

### 6.2 手动触发 / 重新分析

```bash
curl -s -X POST http://localhost:8000/api/v1/reports/<REPORT_ID>/analyze | python -m json.tool
```

---

## 七、数据流示意

```
Device SDK               Cloud Backend                    AI Agent
    │                         │                              │
    │  ① GET /templates/{id}  │                              │
    │────────────────────────>│                              │
    │  ← 模板 JSON            │                              │
    │                         │                              │
    │  ② 模拟/真实测试         │                              │
    │  ③ Fill 模板生成报告     │                              │
    │                         │                              │
    │  ④ MQTT Publish ───────>│  MQTT Listener              │
    │  (iot/test/report/xxx)  │  ⑤ 校验 JSON → 入库          │
    │                         │  ⑥ 触发回调 ────────────────>│
    │                         │                   ⑦ 读取报告+模板
    │                         │                   ⑧ 动态组装 Prompt
    │                         │                   ⑨ 调用 LLM
    │                         │  ⑩ 分析结果存库  <────────────│
    │                         │                              │
```

---

## API 接口一览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/templates` | 创建测试模板 |
| GET  | `/api/v1/templates` | 模板列表 |
| GET  | `/api/v1/templates/{id}` | 模板详情 |
| GET  | `/api/v1/reports` | 报告列表 (`?device_id=` / `?status=`) |
| GET  | `/api/v1/reports/{id}` | 报告详情 (含 `ai_analysis`) |
| POST | `/api/v1/reports/{id}/analyze` | 手动触发 AI 分析 |
| GET  | `/health` | 健康检查 |

---

## 项目结构

```
edgestelle/
├── backend/
│   ├── app/
│   │   ├── config.py          # 配置管理 (pydantic-settings)
│   │   ├── database.py        # 异步数据库引擎
│   │   ├── models.py          # ORM: TestTemplate / TestReport
│   │   ├── schemas.py         # Pydantic 校验 (含 AnalysisConfig)
│   │   ├── main.py            # FastAPI 入口 + 全部路由
│   │   └── mqtt_listener.py   # MQTT 订阅 + 入库 + 回调
│   └── requirements.txt
├── device_sdk/
│   ├── python/
│   │   ├── sdk.py             # Python SDK 完整工作流
│   │   ├── test_runner.py     # 模拟硬件测试数据生成
│   │   ├── device_config.py   # 设备配置
│   │   └── requirements.txt
│   └── cpp/
│       ├── edgestelle_device.hpp  # C++ 头文件 SDK
│       ├── main.cpp               # C++ 示例入口
│       └── CMakeLists.txt
├── ai_agent/
│   ├── agent.py               # AI 分析引擎 (数据驱动 Prompt)
│   └── requirements.txt
├── deploy/
│   ├── docker-compose.yml     # PostgreSQL + Mosquitto
│   └── mosquitto/
│       └── mosquitto.conf
├── .env.example
└── README.md
```
