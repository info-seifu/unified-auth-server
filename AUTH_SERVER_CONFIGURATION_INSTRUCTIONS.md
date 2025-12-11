# 認証サーバー設定手順書

> **対象**: unified-auth-server プロジェクト（別のVS Code/Claude Codeセッションで作業）
> **目的**: 認証サーバーにスライド動画生成システム用の設定を追加

---

## 1. 前提条件

- 認証サーバーが正常に起動することを確認済み（ポート8000）
- `.env` ファイルが存在し、基本設定が完了している
- `config.py` の修正が完了している（Pydantic v2対応）

---

## 2. 必要な設定作業

### 2.1 Google OAuth認証情報の設定

**ファイル**: `/Volumes/990PRO_SSD/dev/unified-auth-server/.env`

以下の項目に実際のGoogle OAuth認証情報を設定してください：

```bash
# 現在の設定（テスト用）
GOOGLE_CLIENT_ID=test-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=test-client-secret

# ↓ 以下に変更

# 実際のGoogle OAuth認証情報に置き換えてください
# Google Cloud Console > 認証情報 > OAuth 2.0 クライアントID で取得
GOOGLE_CLIENT_ID=YOUR_ACTUAL_CLIENT_ID.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-YOUR_ACTUAL_CLIENT_SECRET
```

**取得方法**:
1. [Google Cloud Console](https://console.cloud.google.com/)にアクセス
2. プロジェクト: `interview-api-472500` を選択（または新規作成）
3. 「APIとサービス」→「認証情報」に移動
4. 「認証情報を作成」→「OAuth 2.0 クライアントID」を選択
5. アプリケーションの種類: **ウェブアプリケーション**
6. 承認済みのリダイレクトURIに以下を追加：
   ```
   http://localhost:8000/callback/slide-video
   http://localhost:8000/callback/test-project
   ```
7. 作成後、クライアントIDとシークレットを`.env`に設定

### 2.2 プロジェクト設定の確認

**ファイル**: `/Volumes/990PRO_SSD/dev/unified-auth-server/app/config.py`

`LOCAL_PROJECT_CONFIGS` の `slide-video` プロジェクト設定を確認してください：

```python
"slide-video": {
    "name": "スライド動画生成システム",
    "type": "streamlit_local",
    "description": "PowerPointから動画を生成するツール",
    "allowed_domains": ["i-seifu.jp", "i-seifu.ac.jp"],
    "student_allowed": False,
    "admin_emails": [],
    "required_groups": [],
    "allowed_groups": [],
    "redirect_uris": ["http://localhost:8501/"],
    "token_delivery": "query_param",
    "token_expiry_days": 30,
    "api_proxy_enabled": True,
    "product_id": "product-SlideVideo",
    "api_proxy_credentials_path": "projects/xxx/secrets/slidevideo-users"
}
```

**必要に応じて変更する項目**:
- `admin_emails`: 管理者メールアドレスを追加（例: `["admin@i-seifu.jp"]`）
- `allowed_domains`: 許可するドメインを追加（開発時にGmailを許可する場合は `["i-seifu.jp", "i-seifu.ac.jp", "gmail.com"]`）
- `api_proxy_credentials_path`: 本番環境のSecret Manager パスに変更（ローカル開発時は不要）

### 2.3 APIプロキシサーバーの認証情報設定（本番環境のみ）

**ローカル開発時**: この手順はスキップ可能です。

**本番環境への移行時**: 以下の設定が必要です。

#### 2.3.1 Secret Managerへの認証情報登録

```bash
# Google Cloud Secret Managerにスライド動画生成システム用の認証情報を登録
# プロジェクトIDを設定
export GCP_PROJECT_ID=interview-api-472500

# Secret Managerにシークレットを作成（JSON形式）
gcloud secrets create slidevideo-users \
  --project=$GCP_PROJECT_ID \
  --replication-policy="automatic" \
  --data-file=- <<EOF
{
  "client_id": "slide-video-client",
  "client_secret": "GENERATE_RANDOM_SECRET_HERE",
  "product_id": "product-SlideVideo"
}
EOF

# 認証サーバーのサービスアカウントにアクセス権を付与
gcloud secrets add-iam-policy-binding slidevideo-users \
  --project=$GCP_PROJECT_ID \
  --member="serviceAccount:YOUR_AUTH_SERVER_SERVICE_ACCOUNT@$GCP_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

#### 2.3.2 config.pyの更新

本番環境用のプロジェクト設定を追加（`config.py`の`LOCAL_PROJECT_CONFIGS`に追加、または本番用設定ファイルを作成）：

```python
"slide-video": {
    # ... その他の設定 ...
    "api_proxy_credentials_path": "projects/interview-api-472500/secrets/slidevideo-users"
}
```

### 2.4 JWT秘密鍵の本番環境設定

**ローカル開発時**: 現在の設定のままで問題ありません。

**本番環境への移行時**: ランダムな256-bit以上の秘密鍵を生成してください。

```bash
# 安全なランダム秘密鍵を生成（macOS/Linux）
openssl rand -base64 64

# 生成された値を .env の JWT_SECRET_KEY に設定
# または、Secret Managerに保存して環境変数から読み込む設定に変更
```

---

## 3. 動作確認手順

### 3.1 認証サーバーの起動

```bash
cd /Volumes/990PRO_SSD/dev/unified-auth-server

# 仮想環境をアクティベート
source venv/bin/activate

# サーバー起動
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3.2 エンドポイントの確認

**ヘルスチェック**:
```bash
curl http://localhost:8000/health
```

期待される応答:
```json
{
  "status": "healthy",
  "timestamp": "2024-12-10T12:34:56.789012"
}
```

**プロジェクト設定の確認**（開発モード）:
```bash
# USE_LOCAL_CONFIG=true の場合、ローカル設定が使用される
# config.py の LOCAL_PROJECT_CONFIGS["slide-video"] が読み込まれる
```

### 3.3 認証フローのテスト

**ブラウザで以下のURLにアクセス**:
```
http://localhost:8000/login/slide-video
```

期待される動作:
1. Google OAuth認証画面にリダイレクト
2. ログイン後、`http://localhost:8000/callback/slide-video` にコールバック
3. ドメイン検証（`i-seifu.jp` または `i-seifu.ac.jp` のメールアドレスのみ許可）
4. JWT トークンが発行される
5. Streamlitアプリ（`http://localhost:8501/?token=xxx`）にリダイレクト

---

## 4. トラブルシューティング

### 4.1 よくあるエラー

| エラー | 原因 | 解決策 |
|--------|------|--------|
| `redirect_uri_mismatch` | Google Cloud ConsoleのリダイレクトURIが未登録 | `http://localhost:8000/callback/slide-video` を登録 |
| `invalid_client` | Google OAuth認証情報が正しくない | `.env` の `GOOGLE_CLIENT_ID` と `GOOGLE_CLIENT_SECRET` を確認 |
| `Email domain not allowed` | ドメイン制限エラー | `config.py` の `allowed_domains` にドメインを追加、または開発時のみGmailを許可 |
| `Project configuration not found` | プロジェクトIDが登録されていない | `config.py` の `LOCAL_PROJECT_CONFIGS` に `slide-video` が存在するか確認 |

### 4.2 デバッグログの有効化

`.env` に以下を追加してデバッグログを有効化：

```bash
DEBUG=true
LOG_LEVEL=DEBUG
```

---

## 5. セキュリティチェックリスト

- [ ] `.env` ファイルが `.gitignore` に含まれている
- [ ] Google OAuth認証情報を本番用に変更済み
- [ ] JWT秘密鍵がランダムな256-bit以上の値になっている
- [ ] `allowed_domains` に適切なドメインのみが設定されている
- [ ] 開発環境でGmailを許可している場合、本番環境では削除する
- [ ] 本番環境ではSecret Managerを使用してAPIプロキシ認証情報を管理

---

## 6. 次のステップ

認証サーバーの設定が完了したら、スライド動画生成システム側で以下を実施してください：

1. **認証フロー実装**: `auth_server_client.py` の作成
2. **auth.py の修正**: `USE_AUTH_SERVER` フラグに応じた動作分岐
3. **ローカル統合テスト**: 3システム連携のテスト
4. **本番環境デプロイ**: Cloud Runへのデプロイ

---

## 7. 参考資料

- **DESIGN.md**: 3システムアーキテクチャの設計書
- **unified-auth-server/README.md**: 認証サーバーの詳細ドキュメント
- **Google OAuth 2.0 ドキュメント**: https://developers.google.com/identity/protocols/oauth2
- **Pydantic Settings**: https://docs.pydantic.dev/latest/concepts/pydantic_settings/

---

**作成日**: 2024-12-10
**対象バージョン**: unified-auth-server v1.0.0
**最終更新**: 2024-12-10
