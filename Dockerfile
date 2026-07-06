# =============================================================================
# B2B Customer Develop Platform — Dockerfile
# 多阶段构建：install deps → run
# =============================================================================
FROM python:3.11-slim AS builder

WORKDIR /app

# 只复制依赖文件，利用 Docker 缓存层
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# =============================================================================
FROM python:3.11-slim

WORKDIR /app

# 时区 / 常用工具（非必需，但方便调试）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/*

# 从 builder 阶段复制已安装的 Python 包
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制应用代码
COPY . .

# 创建运行时目录
RUN mkdir -p app/uploads app/static/css app/templates

EXPOSE 8000

# 启动入口 — 用 uvicorn 直接启动（不经过 python main.py，以支持 host 0.0.0.0）
# 所有启动前准备工作通过 CMD 中的 mkdir + python 处理
CMD mkdir -p /app/app/uploads /app/app/static/css && \
    uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info
