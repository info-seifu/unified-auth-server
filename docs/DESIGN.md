# 統合認証サーバー 設計書

## 📋 概要

複数のアプリケーション（Streamlit、Webアプリ等）で使用する統合認証サーバー。
Google OAuth認証、JWTトークン発行、APIプロキシ中継機能を提供します。

### 主要機能
1. **Google OAuth認証** - Google Workspaceアカウントでの統一認証
2. **プロジェクト別アクセス制御** - プロジェクトごとに異なる認証ルール
3. **JWTトークン発行** - セキュアなトークンベース認証
4. **APIプロキシ中継** - client_secretを秘匿化してAPIプロキシサーバーに転送

---

## 🎯 3つのシステムの役割分担

このシステムは3つの独立したコンポーネントで構成されています。

### システム間の関係図

```
┌──────────────────────────────────────────────────────────────┐
│ 【1. クライアント】                                            │
│ リポジトリ: sogo-slide-local-video                           │
│ 場所: C:\Users\濱田英樹\Documents\dev\SlideMovie\...         │
│                                                              │
│ 役割:                                                         │
│ • ユーザーインターフェース提供                                │
│ • 認証サーバーにユーザーをリダイレクト                        │
│ • トークンを受け取り・保存                                    │
│ • 認証サーバー経由でAPI呼び出し                               │
│                                                              │
│ 持っている情報:                                               │
│ ✅ PROJECT_ID (例: "slide-video")                           │
│ ✅ AUTH_SERVER_URL                                          │
│ ✅ アプリ固有の設定（TTS、FFmpeg等）                         │
│                                                              │
│ 持っていない情報（秘匿化される）:                             │
│ ❌ Google OAuth client_secret                              │
│ ❌ API Proxy client_secret                                 │
│ ❌ APIキー（OpenAI、Anthropic等）                           │
└──────────────────────────────────────────────────────────────┘
                         ↓ ↑
              認証リクエスト / トークン受信
                         ↓ ↑
┌──────────────────────────────────────────────────────────────┐
│ 【2. 統合認証サーバー】← このシステム                         │
│ リポジトリ: auth-server（新規作成）                          │
│ 場所: C:\Users\濱田英樹\Documents\dev\auth-server            │
│                                                              │
│ 役割:                                                         │
│ • Google OAuth認証の実行                                     │
│ • ユーザー検証（ドメイン、学生チェック等）                    │
│ • JWTトークン発行                                            │
│ • client_secretの管理                                        │
│ • APIプロキシへの中継（client_secret付与）                   │
│                                                              │
│ 持っている情報:                                               │
│ ✅ Google OAuth client_secret (Secret Manager)             │
│ ✅ 各ユーザーのAPI Proxy client_secret (Secret Manager)    │
│ ✅ プロジェクト設定（Firestore）                             │
│ ✅ JWT署名キー                                               │
│                                                              │
│ 持っていない情報:                                             │
│ ❌ 実際のAPIキー（OpenAI、Anthropic等）                     │
│    → これはAPIプロキシサーバーが管理                         │
└──────────────────────────────────────────────────────────────┘
                         ↓ ↑
              APIリクエスト（HMAC署名付き）
                         ↓ ↑
┌──────────────────────────────────────────────────────────────┐
│ 【3. APIプロキシサーバー】                                     │
│ リポジトリ: api-key-server                                   │
│ 場所: C:\Users\濱田英樹\Documents\dev\api-key-server\...     │
│                                                              │
│ 役割:                                                         │
│ • HMAC署名検証                                               │
│ • APIキーの管理                                               │
│ • 外部API（OpenAI、Anthropic、Gemini）への呼び出し           │
│ • レート制限                                                  │
│ • 使用量記録                                                  │
│                                                              │
│ 持っている情報:                                               │
│ ✅ OpenAI API Key                                           │
│ ✅ Anthropic API Key                                        │
│ ✅ Google Cloud API Key (TTS等)                             │
│ ✅ client_id/client_secret のマッピング                      │
│                                                              │
│ 変更内容:                                                     │
│ ⚪ このシステムは変更なし（既存のまま）                       │
└──────────────────────────────────────────────────────────────┘
```

---

## 📋 各システムの責任範囲

### 1. クライアント（Streamlit/Webアプリ）

#### **責任:**
- ✅ ユーザーインターフェースの提供
- ✅ 未認証時に認証サーバーにリダイレクト
- ✅ トークンの受け取りと保存
- ✅ トークンを使った認証済みリクエスト
- ✅ アプリ固有のビジネスロジック

#### **実装が必要なこと:**
1. **認証フロー**
   ```python
   # streamlit_app.py

   AUTH_SERVER_URL = "https://auth.yourcompany.com"
   PROJECT_ID = "slide-video"

   def check_authentication():
       # トークン確認
       if 'access_token' not in st.session_state:
           # 認証サーバーにリダイレクト
           login_url = f"{AUTH_SERVER_URL}/login/{PROJECT_ID}"
           st.redirect(login_url)
   ```

2. **API呼び出し**
   ```python
   def call_api(endpoint, data):
       """認証サーバー経由でAPI呼び出し"""
       response = requests.post(
           f"{AUTH_SERVER_URL}/api/proxy",
           json={"endpoint": endpoint, "data": data},
           headers={"Authorization": f"Bearer {st.session_state.access_token}"}
       )
       return response.json()
   ```

#### **設定ファイル（secrets.toml）:**
```toml
# 機密情報なし
PROJECT_ID = "slide-video"
AUTH_SERVER_URL = "https://auth.yourcompany.com"

# アプリ固有の設定
TTS_SERVICE = "google_cloud"
GOOGLE_TTS_VOICE = "ja-JP-Neural2-D"
FFMPEG_BIN = "C:/ffmpeg/bin/ffmpeg"
```

---

### 2. 統合認証サーバー（このシステム）

#### **責任:**
- ✅ Google OAuth認証の実行
- ✅ ドメイン検証（@i-seifu.jp）
- ✅ 学生アカウントチェック
- ✅ プロジェクト別アクセス制御
- ✅ JWTトークン発行・検証
- ✅ client_secretの安全な管理
- ✅ APIプロキシへの中継（HMAC署名付与）

#### **実装が必要なこと:**
1. **認証エンドポイント**
   ```python
   # app/routes/auth.py

   @app.get("/login/{project_id}")
   def login(project_id: str):
       """Google OAuth認証開始"""
       # プロジェクト設定を取得
       # Google OAuth フロー開始
       # Google認証画面にリダイレクト

   @app.get("/callback/{project_id}")
   def callback(project_id: str, code: str):
       """OAuth認証完了後のコールバック"""
       # 認証コードをトークンと交換
       # ユーザー情報取得
       # ドメイン検証
       # JWTトークン発行
       # クライアントにリダイレクト
   ```

2. **APIプロキシ中継**
   ```python
   # app/routes/proxy.py

   @app.post("/api/proxy")
   def proxy_request(request: ProxyRequest, token: str = Depends(verify_token)):
       """APIプロキシへの中継"""
       # トークン検証
       # ユーザーのclient_secretを取得（Secret Manager）
       # HMAC署名を生成
       # APIプロキシサーバーに転送
       # レスポンスをクライアントに返却
   ```

#### **管理する機密情報:**
```python
# Secret Manager
secrets = {
    "google-oauth-credentials": {
        "client_id": "xxx.apps.googleusercontent.com",
        "client_secret": "GOCSPX-xxx"
    },
    "jwt-secret-key": "ランダムな256-bit文字列",
    "slidevideo-users": {
        "yamada@i-seifu.jp": {
            "client_id": "slidevideo-yamada",
            "client_secret": "SECRET_YAMADA_xxx"
        }
    }
}
```

#### **プロジェクト設定（Firestore）:**
```python
# projects コレクション
projects = {
    "slide-video": {
        "name": "スライド動画生成システム",
        "type": "streamlit_local",
        "allowed_domains": ["i-seifu.jp", "i-seifu.ac.jp"],
        "student_allowed": False,
        "redirect_uris": ["http://localhost:8501/"],
        "token_delivery": "query_param",
        "api_proxy_enabled": True,
        "product_id": "product-SlideVideo"  # ← APIプロキシサーバーのproduct_id
    }
}
```

---

### 3. APIプロキシサーバー

#### **責任:**
- ✅ HMAC署名の検証
- ✅ APIキーの管理
- ✅ 外部API（OpenAI、Anthropic、Gemini）への呼び出し
- ✅ レート制限
- ✅ 使用量記録

#### **実装が必要なこと:**
⚪ **変更なし（既存のまま使用）**

#### **既存のインターフェース:**
```python
# 既存のAPIプロキシサーバーのエンドポイント

POST /api/openai/images/generate
Headers:
  X-Client-ID: slidevideo-yamada
  X-Signature: <HMAC署名>
  X-Timestamp: <タイムスタンプ>
Body:
  {"prompt": "...", "size": "1024x1024"}

POST /api/anthropic/messages
Headers:
  X-Client-ID: slidevideo-yamada
  X-Signature: <HMAC署名>
Body:
  {"model": "claude-3-5-sonnet-20241022", "messages": [...]}
```

#### **検証プロセス:**
1. ✅ X-Client-ID から client_secret を取得
2. ✅ HMAC署名を検証
3. ✅ product_id に紐づくAPIキーを取得
4. ✅ 外部APIを呼び出し
5. ✅ レスポンスを返却

---

## 🔄 データフロー詳細

### フロー1: 初回ログイン

```
[クライアント]
  ユーザーがアプリ起動
  ↓
  secrets.toml から PROJECT_ID と AUTH_SERVER_URL を読み込み
  PROJECT_ID = "slide-video"
  AUTH_SERVER_URL = "https://auth.yourcompany.com"
  ↓
  トークンが無いことを検出
  ↓
  ブラウザを開いて認証サーバーにリダイレクト
  URL: https://auth.yourcompany.com/login/slide-video
  ↓
───────────────────────────────────────────────────────
[認証サーバー]
  ↓
  Firestoreからプロジェクト設定を取得
  project_config = firestore.collection("projects").document("slide-video").get()
  ↓
  Secret Managerから Google OAuth credentials を取得
  oauth_creds = secret_manager.get("google-oauth-credentials")
  ↓
  Google OAuth フロー開始
  redirect_to: https://accounts.google.com/o/oauth2/auth?...
  ↓
───────────────────────────────────────────────────────
[Google OAuth]
  ↓
  ユーザーが @i-seifu.jp アカウントでログイン
  ↓
  認証サーバーのコールバックURLにリダイレクト
  URL: https://auth.yourcompany.com/callback/slide-video?code=xxx
  ↓
───────────────────────────────────────────────────────
[認証サーバー]
  ↓
  認証コードをトークンと交換
  user_info = {
    "email": "yamada@i-seifu.jp",
    "name": "山田太郎"
  }
  ↓
  ドメイン検証
  if domain not in ["i-seifu.jp", "i-seifu.ac.jp"]:
      return 403 Forbidden
  ↓
  学生アカウントチェック
  if is_student(email) and not project_config["student_allowed"]:
      return 403 Forbidden
  ↓
  JWTトークン発行
  token = jwt.encode({
    "email": "yamada@i-seifu.jp",
    "name": "山田太郎",
    "project_id": "slide-video",
    "exp": timestamp + 30days
  }, JWT_SECRET_KEY)
  ↓
  クライアントにリダイレクト
  URL: http://localhost:8501/?token=eyJhbG...
  ↓
───────────────────────────────────────────────────────
[クライアント]
  ↓
  URLパラメータからトークンを取得
  token = query_params.get("token")
  ↓
  セッションに保存
  st.session_state.access_token = token
  ↓
  ✅ 認証完了、アプリのメイン画面を表示
```

### フロー2: API呼び出し（画像生成の例）

```
[クライアント]
  ユーザーが画像生成ボタンをクリック
  ↓
  認証サーバー経由でAPI呼び出し
  POST https://auth.yourcompany.com/api/proxy
  Headers:
    Authorization: Bearer eyJhbG...
  Body:
    {
      "endpoint": "/api/openai/images/generate",
      "data": {
        "prompt": "A beautiful landscape",
        "size": "1024x1024"
      }
    }
  ↓
───────────────────────────────────────────────────────
[認証サーバー]
  ↓
  トークン検証
  payload = jwt.decode(token, JWT_SECRET_KEY)
  email = payload["email"]  # "yamada@i-seifu.jp"
  project_id = payload["project_id"]  # "slide-video"
  ↓
  Secret Managerからclient_secretを取得
  user_creds = secret_manager.get(f"{project_id}-users")[email]
  client_id = user_creds["client_id"]  # "slidevideo-yamada"
  client_secret = user_creds["client_secret"]  # "SECRET_xxx"
  ↓
  HMAC署名を生成
  timestamp = get_current_timestamp()
  signature = hmac.new(
    client_secret,
    f"{timestamp}{json.dumps(data)}",
    hashlib.sha256
  ).hexdigest()
  ↓
  プロジェクト設定からproduct_idを取得
  product_id = project_config["product_id"]  # "product-SlideVideo"
  ↓
  APIプロキシサーバーに転送
  POST https://api-key-server.run.app/v1/chat/product-SlideVideo
  Headers:
    X-Client-ID: slidevideo-yamada
    X-Signature: <HMAC署名>
    X-Timestamp: <タイムスタンプ>
    Content-Type: application/json
  Body:
    {
      "model": "dall-e-3",
      "messages": [{"role": "user", "content": "A beautiful landscape"}],
      "prompt": "A beautiful landscape",
      "size": "1024x1024"
    }
  ↓
───────────────────────────────────────────────────────
[APIプロキシサーバー]
  ↓
  URLパスからproduct_idを抽出
  product_id = "product-SlideVideo"
  ↓
  HMAC署名を検証
  expected_signature = hmac.new(
    stored_client_secret,
    f"{timestamp}\n{method}\n{path}\n{body_hash}",
    hashlib.sha256
  ).hexdigest()

  if signature != expected_signature:
      return 401 Unauthorized
  ↓
  認証コンテキストのproduct_idと一致するか確認
  if context.product_id != product_id:
      return 403 Forbidden
  ↓
  product_idに紐づくOpenAI APIキーを取得
  api_key = settings.get_api_key_for_product(product_id, "openai")
  ↓
  OpenAI APIを呼び出し
  response = openai.images.generate(
    prompt="A beautiful landscape",
    size="1024x1024",
    api_key=api_key
  )
  ↓
  レスポンスを返却
  {
    "url": "https://oaidalleapiprodscus.blob.core.windows.net/...",
    "revised_prompt": "..."
  }
  ↓
───────────────────────────────────────────────────────
[認証サーバー]
  ↓
  APIプロキシからのレスポンスをそのまま転送
  ↓
───────────────────────────────────────────────────────
[クライアント]
  ↓
  画像URLを受信
  ↓
  画像をダウンロードして表示
  ✅ 完了
```

---

## 📚 各システムで必要なドキュメント

### クライアント側で読み込むドキュメント:
1. ✅ `auth_server_api.yaml` - 認証サーバーのAPI仕様
2. ✅ `DESIGN.md` - 全体アーキテクチャと役割分担（このドキュメント）

### 認証サーバー側で読み込むドキュメント:
1. ✅ `auth_server_api.yaml` - 実装すべきAPI仕様
2. ✅ `DESIGN.md` - 詳細設計書（このドキュメント）

### APIプロキシサーバー側で読み込むドキュメント:
- ⚪ 変更なし（既存のまま）
- 参照用: `DESIGN.md` の「APIプロキシサーバーの責任範囲」セクション

---

## 🏗️ アーキテクチャ

### システム構成図

```
┌─────────────────────────────────────────────────────────────┐
│                    クライアントアプリ層                        │
├─────────────────────────────────────────────────────────────┤
│ Streamlitアプリ  │  Webアプリ   │  FastAPI    │  その他     │
│ (ローカル/Cloud) │ (Flask/React)│  サービス   │  アプリ     │
└─────────────────────────────────────────────────────────────┘
                         ↓ 認証リクエスト
┌─────────────────────────────────────────────────────────────┐
│              統合認証サーバー (Cloud Run)                      │
│  ┌────────────────────────────────────────────────────┐    │
│  │ 認証エンドポイント                                   │    │
│  │ - GET /login/{project_id}                          │    │
│  │ - GET /callback/{project_id}                       │    │
│  │ - GET /api/verify                                  │    │
│  └────────────────────────────────────────────────────┘    │
│  ┌────────────────────────────────────────────────────┐    │
│  │ APIプロキシ中継                                      │    │
│  │ - POST /api/proxy                                  │    │
│  │   → client_secretを付与してAPIプロキシに転送        │    │
│  └────────────────────────────────────────────────────┘    │
│                                                             │
│  【認証情報管理】                                            │
│  - Secret Manager: Google OAuth credentials             │
│  - Secret Manager: プロジェクト別client_secret           │
│  - Firestore: プロジェクト設定                            │
└─────────────────────────────────────────────────────────────┘
                         ↓ API呼び出し
┌─────────────────────────────────────────────────────────────┐
│                    APIプロキシサーバー                         │
│  - OpenAI API                                              │
│  - Anthropic API                                           │
│  - Google Cloud API                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔐 認証フロー

### Phase 1: ログイン開始

```
[クライアント]
  ↓ ユーザーがアプリ起動
  ↓ 未認証を検出
  ↓
  ↓ ブラウザでリダイレクト
  ↓ GET https://auth.yourcompany.com/login/slide-video
  ↓
[認証サーバー]
  ↓ プロジェクト設定を取得
  ↓ Google OAuth フロー開始
  ↓
  ↓ 302 Redirect
  ↓
[Google OAuth]
  ↓ ユーザーがGoogleアカウントでログイン
```

### Phase 2: 認証完了

```
[Google OAuth]
  ↓ 認証成功
  ↓ GET https://auth.yourcompany.com/callback/slide-video?code=xxx
  ↓
[認証サーバー]
  ↓ 認証コードをトークンと交換
  ↓ ユーザー情報を取得
  ↓
  ↓ ドメイン検証（@i-seifu.jp）
  ↓ 学生アカウントチェック
  ↓ プロジェクト別ルール検証
  ↓
  ✅ 検証成功
  ↓ JWTトークン発行
  {
    "email": "yamada@i-seifu.jp",
    "name": "山田太郎",
    "project_id": "slide-video",
    "exp": 1738819200
  }
  ↓
  ↓ クライアント種別に応じてトークン返却
  ↓
  ├─ Streamlitアプリ: URLパラメータ
  │  302 Redirect → http://localhost:8501/?token=eyJhbG...
  │
  └─ Webアプリ: HttpOnly Cookie
     Set-Cookie: auth_token=eyJhbG...; HttpOnly; Secure
     302 Redirect → https://attendance.i-seifu.jp/callback
```

### Phase 3: API呼び出し

```
[クライアント]
  ↓ API呼び出しが必要
  ↓ POST https://auth.yourcompany.com/api/proxy
  ↓ Header: Authorization: Bearer <token>
  ↓ Body: {
       "endpoint": "/api/openai/images/generate",
       "data": {"prompt": "..."}
     }
  ↓
[認証サーバー]
  ↓ トークン検証
  ↓ ユーザーのclient_secretを取得（Secret Manager）
  ↓ HMAC署名を生成
  ↓
  ↓ POST https://api-key-server.run.app/api/openai/images/generate
  ↓ Header: X-Client-ID: slidevideo-yamada
  ↓ Header: X-Signature: <HMAC署名>
  ↓ Body: {"prompt": "..."}
  ↓
[APIプロキシサーバー]
  ↓ HMAC署名検証
  ↓ APIキー取得
  ↓ OpenAI API呼び出し
  ↓
  ↓ レスポンス返却
  ↓
[認証サーバー]
  ↓ レスポンスをクライアントに転送
  ↓
[クライアント]
  ✅ API結果を受信
```

---

## 📦 プロジェクト設定

### 設定データ構造

```python
PROJECT_CONFIGS = {
    "project_id": {
        # 基本情報
        "name": str,              # プロジェクト名
        "type": str,              # クライアント種別
        "description": str,       # 説明（オプション）

        # 認証ルール
        "allowed_domains": [str],        # 許可ドメイン
        "student_allowed": bool,         # 学生アカウント可否
        "admin_emails": [str],           # 管理者限定の場合
        "required_groups": [str],        # 必須グループ（オプション）
        "allowed_groups": [str],         # 許可グループ（オプション）
        "required_org_units": [str],     # 必須組織部門（オプション）
        "allowed_org_units": [str],      # 許可組織部門（オプション）

        # リダイレクト設定
        "redirect_uris": [str],   # 許可するリダイレクトURI
        "token_delivery": str,    # トークン返却方法

        # トークン設定
        "token_expiry_days": int, # トークン有効期限（日数）

        # APIプロキシ設定
        "api_proxy_enabled": bool,           # APIプロキシ使用有無
        "product_id": str,                   # APIプロキシのproduct_id（重要！）
        "api_proxy_credentials_path": str,   # Secret Manager パス

        # カスタム検証
        "custom_validation": str  # カスタム検証関数名（オプション）
    }
}
```

### ⚠️ 重要: product_idについて

**`product_id`は、APIプロキシサーバーでプロジェクトごとに異なるAPIキーを使用するために必須です。**

- 例: `"product-SlideVideo"`, `"product-AttendanceSystem"`
- APIプロキシサーバーは、この `product_id` に基づいて適切なOpenAI/Anthropic/Gemini APIキーを選択します
- プロジェクトごとに異なる `product_id` を設定することで、APIキーの使用を分離できます

---

### 🔐 グループベース認証について

**Google Workspaceのグループメンバーシップによるアクセス制御を追加できます。**

#### **設定項目:**

##### **1. `required_groups`（必須グループ）**
- ユーザーが**全ての**グループに所属している必要がある（AND条件）
- 例: `["teachers@i-seifu.jp", "slide-video-users@i-seifu.jp"]`
- 用途: 特定のグループに限定したい場合

##### **2. `allowed_groups`（許可グループ）**
- ユーザーが**いずれか**のグループに所属していればOK（OR条件）
- 例: `["teachers@i-seifu.jp", "staff@i-seifu.jp"]`
- 用途: 複数のグループのいずれかに所属していれば許可

---

### 🏢 組織部門ベース認証について

**Google Workspaceの組織部門（Organizational Unit）によるアクセス制御を追加できます。**

#### **設定項目:**

##### **1. `required_org_units`（必須組織部門）**
- ユーザーが**全ての**組織部門に所属している必要がある（AND条件）
- 例: `["/教職員/専任教員", "/IT部門"]`
- 用途: 特定の組織部門に限定したい場合
- 階層的な検証: 子組織部門も自動的に含まれる

##### **2. `allowed_org_units`（許可組織部門）**
- ユーザーが**いずれか**の組織部門に所属していればOK（OR条件）
- 例: `["/教職員", "/管理部門", "/IT部門"]`
- 用途: 複数の組織部門のいずれかに所属していれば許可
- 階層的な検証: 子組織部門も自動的に含まれる

#### **組織部門の階層構造例:**
```
/ (ルート)
├── /学生
│   ├── /学生/高校
│   │   ├── /学生/高校/1年
│   │   ├── /学生/高校/2年
│   │   └── /学生/高校/3年
│   └── /学生/大学
│       ├── /学生/大学/情報学部
│       └── /学生/大学/経営学部
├── /教職員
│   ├── /教職員/専任教員
│   ├── /教職員/非常勤講師
│   └── /教職員/事務職員
├── /管理部門
│   ├── /管理部門/理事会
│   └── /管理部門/校長室
└── /IT部門
    ├── /IT部門/システム管理
    └── /IT部門/ヘルプデスク
```

#### **検証の優先順位:**
1. ✅ ドメイン検証（`allowed_domains`）
2. ✅ 学生アカウントチェック（`student_allowed`）
3. ✅ 管理者限定チェック（`admin_emails`）
4. ✅ **必須グループチェック**（`required_groups`）
5. ✅ **許可グループチェック**（`allowed_groups`）
6. ✅ **必須組織部門チェック**（`required_org_units`） ← 新機能
7. ✅ **許可組織部門チェック**（`allowed_org_units`） ← 新機能

#### **Google Directory API の設定が必要:**
- Google Workspace Admin SDK APIを有効化
- サービスアカウントにドメイン全体の委任を設定
- 必要なスコープ:
  - `https://www.googleapis.com/auth/admin.directory.group.readonly` （グループ用）
  - `https://www.googleapis.com/auth/admin.directory.user.readonly` （組織部門用）
```

### プロジェクト種別（type）

| type | 説明 | トークン返却方法 | 用途 |
|------|------|----------------|------|
| `streamlit_local` | Streamlitローカルアプリ | URLパラメータ | 開発環境 |
| `streamlit_cloud` | Streamlit Cloud Run | URLパラメータ | 本番環境 |
| `web_app` | Webアプリ | HttpOnly Cookie | Flask/React等 |
| `api_service` | APIサービス | HttpOnly Cookie | FastAPI等 |

### トークン返却方法（token_delivery）

| token_delivery | 方法 | セキュリティ | 用途 |
|---------------|------|-------------|------|
| `query_param` | URLパラメータ | 中 | Streamlitアプリ |
| `cookie` | HttpOnly Cookie | 高 | Webアプリ |

---

## 🔧 プロジェクト設定例

### 例1: Streamlitローカルアプリ（教職員専用）

```python
"slide-video": {
    "name": "スライド動画生成システム",
    "type": "streamlit_local",
    "description": "PowerPointから動画を生成するツール",

    # 認証ルール
    "allowed_domains": ["i-seifu.jp", "i-seifu.ac.jp"],
    "student_allowed": False,
    "admin_emails": [],
    "required_groups": [],  # グループ制限なし
    "allowed_groups": [],   # グループ制限なし
    "required_org_units": [],  # 組織部門制限なし
    "allowed_org_units": [],   # 組織部門制限なし

    # リダイレクト設定
    "redirect_uris": ["http://localhost:8501/"],
    "token_delivery": "query_param",

    # トークン設定
    "token_expiry_days": 30,

    # APIプロキシ設定
    "api_proxy_enabled": True,
    "product_id": "product-SlideVideo",
    "api_proxy_credentials_path": "projects/xxx/secrets/slidevideo-users"
}
```

### 例2: Webアプリ（学生・教職員両方OK）

```python
"attendance-web": {
    "name": "出席管理Webシステム",
    "type": "web_app",
    "description": "出席記録・管理システム",

    # 認証ルール
    "allowed_domains": ["i-seifu.jp", "i-seifu.ac.jp"],
    "student_allowed": True,  # 学生もOK
    "admin_emails": [],

    # リダイレクト設定
    "redirect_uris": [
        "http://localhost:3000/callback",           # 開発環境
        "https://attendance.i-seifu.jp/callback"    # 本番環境
    ],
    "token_delivery": "cookie",

    # トークン設定
    "token_expiry_days": 7,

    # APIプロキシ設定
    "api_proxy_enabled": False  # API不要
}
```

### 例3: 管理者専用アプリ

```python
"admin-panel": {
    "name": "管理者パネル",
    "type": "web_app",
    "description": "システム管理画面",

    # 認証ルール
    "allowed_domains": ["i-seifu.jp"],
    "student_allowed": False,
    "admin_emails": [  # 管理者限定
        "admin@i-seifu.jp",
        "principal@i-seifu.jp"
    ],

    # リダイレクト設定
    "redirect_uris": ["https://admin.i-seifu.jp/callback"],
    "token_delivery": "cookie",

    # トークン設定
    "token_expiry_days": 1,  # 短い有効期限

    # APIプロキシ設定
    "api_proxy_enabled": False
}
```

### 例4: グループベース認証の例

#### **例4-1: 特定グループのみ許可**

```python
"research-tool": {
    "name": "研究ツール",
    "type": "web_app",
    "description": "研究室専用ツール",

    # 認証ルール
    "allowed_domains": ["i-seifu.jp"],
    "student_allowed": False,
    "admin_emails": [],
    "required_groups": ["research-team@i-seifu.jp"],  # このグループのみ
    "allowed_groups": [],

    # リダイレクト設定
    "redirect_uris": ["https://research.i-seifu.jp/callback"],
    "token_delivery": "cookie",

    # トークン設定
    "token_expiry_days": 7,

    # APIプロキシ設定
    "api_proxy_enabled": True,
    "product_id": "product-ResearchTool"
}
```

#### **例4-2: 複数グループのいずれかに所属**

```python
"faculty-portal": {
    "name": "教職員ポータル",
    "type": "web_app",
    "description": "教職員向けポータルサイト",

    # 認証ルール
    "allowed_domains": ["i-seifu.jp", "i-seifu.ac.jp"],
    "student_allowed": False,
    "admin_emails": [],
    "required_groups": [],
    "allowed_groups": [  # いずれかのグループに所属していればOK
        "teachers@i-seifu.jp",
        "staff@i-seifu.jp",
        "administrators@i-seifu.jp"
    ],

    # リダイレクト設定
    "redirect_uris": ["https://portal.i-seifu.jp/callback"],
    "token_delivery": "cookie",

    # トークン設定
    "token_expiry_days": 30,

    # APIプロキシ設定
    "api_proxy_enabled": False
}
```

#### **例4-3: 複数の必須グループ（AND条件）**

```python
"confidential-system": {
    "name": "機密情報システム",
    "type": "web_app",
    "description": "機密情報を扱うシステム",

    # 認証ルール
    "allowed_domains": ["i-seifu.jp"],
    "student_allowed": False,
    "admin_emails": [],
    "required_groups": [  # 全てのグループに所属している必要がある
        "security-clearance@i-seifu.jp",
        "confidential-access@i-seifu.jp"
    ],
    "allowed_groups": [],

    # リダイレクト設定
    "redirect_uris": ["https://confidential.i-seifu.jp/callback"],
    "token_delivery": "cookie",

    # トークン設定
    "token_expiry_days": 1,  # 短い有効期限

    # APIプロキシ設定
    "api_proxy_enabled": False
}
```

### 例5: 組織部門ベース認証の例

#### **例5-1: 特定組織部門のみ許可**

```python
"teacher-tools": {
    "name": "教員専用ツール",
    "type": "web_app",
    "description": "専任教員のみ利用可能な管理ツール",

    # 認証ルール
    "allowed_domains": ["i-seifu.jp"],
    "student_allowed": False,
    "admin_emails": [],
    "required_groups": [],
    "allowed_groups": [],
    "required_org_units": ["/教職員/専任教員"],  # この組織部門のみ
    "allowed_org_units": [],

    # リダイレクト設定
    "redirect_uris": ["https://teacher-tools.i-seifu.jp/callback"],
    "token_delivery": "cookie",

    # トークン設定
    "token_expiry_days": 30,

    # APIプロキシ設定
    "api_proxy_enabled": True,
    "product_id": "product-TeacherTools"
}
```

#### **例5-2: 複数組織部門のいずれかに所属**

```python
"staff-system": {
    "name": "スタッフシステム",
    "type": "web_app",
    "description": "教職員と管理部門向けシステム",

    # 認証ルール
    "allowed_domains": ["i-seifu.jp", "i-seifu.ac.jp"],
    "student_allowed": False,
    "admin_emails": [],
    "required_groups": [],
    "allowed_groups": [],
    "required_org_units": [],
    "allowed_org_units": [  # いずれかの組織部門に所属していればOK
        "/教職員",      # 全教職員（専任、非常勤、事務）
        "/管理部門",    # 理事会、校長室
        "/IT部門"       # システム管理、ヘルプデスク
    ],

    # リダイレクト設定
    "redirect_uris": ["https://staff.i-seifu.jp/callback"],
    "token_delivery": "cookie",

    # トークン設定
    "token_expiry_days": 14,

    # APIプロキシ設定
    "api_proxy_enabled": False
}
```

#### **例5-3: グループと組織部門の組み合わせ**

```python
"advanced-research": {
    "name": "高度研究システム",
    "type": "web_app",
    "description": "研究グループかつ専任教員のみアクセス可能",

    # 認証ルール
    "allowed_domains": ["i-seifu.jp"],
    "student_allowed": False,
    "admin_emails": [],
    "required_groups": ["research-team@i-seifu.jp"],  # 研究グループ必須
    "allowed_groups": [],
    "required_org_units": ["/教職員/専任教員"],  # かつ専任教員必須
    "allowed_org_units": [],

    # リダイレクト設定
    "redirect_uris": ["https://research.i-seifu.jp/callback"],
    "token_delivery": "cookie",

    # トークン設定
    "token_expiry_days": 7,

    # APIプロキシ設定
    "api_proxy_enabled": True,
    "product_id": "product-AdvancedResearch"
}
```

#### **例5-4: 学生組織部門の階層的許可**

```python
"student-portal": {
    "name": "学生ポータル",
    "type": "web_app",
    "description": "高校生と大学生向けポータル",

    # 認証ルール
    "allowed_domains": ["i-seifu.ac.jp"],
    "student_allowed": True,  # 学生OK
    "admin_emails": [],
    "required_groups": [],
    "allowed_groups": [],
    "required_org_units": [],
    "allowed_org_units": [  # 学生組織部門
        "/学生/高校",   # 高校1-3年全て含む
        "/学生/大学"    # 全学部含む
    ],

    # リダイレクト設定
    "redirect_uris": ["https://student-portal.i-seifu.jp/callback"],
    "token_delivery": "cookie",

    # トークン設定
    "token_expiry_days": 90,

    # APIプロキシ設定
    "api_proxy_enabled": False
}
```

---

## 🔐 セキュリティ設計

### 機密情報の管理

#### **Secret Manager に保存する機密情報（完全版）:**

| Secret名 | 形式 | 説明 | 必須 | 更新日 |
|---------|------|------|------|--------|
| `google-oauth-credentials` | JSON | Google OAuth認証情報 | ✅ 必須 | 初期設定 |
| `jwt-secret-key` | 文字列 | JWT署名キー | ✅ 必須 | 初期設定 |
| `api-proxy-hmac-secret` | 文字列 | **API Proxy ServerとのHMAC認証秘密鍵** | ✅ 必須 | **2025-12-23追加** |
| `workspace-service-account` | JSON | Google Workspace Admin SDK サービスアカウント | ⚪ オプション | グループ/OU検証時 |
| `slidevideo-users` | JSON | ユーザー別APIプロキシ認証情報（旧方式） | ❌ 非推奨 | 旧実装（削除予定） |

#### **1. Google OAuth認証情報**
```json
// Secret名: google-oauth-credentials
{
  "client_id": "xxx.apps.googleusercontent.com",
  "client_secret": "GOCSPX-xxx"
}
```

**登録コマンド:**
```bash
cat > oauth-creds.json <<EOF
{
  "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
  "client_secret": "GOCSPX-YOUR_CLIENT_SECRET"
}
EOF

gcloud secrets create google-oauth-credentials \
  --data-file=oauth-creds.json \
  --project=interview-api-472500

rm oauth-creds.json  # セキュリティのため削除
```

#### **2. JWT署名キー**
```
// Secret名: jwt-secret-key
// 形式: ランダムな256-bit文字列
"a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6"
```

**登録コマンド:**
```bash
# 256-bit (32バイト) のランダムキーを生成
JWT_SECRET=$(openssl rand -base64 32)
echo "生成されたJWT秘密鍵: $JWT_SECRET"

# Secret Managerに保存
echo -n "$JWT_SECRET" | gcloud secrets create jwt-secret-key \
  --data-file=- \
  --project=interview-api-472500
```

#### **3. API Proxy HMAC秘密鍵（新規追加 - 2025-12-23）**
```
// Secret名: api-proxy-hmac-secret
// 形式: 256-bit hex文字列
"a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a1b2c3d4e5f6"
```

**用途**: Unified Auth ServerがAPI Proxy Serverに対して認証する際のHMAC署名生成に使用

**登録コマンド:**
```bash
# 1. HMAC秘密鍵を生成（32バイト = 64文字のhex）
HMAC_SECRET=$(openssl rand -hex 32)
echo "生成されたHMAC秘密鍵: $HMAC_SECRET"

# 2. Unified Auth Server側のSecret Managerに保存
echo -n "$HMAC_SECRET" | gcloud secrets create api-proxy-hmac-secret \
  --data-file=- \
  --project=interview-api-472500 \
  --replication-policy="automatic"

# 3. サービスアカウントに権限付与
gcloud secrets add-iam-policy-binding api-proxy-hmac-secret \
  --member="serviceAccount:856773980753-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=interview-api-472500
```

**重要**: この秘密鍵は、API Proxy Server側でも同じ値を `unified-auth-server-hmac-secret` として登録する必要があります。詳細は [HMAC認証の詳細設計](#-hmac認証の詳細設計api-proxy-server連携) を参照。

#### **4. Google Workspace Admin SDK サービスアカウント（オプション）**
```json
// Secret名: workspace-service-account
// 形式: サービスアカウントのJSON鍵
{
  "type": "service_account",
  "project_id": "YOUR_PROJECT_ID",
  "private_key_id": "...",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "workspace-admin@YOUR_PROJECT.iam.gserviceaccount.com",
  "client_id": "...",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "..."
}
```

**用途**: Google Workspaceのグループメンバーシップや組織部門情報を取得する際に使用（グループ/OU認証を有効にする場合のみ必要）

**登録コマンド:**
```bash
# サービスアカウントJSON鍵ファイルを使用
gcloud secrets create workspace-service-account \
  --data-file=service-account-key.json \
  --project=interview-api-472500
```

#### **5. ユーザー別APIプロキシ認証情報（旧方式 - 非推奨）**
```json
// Secret名: slidevideo-users
// 形式: JSON（ユーザーメールアドレスをキーとした辞書）
{
  "yamada@i-seifu.jp": {
    "client_id": "slidevideo-yamada",
    "client_secret": "SECRET_YAMADA_xxx"
  },
  "tanaka@i-seifu.jp": {
    "client_id": "slidevideo-tanaka",
    "client_secret": "SECRET_TANAKA_xxx"
  }
}
```

**⚠️ 注意**: この方式は旧実装で使用されていましたが、現在は **Unified Auth Server自体のクレデンシャル方式（`api-proxy-hmac-secret`）に移行** しています。新規プロジェクトでは使用しないでください。

### トークンのセキュリティ

#### **JWTトークン構造:**
```json
{
  "email": "yamada@i-seifu.jp",
  "name": "山田太郎",
  "project_id": "slide-video",
  "iat": 1706755200,
  "exp": 1738819200
}
```

#### **セキュリティ対策:**
- ✅ HMAC-SHA256署名
- ✅ 有効期限チェック
- ✅ プロジェクトID検証
- ✅ client_secretは含めない（サーバー側のみ保持）

### Cookie設定（Webアプリ）

```
Set-Cookie: auth_token=eyJhbG...;
  Path=/;
  HttpOnly;           # JavaScriptからアクセス不可
  Secure;             # HTTPS必須
  SameSite=Lax;       # CSRF対策
  Max-Age=604800      # 7日間
```

---

## 📊 データベース設計

### Firestore コレクション構造

#### **projects コレクション**
```
projects/{project_id}
├── name: string
├── type: string
├── allowed_domains: array<string>
├── student_allowed: boolean
├── admin_emails: array<string>
├── required_groups: array<string>
├── allowed_groups: array<string>
├── required_org_units: array<string>
├── allowed_org_units: array<string>
├── redirect_uris: array<string>
├── token_delivery: string
├── token_expiry_days: number
├── api_proxy_enabled: boolean
├── api_proxy_credentials_path: string
├── product_id: string
├── created_at: timestamp
└── updated_at: timestamp
```

#### **audit_logs コレクション（監査ログ）**
```
audit_logs/{log_id}
├── timestamp: timestamp
├── project_id: string
├── user_email: string
├── event_type: string  # login_success, login_failed, api_call, etc.
├── ip_address: string
├── user_agent: string
└── details: map
```

---

## 🚀 実装フェーズ

### Phase 1: 基本認証機能（2-3日）

**実装内容:**
- ✅ Google OAuth統合
- ✅ プロジェクト設定管理
- ✅ トークン発行機能
- ✅ `/login/{project_id}` エンドポイント
- ✅ `/callback/{project_id}` エンドポイント
- ✅ `/api/verify` エンドポイント

**成果物:**
- ✅ Google OAuth認証が動作
- ✅ JWTトークン発行
- ✅ クライアント側のGoogle OAuth client_secretが不要に

**検証方法:**
1. ローカルでFlaskアプリ起動
2. `/login/test-project` にアクセス
3. Google認証完了後、トークンが返却されることを確認

---

### Phase 2: APIプロキシ統合（1-2日）

**実装内容:**
- ✅ `/api/proxy` エンドポイント実装
- ✅ client_secret管理機能
- ✅ HMAC署名生成
- ✅ APIプロキシサーバーへの転送

**成果物:**
- ✅ 全ての機密情報がクライアント側から削除
- ✅ API呼び出しも認証サーバー経由

**検証方法:**
1. トークンを取得
2. `/api/proxy` にリクエスト
3. APIプロキシサーバー経由でOpenAI APIが呼び出されることを確認

---

### Phase 3: 監査ログ・管理機能（オプション）

**実装内容:**
- ✅ ログイン履歴の記録
- ✅ API呼び出し履歴の記録
- ✅ 管理画面（プロジェクト設定のGUI）

---

## 🧪 テスト計画

### 単体テスト

```python
# test_auth.py

def test_domain_validation():
    """ドメイン検証のテスト"""
    assert validate_email("yamada@i-seifu.jp") == (True, None)
    assert validate_email("user@gmail.com") == (False, "Invalid domain")

def test_student_check():
    """学生アカウントチェックのテスト"""
    assert is_student_account("12345678@i-seifu.jp") == True
    assert is_student_account("yamada@i-seifu.jp") == False

def test_token_generation():
    """トークン生成のテスト"""
    token = generate_jwt_token("yamada@i-seifu.jp", "slide-video")
    payload = verify_jwt_token(token)
    assert payload["email"] == "yamada@i-seifu.jp"
    assert payload["project_id"] == "slide-video"
```

### 統合テスト

```python
# test_integration.py

def test_login_flow():
    """ログインフロー全体のテスト"""
    # 1. /login にアクセス
    response = client.get("/login/test-project")
    assert response.status_code == 302

    # 2. Google OAuth（モック）
    # 3. /callback にコールバック
    # 4. トークンが返却されることを確認

def test_api_proxy():
    """APIプロキシのテスト"""
    # 1. トークン取得
    # 2. /api/proxy にリクエスト
    # 3. APIプロキシサーバーが呼び出されることを確認
```

---

## 🔧 環境変数

```bash
# 開発環境
GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxx
JWT_SECRET_KEY=your-secret-key
ENVIRONMENT=development

# 本番環境（Secret Managerから取得）
GCP_PROJECT_ID=your-project-id
SECRET_MANAGER_ENABLED=true
```

---

## 📝 エラーハンドリング

### エラーコード一覧

| コード | エラー | 説明 |
|-------|-------|------|
| `AUTH_001` | Invalid domain | 許可されていないドメイン |
| `AUTH_002` | Student not allowed | 学生アカウント不可 |
| `AUTH_003` | Admin only | 管理者専用 |
| `AUTH_004` | Invalid token | トークンが無効 |
| `AUTH_005` | Token expired | トークン期限切れ |
| `AUTH_006` | Project not found | プロジェクトIDが見つからない |
| `AUTH_007` | Group membership required | 必須グループに未所属 |
| `AUTH_008` | No matching group | 許可グループのいずれにも未所属 |
| `AUTH_009` | Org unit membership required | 必須組織部門に未所属 |
| `AUTH_010` | No matching org unit | 許可組織部門のいずれにも未所属 |
| `PROXY_001` | Client secret not found | client_secretが見つからない |
| `PROXY_002` | API proxy failed | APIプロキシ呼び出し失敗 |

---

## 🔄 今後の拡張

### 機能拡張案

1. **シングルサインオン（SSO）**
   - 一度ログインすれば複数プロジェクトで有効

2. **トークンリフレッシュ**
   - 期限切れ時に自動更新

3. **2要素認証（2FA）**
   - より強固なセキュリティ

4. **ログイン履歴表示**
   - ユーザーが自分のログイン履歴を確認

5. **管理画面**
   - プロジェクト設定のGUI管理
   - ユーザー管理
   - 監査ログ閲覧

---

## 📚 関連ドキュメント

- [API仕様書](auth_server_api.yaml) - OpenAPI 3.0形式
- [README](README.md) - プロジェクト概要とセットアップ
- [APIプロキシサーバー](C:\Users\濱田英樹\Documents\dev\api-key-server\api-key-server) - 連携先
- [クライアント（スライド動画生成）](C:\Users\濱田英樹\Documents\dev\SlideMovie\sogo-slide-local-video) - クライアント実装例

---

## 🤝 貢献者

- 開発: 情政府高校 IT部門
- 設計: Claude Code

---

## 📄 ライセンス

（プロジェクトのライセンスを記載）

---

## 🔐 HMAC認証の詳細設計（API Proxy Server連携）

### 概要

Unified Auth ServerとAPI Proxy Server間の通信は、HMAC-SHA256署名による認証で保護されています。

### 認証フロー

```
[Unified Auth Server] → [API Proxy Server] → [外部API (Anthropic/OpenAI)]
     HMAC署名付き           署名検証           APIキー付き
```

### HMAC署名の生成アルゴリズム

#### **署名生成（Unified Auth Server側）**

実装場所: [app/core/hmac_signer.py](../app/core/hmac_signer.py)

```python
def generate_signature(client_secret: str, timestamp: str, method: str, path: str, body: dict) -> str:
    """
    HMAC-SHA256署名を生成

    重要: API Proxy Serverと完全に一致する必要がある
    """
    # 1. リクエストボディをJSON化（重要: separators=(',', ':') でスペースなし）
    body_json = json.dumps(body, sort_keys=True, separators=(',', ':'))

    # 2. ボディのSHA256ハッシュを計算
    body_hash = hashlib.sha256(body_json.encode('utf-8')).hexdigest()

    # 3. 署名対象文字列を作成（重要: method.upper() で大文字化）
    signature_string = f"{timestamp}\n{method.upper()}\n{path}\n{body_hash}"

    # 4. HMAC-SHA256署名を計算
    mac = hmac.new(
        client_secret.encode('utf-8'),
        signature_string.encode('utf-8'),
        hashlib.sha256
    )

    return mac.hexdigest()
```

#### **署名検証（API Proxy Server側）**

実装場所: `api-key-server/app/auth.py`

```python
def _calculate_hmac_signature(secret: str, timestamp: str, method: str, path: str, body: bytes) -> str:
    """
    HMAC-SHA256署名を計算（検証用）

    Unified Auth Serverの生成ロジックと完全一致が必須
    """
    # 1. ボディのSHA256ハッシュを計算（受信したbytesから）
    body_hash = hashlib.sha256(body).hexdigest()

    # 2. 署名対象文字列を作成（method.upper() で大文字化）
    message = f"{timestamp}\n{method.upper()}\n{path}\n{body_hash}"

    # 3. HMAC-SHA256署名を計算
    mac = hmac.new(secret.encode('utf-8'), message.encode('utf-8'), hashlib.sha256)

    return mac.hexdigest()
```

### 重要な実装ポイント

#### **1. JSONシリアライゼーションの統一**

**問題**:
- Pythonの`json.dumps()`はデフォルトで`separators=(', ', ': ')`（スペース付き）
- `httpx.post(json=data)`も内部で`json.dumps()`を使用するため、スペース付きになる
- 署名生成時とリクエスト送信時でJSON形式が異なると、署名が一致しない

**解決策**:
```python
# app/routes/proxy.py

# HMAC署名生成（スペースなし）
body_json = json.dumps(proxy_req.data, sort_keys=True, separators=(',', ':'))
signature = generate_signature(client_secret, timestamp, "POST", path, proxy_req.data)

# リクエスト送信（同じJSON形式を使用）
body_json = json.dumps(proxy_req.data, sort_keys=True, separators=(',', ':'))
response = await client.post(
    full_url,
    headers=headers,
    content=body_json  # jsonパラメータではなくcontentとして送信
)
```

**修正履歴**:
- コミット: `685990f` (2025-12-23)
- 問題: HMAC署名とリクエストbodyのJSON形式不一致
- 修正: `separators=(',', ':')`で統一、`content=body_json`で送信

#### **2. HTTPメソッドの大文字化**

**問題**:
- API Proxy Serverは`method.upper()`で大文字化して署名を検証
- Unified Auth Serverが小文字で署名を生成すると、署名が一致しない

**解決策**:
```python
# 修正前（誤り）
signature_string = f"{timestamp}\n{method}\n{path}\n{body_hash}"

# 修正後（正しい）
signature_string = f"{timestamp}\n{method.upper()}\n{path}\n{body_hash}"
```

**修正履歴**:
- コミット: `95eb568` (2025-12-16)
- 問題: HTTPメソッドが小文字のまま
- 修正: `method.upper()`で大文字化

#### **3. Unified Auth Server自体の認証**

**問題**:
- 初期実装では、ユーザーごとのクレデンシャルを使用していた
- API Proxy ServerはUnified Auth Server自体を認証する必要がある

**解決策**:
```python
# app/routes/proxy.py

# 修正前（誤り）: ユーザーごとのクレデンシャル
credentials = await secret_manager_client.get_api_proxy_credentials_async(email, project_id)
client_id = credentials.get("client_id")
client_secret = credentials.get("client_secret")

# 修正後（正しい）: Unified Auth Server自体のクレデンシャル
client_id = settings.api_proxy_client_id  # "unified-auth-server"
client_secret = settings.api_proxy_hmac_secret  # Secret Managerから取得
```

**修正履歴**:
- コミット: `e0aa82f` (2025-12-23)
- 問題: 401 Unknown client エラー
- 修正: Unified Auth Server自体のクレデンシャルを使用

### 環境変数とSecret Manager設定

#### **環境変数（.env.production）**

```bash
# API Proxy Server設定
API_PROXY_SERVER_URL=https://api-key-server-856773980753.asia-northeast1.run.app
API_PROXY_CLIENT_ID=unified-auth-server
# API_PROXY_HMAC_SECRET は Secret Manager経由で管理（環境変数では設定しない）
```

#### **Secret Manager**

| Secret名 | 説明 | 使用箇所 |
|---------|------|---------|
| `api-proxy-hmac-secret` | Unified Auth ServerのHMAC秘密鍵 | Unified Auth Server |
| `unified-auth-server-hmac-secret` | 同じ値（API Proxy Server側の名前） | API Proxy Server |

**重要**: 両サーバーで同じ秘密鍵を共有する必要があります。

#### **Secret Managerへの登録手順**

```bash
# 1. HMAC秘密鍵を生成（32バイト）
SECRET_VALUE=$(openssl rand -hex 32)
echo "生成されたHMAC秘密鍵: $SECRET_VALUE"

# 2. Unified Auth Server側のSecret Managerに保存
echo -n "$SECRET_VALUE" | gcloud secrets create api-proxy-hmac-secret \
  --data-file=- \
  --project=interview-api-472500 \
  --replication-policy="automatic"

# 3. API Proxy Server側のSecret Managerに保存（同じ値）
echo -n "$SECRET_VALUE" | gcloud secrets create unified-auth-server-hmac-secret \
  --data-file=- \
  --project=interview-api-472500 \
  --replication-policy="automatic"

# 4. サービスアカウントに権限付与
gcloud secrets add-iam-policy-binding api-proxy-hmac-secret \
  --member="serviceAccount:856773980753-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=interview-api-472500

gcloud secrets add-iam-policy-binding unified-auth-server-hmac-secret \
  --member="serviceAccount:856773980753-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=interview-api-472500
```

### API Proxy Serverとのリクエストフォーマット

#### **リクエスト例**

```http
POST https://api-key-server-856773980753.asia-northeast1.run.app/v1/chat/product-SlideVideo
Content-Type: application/json
X-Client-ID: unified-auth-server
X-Timestamp: 1703001234
X-Signature: a1b2c3d4e5f6...

{"model":"claude-3-sonnet","messages":[{"role":"user","content":"Hello"}]}
```

#### **ヘッダー詳細**

| ヘッダー | 説明 | 例 |
|---------|------|-----|
| `Content-Type` | 常に `application/json` | `application/json` |
| `X-Client-ID` | Unified Auth ServerのクライアントID | `unified-auth-server` |
| `X-Timestamp` | Unix timestamp（秒） | `1703001234` |
| `X-Signature` | HMAC-SHA256署名（16進数） | `a1b2c3d4e5f6...` |

#### **URL構造**

```
{API_PROXY_SERVER_URL}/v1/chat/{product_id}
```

- `API_PROXY_SERVER_URL`: 環境変数で設定
- `product_id`: プロジェクト設定の`product_id`から取得
  - 例: `product-SlideVideo`, `product-textbook-translation`

### エラーハンドリング

#### **HMAC認証関連のエラー**

| エラーコード | HTTPステータス | 説明 | 原因 |
|------------|--------------|------|------|
| `Unknown client` | 401 | クライアントIDが登録されていない | API Proxy ServerにClient IDが未登録 |
| `Signature mismatch` | 401 | HMAC署名が一致しない | JSON形式の不一致、メソッド大文字化忘れ、秘密鍵の不一致 |
| `Timestamp expired` | 401 | タイムスタンプが古い | リクエストが遅延、サーバー時刻のずれ |
| `PROXY_AUTH_001` | 500 | HMAC秘密鍵が設定されていない | 環境変数またはSecret Managerに秘密鍵がない |

#### **デバッグ方法**

```bash
# Unified Auth Serverのログ確認
gcloud run services logs read unified-auth-server \
  --region=asia-northeast1 \
  --limit=30

# API Proxy Serverのログ確認
gcloud run services logs read api-key-server \
  --region=asia-northeast1 \
  --limit=30

# Secret Managerの値確認
gcloud secrets versions access latest \
  --secret=api-proxy-hmac-secret \
  --project=interview-api-472500
```

### トラブルシューティング

#### **問題1: Signature mismatch**

**原因**:
- JSONシリアライゼーションの不一致（スペースの有無）
- HTTPメソッドの大文字化忘れ
- HMAC秘密鍵が両サーバーで異なる

**確認手順**:
```python
# デバッグログを追加（本番環境では削除）
logger.debug(f"Body JSON: {body_json}")
logger.debug(f"Body hash: {body_hash}")
logger.debug(f"Signature string: {signature_string}")
logger.debug(f"Generated signature: {signature}")
```

**解決策**:
1. `separators=(',', ':')`を使用
2. `method.upper()`で大文字化
3. 両サーバーで同じ秘密鍵を使用

#### **問題2: Unknown client**

**原因**:
- API Proxy ServerにClient ID `unified-auth-server`が登録されていない

**解決策**:
API Proxy Server側で以下を実施:
```python
# app/config.py または clients.py
REGISTERED_CLIENTS = {
    "unified-auth-server": {
        "name": "Unified Auth Server",
        "hmac_secret_path": "projects/interview-api-472500/secrets/unified-auth-server-hmac-secret/versions/latest",
        "allowed_products": ["product-SlideVideo", "product-textbook-translation"],
        "description": "Unified authentication server for all products"
    }
}
```

### テスト方法

#### **ローカルテスト**

```python
# tests/test_hmac_signer.py

def test_hmac_signature_matches_api_proxy():
    """HMAC署名がAPI Proxy Serverの検証ロジックと一致することを確認"""
    client_secret = "test-secret"
    timestamp = "1234567890"
    method = "post"  # 小文字で渡す
    path = "/v1/chat/product-SlideVideo"
    body = {"model": "claude-3-sonnet", "messages": [{"role": "user", "content": "test"}]}

    # Unified Auth Server側の署名生成
    auth_signature = HMACSignatureGenerator.generate_signature(
        client_secret=client_secret,
        timestamp=timestamp,
        method=method,
        path=path,
        body=body
    )

    # API Proxy Server側の検証ロジックを再現
    body_json = json.dumps(body, sort_keys=True, separators=(',', ':'))
    body_hash = hashlib.sha256(body_json.encode()).hexdigest()
    message = f"{timestamp}\n{method.upper()}\n{path}\n{body_hash}"
    api_proxy_signature = hmac.new(
        client_secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    # 署名が一致することを確認
    assert auth_signature == api_proxy_signature
```

#### **統合テスト（本番環境）**

1. Streamlitアプリにログイン
2. スライド生成機能を実行
3. ログで確認:
   ```
   # 成功時のログ
   [Unified Auth Server] API proxy request successful for h.hamada@i-seifu.jp
   [API Proxy Server] Client unified-auth-server authenticated
   [API Proxy Server] Forwarding to Claude API
   ```

### 変更履歴

| 日付 | コミット | 説明 |
|------|---------|------|
| 2025-12-16 | `95eb568` | HTTPメソッドを大文字化（method.upper()） |
| 2025-12-23 | `685990f` | JSONシリアライゼーション統一（separators=(',', ':')） |
| 2025-12-23 | `e0aa82f` | Unified Auth Server自体のクレデンシャルを使用 |

---
