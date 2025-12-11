# Cloud Run デプロイ用 Dockerfile
FROM python:3.11-slim

# 作業ディレクトリを設定
WORKDIR /app

# 依存関係をコピーしてインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコピー
COPY app/ ./app/

# 環境変数を設定（デフォルト値）
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV HOST=0.0.0.0
ENV ENVIRONMENT=production

# Cloud Run ではポート 8080 を使用
EXPOSE 8080

# Gunicorn + Uvicorn でサーバーを起動
CMD exec gunicorn --bind :$PORT --workers 1 --worker-class uvicorn.workers.UvicornWorker --timeout 0 app.main:app
