#!/usr/bin/env bash
# ============================================================
# EdgeStelle — Agent 安装脚本（适用于 Linux 边缘节点）
# 功能：
#   1. 创建 Python 虚拟环境
#   2. 安装依赖
#   3. 生成 systemd service 文件
#   4. 启用并启动服务
# ============================================================
set -euo pipefail

# ---------- 配置 ----------
INSTALL_DIR="/opt/edgestelle"
SERVICE_NAME="edgestelle-agent"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="$INSTALL_DIR/venv"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

info() { echo -e "${CYAN}[INFO]${NC} $1"; }
ok() { echo -e "${GREEN}[OK]${NC} $1"; }
err() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ---------- 检查 root ----------
if [ "$EUID" -ne 0 ]; then
    err "请使用 root 运行此脚本: sudo bash install_agent.sh"
fi

# ---------- 检查 Python ----------
if ! command -v $PYTHON_BIN &> /dev/null; then
    err "未找到 $PYTHON_BIN，请先安装 Python 3.10+"
fi
PYTHON_VER=$($PYTHON_BIN --version 2>&1 | awk '{print $2}')
info "检测到 Python 版本: $PYTHON_VER"

# ---------- 创建安装目录 ----------
info "创建安装目录: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"

# ---------- 复制项目文件 ----------
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
info "从 $SCRIPT_DIR 复制项目文件..."
cp -r "$SCRIPT_DIR/shared" "$INSTALL_DIR/"
cp -r "$SCRIPT_DIR/agent" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/run_agent.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/pyproject.toml" "$INSTALL_DIR/"

# 复制或创建 .env
if [ -f "$SCRIPT_DIR/.env" ]; then
    cp "$SCRIPT_DIR/.env" "$INSTALL_DIR/.env"
    ok ".env 已复制"
elif [ -f "$SCRIPT_DIR/.env.example" ]; then
    cp "$SCRIPT_DIR/.env.example" "$INSTALL_DIR/.env"
    info "已从 .env.example 创建 .env，请编辑 $INSTALL_DIR/.env 填入实际配置！"
else
    err "未找到 .env 或 .env.example 文件"
fi

# ---------- 创建虚拟环境 ----------
info "创建 Python 虚拟环境..."
$PYTHON_BIN -m venv "$VENV_DIR"
ok "虚拟环境: $VENV_DIR"

# ---------- 安装依赖 ----------
info "安装 Python 依赖..."
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -e "$INSTALL_DIR"
ok "依赖安装完成"

# ---------- 生成 systemd 服务文件 ----------
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
info "生成 systemd 服务文件: $SERVICE_FILE"

cat > "$SERVICE_FILE" << EOF
[Unit]
Description=EdgeStelle Agent — MQTT 远程执行代理
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR
ExecStart=$VENV_DIR/bin/python run_agent.py
Restart=always
RestartSec=5
StartLimitIntervalSec=60
StartLimitBurst=5

# 安全限制
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=$INSTALL_DIR

# 环境
Environment=PYTHONUNBUFFERED=1

# 日志
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$SERVICE_NAME

[Install]
WantedBy=multi-user.target
EOF

ok "服务文件已生成"

# ---------- 启动服务 ----------
info "重新加载 systemd 并启动服务..."
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl start "$SERVICE_NAME"

ok "🎉 EdgeStelle Agent 已安装并启动!"
echo ""
echo "常用命令:"
echo "  查看状态: systemctl status $SERVICE_NAME"
echo "  查看日志: journalctl -u $SERVICE_NAME -f"
echo "  重启服务: systemctl restart $SERVICE_NAME"
echo "  停止服务: systemctl stop $SERVICE_NAME"
echo ""
echo "配置文件: $INSTALL_DIR/.env"
echo "  ⚠ 请确认 MQTT_BROKER, SECRET_KEY, NODE_NAME 已正确设置"
