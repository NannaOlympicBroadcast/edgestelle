# ============================================================
# EdgeStelle Master Dockerfile
# ============================================================
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# 拷贝源代码
COPY shared/ ./shared/
COPY master/ ./master/
COPY frontend/ ./frontend/
COPY run_master.py .

# 创建数据目录
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["python", "run_master.py"]
