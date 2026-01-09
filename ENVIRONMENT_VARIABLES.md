# 環境変数一覧

> **重要**: このドキュメントは環境変数の設定を管理するためのリファレンスです。

---

## Secret Manager（機密情報）

本番環境では、以下の機密情報を Secret Manager で管理してください。

| シークレット名 | 環境変数名 | 用途 | 設定方法 |
|--------------|-----------|------|---------|
| `google-client-id` | `GOOGLE_CLIENT_ID` | Google OAuth クライアントID | Cloud Console で作成 |
| `google-client-secret` | `GOOGLE_CLIENT_SECRET` | Google OAuth クライアントシークレット | Cloud Console で作成 |
| `jwt-secret-key` | `JWT_SECRET_KEY` | JWT署名用秘密鍵（64文字以上推奨） | `openssl rand -base64 64` |
| `api-proxy-hmac-secret` | `API_PROXY_HMAC_SECRET` | APIプロキシのHMAC署名キー | APIプロキシサーバーと共有 |

### Secret Manager への登録コマンド

```bash
export PROJECT_ID=interview-api-472500

# JWT秘密鍵（新規生成の場合）
export JWT_SECRET=$(openssl rand -base64 64)
echo -n "$JWT_SECRET" | gcloud secrets create jwt-secret-key \
  --data-file=- \
  --replication-policy="automatic" \
  --project=$PROJECT_ID

# Google OAuth認証情報（既存の値を登録）
echo -n "YOUR_CLIENT_ID.apps.googleusercontent.com" | \
  gcloud secrets create google-client-id \
  --data-file=- \
  --replication-policy="automatic" \
  --project=$PROJECT_ID

echo -n "GOCSPX-YOUR_CLIENT_SECRET" | \
  gcloud secrets create google-client-secret \
  --data-file=- \
  --replication-policy="automatic" \
  --project=$PROJECT_ID

# APIプロキシHMACシークレット（APIプロキシサーバーと同じ値）
echo -n "YOUR_HMAC_SECRET" | \
  gcloud secrets create api-proxy-hmac-secret \
  --data-file=- \
  --replication-policy="automatic" \
  --project=$PROJECT_ID
```

---

## Cloud Run 環境変数（非機密情報）

本番環境（Cloud Run）で設定すべき環境変数:

| 環境変数名 | 推奨値 | 用途 | 必須 |
|-----------|-------|------|------|
| `ENVIRONMENT` | `production` | 環境識別（development/production） | ✅ |
| `SECRET_MANAGER_ENABLED` | `true` | Secret Manager使用フラグ | ✅ |
| `FIREBASE_ENABLED` | `true` | Firestore使用フラグ | ✅ |
| `GCP_PROJECT_ID` | `interview-api-472500` | GCPプロジェクトID | ✅ |
| `API_PROXY_SERVER_URL` | `https://api-key-server-856773980753.asia-northeast1.run.app` | APIプロキシサーバーURL | ✅ |
| `API_PROXY_CLIENT_ID` | `unified-auth-server` | APIプロキシクライアントID | ✅ |
| `USE_LOCAL_CONFIG` | `false` | ローカル設定使用（本番ではfalse） | ✅ |
| `LOG_LEVEL` | `INFO` | ログレベル（INFO/DEBUG/WARNING/ERROR） | オプション |
| `LOG_FORMAT` | `json` | ログフォーマット（json/text） | オプション |
| `ALLOWED_HOSTS` | Cloud RunのURL | 許可されたホスト名 | オプション |
| `CORS_ORIGINS` | アプリのURL（カンマ区切り） | CORS許可オリジン | 推奨 |
| `ALLOWED_DOMAINS` | `i-seifu.jp,i-seifu.ac.jp` | 許可ドメイン（カンマ区切り） | オプション |
| `WORKSPACE_SERVICE_ACCOUNT_FILE` | Secret Managerパス | Admin SDKサービスアカウント | グループ検証時 |
| `WORKSPACE_ADMIN_EMAIL` | 管理者メール | ドメイン委任用管理者メール | グループ検証時 |

### Cloud Run での設定方法

**初回デプロイ時**:

```bash
gcloud run deploy unified-auth-server \
  --image gcr.io/$PROJECT_ID/unified-auth-server \
  --region asia-northeast1 \
  --platform managed \
  --set-env-vars "ENVIRONMENT=production,SECRET_MANAGER_ENABLED=true,FIREBASE_ENABLED=true,GCP_PROJECT_ID=$PROJECT_ID,API_PROXY_SERVER_URL=https://api-key-server-856773980753.asia-northeast1.run.app,API_PROXY_CLIENT_ID=unified-auth-server,USE_LOCAL_CONFIG=false,LOG_LEVEL=INFO,LOG_FORMAT=json" \
  --set-secrets "GOOGLE_CLIENT_ID=google-client-id:latest,GOOGLE_CLIENT_SECRET=google-client-secret:latest,JWT_SECRET_KEY=jwt-secret-key:latest,API_PROXY_HMAC_SECRET=api-proxy-hmac-secret:latest"
```

**環境変数を追加・更新する場合**（既存設定を保持）:

```bash
gcloud run services update unified-auth-server \
  --region asia-northeast1 \
  --update-env-vars "NEW_VAR=value"
```

---

## ローカル開発環境

ローカル開発では `.env` ファイルに環境変数を設定してください。

### .env ファイルの例

```bash
# Environment
ENVIRONMENT=development
DEBUG=true

# Server
HOST=0.0.0.0
PORT=8000

# Google OAuth
GOOGLE_CLIENT_ID=YOUR_DEV_CLIENT_ID.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-YOUR_DEV_CLIENT_SECRET
GOOGLE_REDIRECT_URI=http://localhost:8000/callback/{project_id}

# JWT
JWT_SECRET_KEY=your-local-secret-key-at-least-64-characters-long-for-security
JWT_ALGORITHM=HS256
JWT_EXPIRY_DAYS=30

# Google Cloud
GCP_PROJECT_ID=interview-api-472500
USE_FIREBASE_EMULATOR=false

# Secret Manager
SECRET_MANAGER_ENABLED=false

# API Proxy
API_PROXY_SERVER_URL=https://api-key-server-856773980753.asia-northeast1.run.app
API_PROXY_HMAC_SECRET=your-hmac-secret
API_PROXY_CLIENT_ID=unified-auth-server

# Workspace Admin SDK（グループ検証を使う場合）
WORKSPACE_SERVICE_ACCOUNT_FILE=/path/to/service-account.json
WORKSPACE_ADMIN_EMAIL=admin@i-seifu.jp

# Allowed Domains
ALLOWED_DOMAINS=i-seifu.jp,i-seifu.ac.jp,gmail.com

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:8501,http://localhost:8000
CORS_ALLOW_CREDENTIALS=true

# Logging
LOG_LEVEL=DEBUG
LOG_FORMAT=text

# Development Mode
USE_LOCAL_CONFIG=true
```

### .env ファイルの作成

```bash
# .env.example をコピー
cp .env.example .env

# エディタで編集
nano .env
```

**重要**: `.env` ファイルは `.gitignore` に含まれているため、Git にコミットされません。

---

## 環境変数の検証

### 必須環境変数のチェック

起動時に以下の環境変数が設定されているか確認されます：

- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `JWT_SECRET_KEY`

これらが設定されていない場合、アプリケーションは起動時にエラーを出します。

### 現在の設定を確認

```bash
# Cloud Run の環境変数を確認
gcloud run services describe unified-auth-server \
  --region asia-northeast1 \
  --project interview-api-472500 \
  --format="yaml(spec.template.spec.containers[0].env)"

# ローカルで設定を確認（開発モードのみ）
curl http://localhost:8000/api/config
```

---

## トラブルシューティング

### 環境変数が読み込まれない

**症状**: アプリケーション起動時に環境変数が見つからないエラー

**確認事項**:
1. `.env` ファイルがプロジェクトルートに存在するか
2. 環境変数名が正しいか（大文字小文字を含む）
3. 値にスペースや改行が含まれていないか

### Secret Manager から読み込めない

**症状**: `Secret not found` エラー

**確認事項**:
1. Secret Manager でシークレットが作成されているか
2. Cloud Run のサービスアカウントに `Secret Manager Secret Accessor` ロールが付与されているか
3. `SECRET_MANAGER_ENABLED=true` が設定されているか

```bash
# シークレット一覧を確認
gcloud secrets list --project=interview-api-472500

# 権限を確認
gcloud secrets get-iam-policy jwt-secret-key --project=interview-api-472500
```

---

## セキュリティのベストプラクティス

1. **本番環境では Secret Manager を使用**
   - `.env` ファイルは開発環境のみ
   - 本番環境では全ての機密情報を Secret Manager で管理

2. **環境変数の命名規則**
   - すべて大文字（例: `GOOGLE_CLIENT_ID`）
   - 単語はアンダースコア区切り

3. **機密情報のログ出力禁止**
   - JWT秘密鍵、APIキー、シークレットは絶対にログに出力しない
   - デバッグ時も注意

4. **定期的なローテーション**
   - JWT秘密鍵は3ヶ月ごとに更新推奨
   - OAuth クライアントシークレットは6ヶ月ごとに更新推奨

---

**作成日**: 2026-01-09
**最終更新**: 2026-01-09
