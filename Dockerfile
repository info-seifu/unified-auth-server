# Cloud Run デプロイ用 Dockerfile
FROM python:3.11-slim

# 環境変数を設定
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    HOST=0.0.0.0 \
    ENVIRONMENT=production

# 作業ディレクトリを設定
WORKDIR /app

# システム依存関係をインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 依存関係をコピーしてインストール（キャッシュ効率化）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコピー
COPY app/ ./app/

# セキュリティ: 非rootユーザーで実行
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Cloud Run ではポート 8080 を使用
EXPOSE 8080

# Gunicorn + Uvicorn でサーバーを起動
CMD exec gunicorn --bind :$PORT --workers 1 --worker-class uvicorn.workers.UvicornWorker --threads 8 --timeout 0 app.main:app
