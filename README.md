# 統合認証サーバー (Authentication Server)

複数のStreamlitプロジェクトで使用する統合認証サーバー。

## 機能

- **Google OAuth認証**: Google Workspaceアカウントでの認証
- **プロジェクト別アクセス制御**: プロジェクトごとに異なるアクセスルール
- **JWTトークン発行**: 安全なトークンベース認証
- **APIプロキシ中継**: client_secretを秘匿化してAPIプロキシサーバーに転送

## API仕様

詳細は [auth_server_api.yaml](auth_server_api.yaml) を参照してください。

## エンドポイント

### 認証関連
- `GET /login/{project_id}` - Google OAuth認証開始
- `GET /callback/{project_id}` - OAuth認証完了後のコールバック
- `GET /api/verify` - トークン検証
- `POST /api/proxy` - APIプロキシへの中継

### 監査ログ関連 (Phase 3)
- `GET /api/audit/logs` - 監査ログの取得
- `GET /api/audit/login-history` - ログイン履歴の取得
- `GET /api/audit/statistics` - 統計情報の取得
- `GET /api/audit/export` - ログのエクスポート
- `POST /api/audit/cleanup` - 古いログの削除（管理者のみ）

## 技術スタック

- Python 3.9+
- FastAPI (Web framework)
- Google OAuth 2.0 (Authlib)
- JWT (PyJWT)
- Firestore (オプション: プロジェクト設定管理)

## セットアップ

### 1. 必要なパッケージをインストール

```bash
pip install -r requirements.txt
```

### 2. Google OAuth認証の設定

1. [Google Cloud Console](https://console.cloud.google.com/apis/credentials) にアクセス
2. 新しいOAuth 2.0 クライアントIDを作成
3. 認可済みリダイレクトURIに以下を追加:
   - `http://localhost:8000/callback/test-project`
   - `http://localhost:8000/callback/slide-video`
   - 本番環境用: `https://your-auth-server.com/callback/{project_id}`

### 3. 環境設定

`.env.example` をコピーして `.env` を作成:

```bash
cp .env.example .env
```

`.env` ファイルを編集して以下を設定:

```env
# Google OAuth設定
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-your-client-secret

# JWT署名キー（ランダムな文字列を生成）
JWT_SECRET_KEY=your-secure-random-string
```

JWT_SECRET_KEYの生成方法:
```python
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 4. 初期セットアップの確認（オプション）

```bash
python test_setup.py
```

## 開発サーバーの起動

```bash
python run_dev.py
```

サーバーは http://localhost:8000 で起動します。

## 本番環境へのデプロイ

### Cloud Runへのデプロイ（推奨）

#### 自動デプロイスクリプトを使用

```bash
# 対話式デプロイ
./deploy.sh

# 確認なしで即座にデプロイ
./deploy.sh --yes
```

デプロイスクリプトは以下を自動実行します：
1. `.env.production` から環境変数を読み込み
2. Dockerイメージのビルド
3. Artifact Registryへのプッシュ
4. Cloud Runへのデプロイ
5. ヘルスチェックの実行

#### 手動デプロイ

```bash
# 1. Dockerイメージのビルド
docker build -t asia-northeast1-docker.pkg.dev/interview-api-472500/unified-auth-server/unified-auth-server:latest .

# 2. Artifact Registryへプッシュ
docker push asia-northeast1-docker.pkg.dev/interview-api-472500/unified-auth-server/unified-auth-server:latest

# 3. Cloud Runへデプロイ
gcloud run deploy unified-auth-server \
  --image asia-northeast1-docker.pkg.dev/interview-api-472500/unified-auth-server/unified-auth-server:latest \
  --region asia-northeast1 \
  --env-vars-file .env.production \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 3
```

### デプロイ後の確認

```bash
# ヘルスチェック
curl https://unified-auth-server-856773980753.asia-northeast1.run.app/health

# ログ確認
gcloud run services logs read unified-auth-server --region asia-northeast1 --limit 50

# サービス詳細
gcloud run services describe unified-auth-server --region asia-northeast1
```

### 環境変数の管理

本番環境では `.env.production` ファイルで環境変数を管理します：

```env
ENVIRONMENT=production
SECRET_MANAGER_ENABLED=true
GCP_PROJECT_ID=interview-api-472500
# その他の設定...
```

**重要**: 機密情報（OAuth認証情報、JWT秘密鍵）はSecret Managerで管理され、`.env.production`には含まれません。

## 使い方

### 1. ログインテスト

ブラウザで以下のURLにアクセス:
```
http://localhost:8000/login/test-project
```

### 2. API ドキュメント

FastAPIの自動生成ドキュメント:
```
http://localhost:8000/docs
```

### 3. トークン検証

```bash
# トークンを取得後
curl http://localhost:8000/api/verify?token=YOUR_JWT_TOKEN
```

## プロジェクト構成

```
auth-server/
├── app/
│   ├── __init__.py
│   ├── config.py           # 設定管理
│   ├── main.py            # FastAPIアプリケーション
│   ├── core/              # コア機能
│   │   ├── __init__.py
│   │   ├── errors.py      # エラーハンドリング
│   │   ├── firestore_client.py  # Firestore接続
│   │   ├── hmac_signer.py      # HMAC署名生成
│   │   ├── jwt_handler.py       # JWT処理
│   │   ├── oauth.py            # Google OAuth処理
│   │   ├── project_config.py   # プロジェクト設定管理
│   │   ├── secret_manager.py   # Secret Manager統合
│   │   └── validators.py       # バリデーション
│   ├── models/            # データモデル
│   │   ├── __init__.py
│   │   └── schemas.py     # Pydanticスキーマ
│   └── routes/            # APIルート
│       ├── __init__.py
│       ├── auth.py        # 認証エンドポイント
│       ├── proxy.py       # APIプロキシエンドポイント
│       └── audit.py       # 監査ログエンドポイント
├── requirements.txt       # Pythonパッケージ
├── .env.example          # 環境設定サンプル
├── run_dev.py            # 開発サーバー起動スクリプト
├── test_setup.py         # 初期セットアップテスト
├── DESIGN.md             # 設計書
├── auth_server_api.yaml  # OpenAPI仕様
└── README.md             # このファイル
```

## 開発モードの機能

開発モードでは以下の追加エンドポイントが利用可能:

- `GET /api/config` - 現在の設定を確認
- `GET /api/projects` - 利用可能なプロジェクト一覧
- `GET /api/projects/{project_id}` - プロジェクト設定の詳細

## テスト用プロジェクト

開発環境では以下のプロジェクトが事前設定されています:

### test-project
- 用途: 開発・テスト用
- 特徴: Gmailアドレスも許可（テスト用）
- ログインURL: http://localhost:8000/login/test-project

### slide-video
- 用途: スライド動画生成システム用
- 特徴: @i-seifu.jp ドメインのみ許可
- ログインURL: http://localhost:8000/login/slide-video

## 実装状況

✅ **Phase 1: 基本認証機能（完了）**
- Google OAuth統合
- JWTトークン発行
- プロジェクト設定管理
- ドメイン・学生アカウント検証

✅ **Phase 2: APIプロキシ統合（完了）**
- `/api/proxy` エンドポイント
- Secret Manager統合（client_secret管理）
- HMAC署名生成
- APIプロキシサーバーへの中継

✅ **Phase 3: 監査ログ機能（完了）**
- ログイン成功/失敗の記録
- API呼び出しの詳細記録
- ログの検索・フィルタリング機能
- ユーザー別ログイン履歴
- 統計情報の集計（ログイン数、ユニークユーザー数、API呼び出し数など）
- 古いログの自動削除機能（デフォルト: 90日保持）
- JSON形式でのエクスポート機能

## トラブルシューティング

### ModuleNotFoundError

```bash
pip install -r requirements.txt
```

### Google OAuth エラー

1. `.env` ファイルの `GOOGLE_CLIENT_ID` と `GOOGLE_CLIENT_SECRET` を確認
2. Google Cloud Console でリダイレクトURIが正しく設定されているか確認

### ポート使用中エラー

```bash
# ポート8000を使用しているプロセスを確認
netstat -ano | findstr :8000

# 別のポートで起動
PORT=8001 python run_dev.py
```

## 関連プロジェクト

- **APIプロキシサーバー**: `C:\Users\濱田英樹\Documents\dev\api-key-server\api-key-server`
- **クライアント（スライド動画生成）**: `C:\Users\濱田英樹\Documents\dev\SlideMovie\sogo-slide-local-video`

## ライセンス

（プロジェクトのライセンスを記載）
