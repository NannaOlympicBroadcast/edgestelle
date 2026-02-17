# EdgeStelle ⚡

> 基于 MQTT 的多节点脚本执行与实时日志管理平台

## 架构

```
┌─────────────────┐     MQTT      ┌───────────────────┐
│   Edge Agent 1  │◄────────────►│                   │
│   Edge Agent 2  │◄────────────►│  Mosquitto Broker │
│   Edge Agent N  │◄────────────►│      (TLS)        │
└─────────────────┘               └────────┬──────────┘
                                           │
                                  ┌────────▼──────────┐
                                  │   Master Server   │
                                  │  FastAPI + SQLite  │
                                  │  WebSocket Push    │
                                  └────────┬──────────┘
                                           │
                                  ┌────────▼──────────┐
                                  │    Web Browser     │
                                  │  Vue 3 + xterm.js  │
                                  └───────────────────┘
```

## 技术栈

| 组件 | 技术 |
|------|------|
| Master 后端 | Python 3.10+, FastAPI, SQLAlchemy (async) |
| Agent | Python asyncio + subprocess |
| 通信 | MQTT (paho-mqtt), WebSocket |
| 数据库 | SQLite (aiosqlite) |
| 前端 | Vue 3, Element Plus, xterm.js |
| 加密 | AES-256-GCM, TLS |
| 部署 | Docker Compose, Systemd |

## 快速开始

### 1. 克隆 & 配置

```bash
git clone <repo-url> && cd edgestelle
cp .env.example .env
# 编辑 .env，至少设置 SECRET_KEY
```

### 2. 启动 Master (Docker)

```bash
cd deploy
docker-compose up -d
# Master: http://localhost:8000
# Mosquitto: localhost:1883
```

### 3. 启动 Master (本地开发)

```bash
pip install -e .
python run_master.py
```

### 4. 部署 Agent (Linux)

```bash
sudo bash deploy/install_agent.sh
# 编辑 /opt/edgestelle/.env 确认配置
sudo systemctl restart edgestelle-agent
```

### 5. 启动 Agent (本地测试)

```bash
python run_agent.py
```

## 项目结构

```
edgestelle/
├── shared/              # 共享工具
│   ├── config.py        # 配置加载 (pydantic-settings)
│   ├── protocol.py      # MQTT Topic/Payload 定义
│   ├── crypto.py        # AES-256-GCM 加密
│   └── mqtt_wrapper.py  # MQTT 客户端封装
├── master/              # Master 后端
│   ├── database.py      # SQLAlchemy 模型
│   ├── mqtt_service.py  # MQTT 消息处理
│   ├── ws_manager.py    # WebSocket 管理器
│   ├── api.py           # REST API 路由
│   └── app.py           # FastAPI 应用
├── agent/               # Slave Agent
│   ├── config.py        # 节点 ID 持久化
│   ├── executor.py      # 异步命令执行器
│   └── agent.py         # Agent 主逻辑
├── frontend/
│   └── index.html       # Vue 3 SPA
├── deploy/
│   ├── docker-compose.yml
│   ├── Dockerfile
│   ├── gen_certs.sh     # TLS 证书生成
│   ├── install_agent.sh # Agent systemd 安装
│   └── mosquitto/       # Broker 配置
├── run_master.py
├── run_agent.py
└── pyproject.toml
```

## TLS 加密

```bash
cd deploy && bash gen_certs.sh
# 然后在 .env 中设置:
# MQTT_USE_TLS=true
# MQTT_CA_CERT=deploy/certs/ca.crt
# ...
```

## License

MIT
