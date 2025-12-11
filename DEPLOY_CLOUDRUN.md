# Cloud Run デプロイ手順書

> **対象**: unified-auth-server プロジェクトをGoogle Cloud Runにデプロイする手順

---

## 1. 前提条件

- Google Cloud Platform アカウント
- プロジェクト: `interview-api-472500`（または任意のプロジェクトID）
- gcloud CLI がインストール済み
- Docker がインストール済み（ローカルビルド時）
- 必要な権限:
  - Cloud Run Admin
  - Secret Manager Admin
  - Service Account Admin
  - Cloud Build Editor

---

## 2. 環境準備

### 2.1 Google Cloud プロジェクトの設定

```bash
# プロジェクトIDを設定
export PROJECT_ID=interview-api-472500
export REGION=asia-northeast1  # 東京リージョン

# gcloud CLI の設定
gcloud config set project $PROJECT_ID
gcloud config set run/region $REGION

# 必要なAPIを有効化
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable firestore.googleapis.com
```

### 2.2 Secret Manager への認証情報登録

```bash
# JWT 秘密鍵の生成
export JWT_SECRET=$(openssl rand -base64 64)

# Secret Managerに登録
echo -n "$JWT_SECRET" | gcloud secrets create jwt-secret-key \
  --data-file=- \
  --replication-policy="automatic"

# Google OAuth 認証情報を登録
echo -n "YOUR_PRODUCTION_CLIENT_ID.apps.googleusercontent.com" | \
  gcloud secrets create google-oauth-client-id \
  --data-file=- \
  --replication-policy="automatic"

echo -n "GOCSPX-YOUR_PRODUCTION_CLIENT_SECRET" | \
  gcloud secrets create google-oauth-client-secret \
  --data-file=- \
  --replication-policy="automatic"
```

### 2.3 サービスアカウントの作成

```bash
# サービスアカウント作成
gcloud iam service-accounts create unified-auth-server \
  --display-name="Unified Auth Server Service Account"

export SERVICE_ACCOUNT=unified-auth-server@${PROJECT_ID}.iam.gserviceaccount.com

# Secret Manager のアクセス権を付与
gcloud secrets add-iam-policy-binding jwt-secret-key \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding google-oauth-client-id \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding google-oauth-client-secret \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/secretmanager.secretAccessor"

# Firestore のアクセス権を付与
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/datastore.user"
```

---

## 3. Google OAuth 設定

### 3.1 OAuth 2.0 クライアントIDの作成

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. 「APIとサービス」→「認証情報」
3. 「認証情報を作成」→「OAuth 2.0 クライアントID」
4. アプリケーションの種類: **ウェブアプリケーション**
5. **承認済みのリダイレクトURI** に追加:
   ```
   https://YOUR_SERVICE_URL/callback/slide-video
   https://YOUR_SERVICE_URL/callback/test-project
   ```
   - `YOUR_SERVICE_URL` はデプロイ後に確定するCloud RunのURL
   - 例: `https://unified-auth-server-xxxx-an.a.run.app`

### 3.2 OAuth認証情報のSecret Managerへの登録

上記2.2で実施済み

---

## 4. Firestore データベースの設定

### 4.1 Firestore の初期化

```bash
# Firestore（Native モード）を有効化
gcloud firestore databases create --region=$REGION

# インデックスの作成（必要に応じて）
# audit_logs コレクション用のインデックスは自動的に作成される
```

### 4.2 プロジェクト設定の登録

```bash
# Firestore にプロジェクト設定を登録（例: slide-video）
# 手動で Firestore Console から登録するか、以下のようにgcloud経由で登録

# 例: gcloud firestore からは直接書き込めないため、アプリケーションから初期データを登録する方法を推奨
```

**または、アプリケーション起動後にAPIエンドポイントから登録**:
```bash
curl -X POST https://YOUR_SERVICE_URL/api/admin/projects \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "slide-video",
    "name": "スライド動画生成システム",
    "allowed_domains": ["i-seifu.jp", "i-seifu.ac.jp"],
    "student_allowed": false,
    "redirect_uris": ["https://YOUR_STREAMLIT_APP_URL/"],
    "token_delivery": "query_param",
    "api_proxy_enabled": true,
    "product_id": "product-SlideVideo"
  }'
```

---

## 5. デプロイ手順

### 5.1 Cloud Build でのデプロイ（推奨）

```bash
# Cloud Build を使用してビルド＆デプロイ
gcloud builds submit --tag gcr.io/$PROJECT_ID/unified-auth-server

# Cloud Run にデプロイ
gcloud run deploy unified-auth-server \
  --image gcr.io/$PROJECT_ID/unified-auth-server \
  --platform managed \
  --region $REGION \
  --service-account $SERVICE_ACCOUNT \
  --allow-unauthenticated \
  --set-env-vars "ENVIRONMENT=production,GCP_PROJECT_ID=$PROJECT_ID,USE_LOCAL_CONFIG=false,SECRET_MANAGER_ENABLED=true,LOG_LEVEL=INFO,LOG_FORMAT=json" \
  --set-secrets "JWT_SECRET_KEY=jwt-secret-key:latest,GOOGLE_CLIENT_ID=google-oauth-client-id:latest,GOOGLE_CLIENT_SECRET=google-oauth-client-secret:latest" \
  --min-instances 0 \
  --max-instances 10 \
  --memory 512Mi \
  --cpu 1 \
  --timeout 60s
```

### 5.2 ローカルでDockerビルド後にデプロイ

```bash
# Docker イメージをビルド
docker build -t gcr.io/$PROJECT_ID/unified-auth-server:latest .

# Google Container Registry にプッシュ
docker push gcr.io/$PROJECT_ID/unified-auth-server:latest

# Cloud Run にデプロイ（上記と同じコマンド）
gcloud run deploy unified-auth-server \
  --image gcr.io/$PROJECT_ID/unified-auth-server:latest \
  ...（以下同様）
```

---

## 6. デプロイ後の確認

### 6.1 サービスURLの取得

```bash
# デプロイされたサービスのURLを取得
export SERVICE_URL=$(gcloud run services describe unified-auth-server \
  --region $REGION \
  --format='value(status.url)')

echo "Service URL: $SERVICE_URL"
```

### 6.2 ヘルスチェック

```bash
# ヘルスチェック
curl $SERVICE_URL/health

# サービス情報
curl $SERVICE_URL/
```

### 6.3 Google OAuth リダイレクトURIの更新

デプロイ後、Google Cloud Console で OAuth 2.0 クライアントIDのリダイレクトURIを更新:
```
https://<YOUR_SERVICE_URL>/callback/slide-video
https://<YOUR_SERVICE_URL>/callback/test-project
```

---

## 7. ログの確認

```bash
# Cloud Run のログを確認
gcloud run services logs read unified-auth-server \
  --region $REGION \
  --limit 50

# リアルタイムでログを監視
gcloud run services logs tail unified-auth-server \
  --region $REGION
```

---

## 8. 環境変数の更新

デプロイ後に環境変数を変更する場合:

```bash
# 環境変数の更新
gcloud run services update unified-auth-server \
  --region $REGION \
  --set-env-vars "NEW_VAR=value"

# Secretの更新
gcloud run services update unified-auth-server \
  --region $REGION \
  --update-secrets "JWT_SECRET_KEY=jwt-secret-key:latest"
```

---

## 9. カスタムドメインの設定（オプション）

```bash
# カスタムドメインをマッピング
gcloud run domain-mappings create \
  --service unified-auth-server \
  --domain auth.your-domain.com \
  --region $REGION

# DNS設定（Cloud DNSまたはドメインレジストラで設定）
# CNAME レコード: auth.your-domain.com → ghs.googlehosted.com
```

---

## 10. トラブルシューティング

### 10.1 よくあるエラー

| エラー | 原因 | 解決策 |
|--------|------|--------|
| `Service unavailable` | コンテナ起動失敗 | ログを確認し、環境変数やSecretが正しいか確認 |
| `Permission denied` | サービスアカウント権限不足 | Secret Manager / Firestore の権限を確認 |
| `OAuth redirect_uri_mismatch` | リダイレクトURI未登録 | Google Cloud Console でリダイレクトURIを追加 |
| `Firestore not initialized` | Firestore が有効化されていない | Firestore を有効化してプロジェクト設定を登録 |

### 10.2 デバッグモード

デバッグログを有効化:
```bash
gcloud run services update unified-auth-server \
  --region $REGION \
  --set-env-vars "LOG_LEVEL=DEBUG"
```

---

## 11. セキュリティ強化（推奨）

### 11.1 Cloud Armor の設定

```bash
# Cloud Armor ポリシーを作成（DDoS対策）
gcloud compute security-policies create auth-server-policy \
  --description="Security policy for auth server"

# レート制限ルールを追加
gcloud compute security-policies rules create 1000 \
  --security-policy=auth-server-policy \
  --expression="true" \
  --action="rate-based-ban" \
  --rate-limit-threshold-count=100 \
  --rate-limit-threshold-interval-sec=60
```

### 11.2 VPC Connector の設定（オプション）

プライベートネットワーク経由でFirestoreにアクセス:
```bash
# VPC Connector を作成
gcloud compute networks vpc-access connectors create auth-connector \
  --region $REGION \
  --network default \
  --range 10.8.0.0/28

# Cloud Run サービスに VPC Connector を設定
gcloud run services update unified-auth-server \
  --region $REGION \
  --vpc-connector auth-connector
```

---

## 12. CI/CD パイプライン（オプション）

### 12.1 Cloud Build トリガーの作成

```yaml
# cloudbuild.yaml
steps:
  # Docker イメージをビルド
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/unified-auth-server:$SHORT_SHA', '.']

  # Container Registry にプッシュ
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/unified-auth-server:$SHORT_SHA']

  # Cloud Run にデプロイ
  - name: 'gcr.io/cloud-builders/gcloud'
    args:
      - 'run'
      - 'deploy'
      - 'unified-auth-server'
      - '--image=gcr.io/$PROJECT_ID/unified-auth-server:$SHORT_SHA'
      - '--region=asia-northeast1'
      - '--platform=managed'
```

---

## 13. 監視とアラート

### 13.1 Cloud Monitoring

```bash
# アラートポリシーの作成（例: エラー率が5%を超えたら通知）
gcloud alpha monitoring policies create \
  --notification-channels=CHANNEL_ID \
  --display-name="Auth Server Error Rate" \
  --condition-display-name="High Error Rate" \
  --condition-threshold-value=0.05 \
  --condition-threshold-duration=60s
```

---

**作成日**: 2024-12-11
**対象バージョン**: unified-auth-server v1.0.0
**最終更新**: 2024-12-11
