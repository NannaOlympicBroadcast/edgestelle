#!/usr/bin/env bash
# ============================================================
# EdgeStelle — TLS 自签名证书生成脚本
# 生成 CA、Server、Client 三套证书
# ============================================================
set -euo pipefail

CERT_DIR="$(cd "$(dirname "$0")" && pwd)/certs"
mkdir -p "$CERT_DIR"
cd "$CERT_DIR"

DAYS=3650  # 10 年有效期
SUBJ_CA="/CN=EdgeStelle CA"
SUBJ_SERVER="/CN=edgestelle-mosquitto"
SUBJ_CLIENT="/CN=edgestelle-client"

echo "📁 证书输出目录: $CERT_DIR"
echo ""

# ---------- 1. 生成 CA ----------
echo "🔐 [1/3] 生成 CA 证书..."
openssl genrsa -out ca.key 2048
openssl req -new -x509 -days $DAYS -key ca.key -out ca.crt -subj "$SUBJ_CA"
echo "   ✅ ca.key, ca.crt"
echo ""

# ---------- 2. 生成 Server 证书 ----------
echo "🔐 [2/3] 生成 Server 证书..."
openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr -subj "$SUBJ_SERVER"
openssl x509 -req -days $DAYS -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out server.crt
rm -f server.csr
echo "   ✅ server.key, server.crt"
echo ""

# ---------- 3. 生成 Client 证书 ----------
echo "🔐 [3/3] 生成 Client 证书..."
openssl genrsa -out client.key 2048
openssl req -new -key client.key -out client.csr -subj "$SUBJ_CLIENT"
openssl x509 -req -days $DAYS -in client.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out client.crt
rm -f client.csr
echo "   ✅ client.key, client.crt"
echo ""

# 清理临时文件
rm -f ca.srl

echo "🎉 所有证书已生成完毕!"
echo ""
echo "文件列表:"
ls -la "$CERT_DIR"
echo ""
echo "接下来请:"
echo "  1. 将 ca.crt, server.crt, server.key 放入 Mosquitto 配置目录"
echo "  2. 将 ca.crt, client.crt, client.key 分发给 Agent"
echo "  3. 在 .env 中设置 MQTT_USE_TLS=true 并填写证书路径"
