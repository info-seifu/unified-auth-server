#!/bin/bash
# Cloud Run デプロイスクリプト
# 統合認証サーバー（unified-auth-server）を本番環境にデプロイします

set -e  # エラーが発生したら即座に終了

# カラー出力設定
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# プロジェクト設定
PROJECT_ID="interview-api-472500"
SERVICE_NAME="unified-auth-server"
REGION="asia-northeast1"
ENV_FILE=".env.production"

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  統合認証サーバー デプロイ開始${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# 環境変数ファイルの存在確認
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}エラー: $ENV_FILE が見つかりません${NC}"
    echo "デプロイを中止します。"
    exit 1
fi

echo -e "${GREEN}✓${NC} 環境変数ファイル確認: $ENV_FILE"

# GCPプロジェクトの確認
echo ""
echo -e "${YELLOW}使用するGCPプロジェクト: $PROJECT_ID${NC}"
echo -e "${YELLOW}デプロイ先リージョン: $REGION${NC}"
echo -e "${YELLOW}サービス名: $SERVICE_NAME${NC}"
echo ""

# 確認プロンプト（スキップ可能）
if [ "$1" != "--yes" ] && [ "$1" != "-y" ]; then
    read -p "デプロイを続行しますか？ (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "デプロイを中止しました。"
        exit 0
    fi
fi

echo ""
echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  Dockerイメージのビルド${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# Dockerイメージのビルド
DOCKER_IMAGE="asia-northeast1-docker.pkg.dev/$PROJECT_ID/$SERVICE_NAME/$SERVICE_NAME:latest"
echo "Dockerイメージをビルド中: $DOCKER_IMAGE"
docker build -t "$DOCKER_IMAGE" .

if [ $? -ne 0 ]; then
    echo -e "${RED}エラー: Dockerビルドに失敗しました${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Dockerイメージのビルド完了"

echo ""
echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  Artifact Registryへプッシュ${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# Docker認証設定（初回のみ必要）
gcloud auth configure-docker asia-northeast1-docker.pkg.dev --quiet

# イメージのプッシュ
echo "イメージをプッシュ中: $DOCKER_IMAGE"
docker push "$DOCKER_IMAGE"

if [ $? -ne 0 ]; then
    echo -e "${RED}エラー: Dockerプッシュに失敗しました${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Artifact Registryへのプッシュ完了"

echo ""
echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  Cloud Runへデプロイ${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# Cloud Runへデプロイ
gcloud run deploy "$SERVICE_NAME" \
    --image "$DOCKER_IMAGE" \
    --region "$REGION" \
    --project "$PROJECT_ID" \
    --platform managed \
    --allow-unauthenticated \
    --min-instances 0 \
    --max-instances 3 \
    --memory 512Mi \
    --cpu 1 \
    --timeout 300 \
    --env-vars-file "$ENV_FILE" \
    --quiet

if [ $? -ne 0 ]; then
    echo -e "${RED}エラー: Cloud Runデプロイに失敗しました${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  デプロイ完了！${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""

# サービスURLの取得
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --region "$REGION" \
    --project "$PROJECT_ID" \
    --format "value(status.url)")

echo -e "${GREEN}✓${NC} サービスURL: ${BLUE}$SERVICE_URL${NC}"
echo ""

# ヘルスチェック
echo "ヘルスチェック中..."
HEALTH_STATUS=$(curl -s "$SERVICE_URL/health" | python -m json.tool 2>/dev/null)

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} ヘルスチェック成功"
    echo "$HEALTH_STATUS"
else
    echo -e "${YELLOW}⚠${NC} ヘルスチェックの確認に失敗しました（サービスは起動している可能性があります）"
fi

echo ""
echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  次のステップ${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""
echo "1. ログ確認:"
echo "   gcloud run services logs read $SERVICE_NAME --region $REGION --limit 50"
echo ""
echo "2. サービス詳細:"
echo "   gcloud run services describe $SERVICE_NAME --region $REGION"
echo ""
echo "3. 動作確認:"
echo "   curl $SERVICE_URL/health"
echo ""
