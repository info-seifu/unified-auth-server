# 統合認証サーバー 連携ガイド

> このドキュメントは、新規プロダクト（Streamlitアプリ、Webアプリ等）を統合認証サーバーに接続するための手順書です。

---

## 📋 目次

1. [概要](#概要)
2. [システム構成](#システム構成)
3. [接続手順（クイックスタート）](#接続手順クイックスタート)
4. [プロジェクト登録](#プロジェクト登録)
5. [クライアント側実装](#クライアント側実装)
6. [APIエンドポイント一覧](#apiエンドポイント一覧)
7. [認証フロー詳細](#認証フロー詳細)
8. [アクセス制御オプション](#アクセス制御オプション)
9. [APIプロキシ機能](#apiプロキシ機能)
10. [トラブルシューティング](#トラブルシューティング)
11. [サンプルコード](#サンプルコード)

---

## 概要

### 統合認証サーバーとは

統合認証サーバーは、複数のアプリケーションで共通して使用できる認証基盤です。

**主な機能:**
- Google OAuth 2.0 による統一認証
- プロジェクト別のアクセス制御
- JWT トークンの発行・検証
- API プロキシ機能（外部 API キーの秘匿化）

**メリット:**
- 各アプリで OAuth 設定が不要
- 機密情報（client_secret、API キー）をクライアント側に置かない
- 統一されたユーザー管理・監査ログ

### 対応クライアント種別

| 種別 | 説明 | トークン受け取り方法 |
|------|------|---------------------|
| Streamlit（ローカル） | ローカル開発環境 | URL パラメータ |
| Streamlit（Cloud Run） | 本番環境 | URL パラメータ |
| Web アプリ | Flask/React 等 | HttpOnly Cookie |
| API サービス | FastAPI 等 | HttpOnly Cookie |

---

## システム構成

```
┌─────────────────────────────────────────────────────────────┐
│                    あなたのアプリケーション                    │
│              （Streamlit / Web / API サービス）               │
└─────────────────────────────────────────────────────────────┘
                         ↓ ↑
              ① 認証リクエスト / ⑤ トークン受信
                         ↓ ↑
┌─────────────────────────────────────────────────────────────┐
│                    統合認証サーバー                           │
│                                                             │
│  エンドポイント:                                              │
│  • /login/{project_id}     - ログイン開始                    │
│  • /callback/{project_id}  - OAuth コールバック              │
│  • /api/verify             - トークン検証                    │
│  • /api/refresh            - トークン更新                    │
│  • /api/proxy              - API プロキシ（オプション）       │
│  • /logout                 - ログアウト                      │
└─────────────────────────────────────────────────────────────┘
                         ↓ ↑
              ② Google OAuth / ③ ユーザー情報取得
                         ↓ ↑
┌─────────────────────────────────────────────────────────────┐
│                    Google OAuth 2.0                          │
│                  （Google Workspace 連携）                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 接続手順（クイックスタート）

### Step 1: プロジェクト登録

認証サーバー管理者に以下の情報を伝えてプロジェクトを登録してもらいます：

```yaml
# 必須項目
project_id: "your-project-id"        # 一意のプロジェクトID（英数字とハイフン）
name: "あなたのアプリ名"              # 表示名
allowed_domains:                      # 許可するメールドメイン
  - "i-seifu.jp"
  - "i-seifu.ac.jp"
redirect_uris:                        # 認証後のリダイレクト先
  - "http://localhost:8501/"          # 開発環境
  - "https://your-app.example.com/"   # 本番環境

# オプション
student_allowed: false                # 学生アカウントを許可するか
token_expiry_days: 30                 # トークン有効期限（日数）
```

### Step 2: クライアント側設定

アプリケーションに以下の設定を追加：

```python
# 設定値
AUTH_SERVER_URL = "https://auth.example.com"  # 認証サーバーURL
PROJECT_ID = "your-project-id"                 # 登録したプロジェクトID
```

### Step 3: 認証フローの実装

```python
# 1. 未認証時にログインURLにリダイレクト
login_url = f"{AUTH_SERVER_URL}/login/{PROJECT_ID}"

# 2. 認証後、トークンを受け取って保存
token = request.args.get("token")

# 3. API呼び出し時にトークンを使用
headers = {"Authorization": f"Bearer {token}"}
```

---

## プロジェクト登録

### 設定項目一覧

| 項目 | 必須 | 説明 | 例 |
|------|------|------|-----|
| `project_id` | ✅ | 一意の識別子 | `"slide-video"` |
| `name` | ✅ | プロジェクト名 | `"スライド動画生成"` |
| `type` | ✅ | クライアント種別 | `"streamlit_local"` |
| `allowed_domains` | ✅ | 許可ドメイン | `["i-seifu.jp"]` |
| `redirect_uris` | ✅ | リダイレクト先 | `["http://localhost:8501/"]` |
| `token_delivery` | ✅ | トークン返却方法 | `"query_param"` or `"cookie"` |
| `student_allowed` | - | 学生許可 | `false` |
| `admin_emails` | - | 管理者限定 | `["admin@i-seifu.jp"]` |
| `allowed_groups` | - | 許可グループ | `["staff@i-seifu.jp"]` |
| `allowed_org_units` | - | 許可組織部門 | `["/教職員"]` |
| `token_expiry_days` | - | 有効期限 | `30` |
| `api_proxy_enabled` | - | APIプロキシ使用 | `true` |
| `product_id` | - | APIプロキシ用ID | `"product-SlideVideo"` |

### プロジェクト種別（type）

| type | 用途 | トークン返却 |
|------|------|-------------|
| `streamlit_local` | Streamlit開発環境 | URL パラメータ |
| `streamlit_cloud` | Streamlit本番環境 | URL パラメータ |
| `web_app` | Webアプリ（Flask/React） | HttpOnly Cookie |
| `api_service` | APIサービス | HttpOnly Cookie |

### 登録例

#### 例1: Streamlit アプリ（教職員専用）

```python
{
    "project_id": "my-streamlit-app",
    "name": "マイStreamlitアプリ",
    "type": "streamlit_local",
    "allowed_domains": ["i-seifu.jp", "i-seifu.ac.jp"],
    "student_allowed": False,
    "redirect_uris": [
        "http://localhost:8501/",
        "https://my-app.run.app/"
    ],
    "token_delivery": "query_param",
    "token_expiry_days": 30,
    "api_proxy_enabled": False
}
```

#### 例2: Web アプリ（特定グループのみ）

```python
{
    "project_id": "staff-portal",
    "name": "職員ポータル",
    "type": "web_app",
    "allowed_domains": ["i-seifu.jp"],
    "student_allowed": False,
    "allowed_groups": ["staff@i-seifu.jp"],
    "redirect_uris": [
        "http://localhost:3000/callback",
        "https://portal.example.com/callback"
    ],
    "token_delivery": "cookie",
    "token_expiry_days": 7
}
```

---

## クライアント側実装

### Streamlit アプリの場合

```python
import streamlit as st
import requests
from urllib.parse import urlencode

# 設定
AUTH_SERVER_URL = "https://auth.example.com"
PROJECT_ID = "your-project-id"

def check_authentication():
    """認証状態をチェックし、未認証ならログインページへリダイレクト"""

    # URLパラメータからトークンを取得
    query_params = st.query_params

    if "token" in query_params:
        # トークンを検証してセッションに保存
        token = query_params["token"]
        user_info = verify_token(token)

        if user_info:
            st.session_state["token"] = token
            st.session_state["user"] = user_info
            # URLパラメータをクリア
            st.query_params.clear()
            return True

    # セッションにトークンがあるか確認
    if "token" in st.session_state:
        return True

    # 未認証の場合、ログインボタンを表示
    st.title("ログインが必要です")

    login_url = f"{AUTH_SERVER_URL}/login/{PROJECT_ID}"
    st.markdown(f"[Googleアカウントでログイン]({login_url})")

    return False

def verify_token(token: str) -> dict:
    """トークンを検証してユーザー情報を取得"""
    try:
        response = requests.get(
            f"{AUTH_SERVER_URL}/api/verify",
            params={"token": token},
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.error(f"認証エラー: {str(e)}")
    return None

def logout():
    """ログアウト処理"""
    if "token" in st.session_state:
        del st.session_state["token"]
    if "user" in st.session_state:
        del st.session_state["user"]
    st.rerun()

# メインアプリ
def main():
    if not check_authentication():
        st.stop()

    # 認証済みユーザーの情報を表示
    user = st.session_state["user"]
    st.sidebar.write(f"ログイン中: {user['name']}")
    st.sidebar.write(f"Email: {user['email']}")

    if st.sidebar.button("ログアウト"):
        logout()

    # ここからメインコンテンツ
    st.title("マイアプリ")
    st.write("認証されました！")

if __name__ == "__main__":
    main()
```

### Web アプリ（Flask）の場合

```python
from flask import Flask, redirect, request, session, jsonify
import requests

app = Flask(__name__)
app.secret_key = "your-secret-key"

AUTH_SERVER_URL = "https://auth.example.com"
PROJECT_ID = "your-project-id"

@app.route("/")
def index():
    """メインページ"""
    if "user" not in session:
        return redirect(f"{AUTH_SERVER_URL}/login/{PROJECT_ID}")

    return f"ようこそ、{session['user']['name']}さん！"

@app.route("/callback")
def callback():
    """認証コールバック"""
    # Cookie からトークンを取得（token_delivery: cookie の場合）
    token = request.cookies.get("auth_token")

    # または URL パラメータから（token_delivery: query_param の場合）
    if not token:
        token = request.args.get("token")

    if not token:
        return "認証エラー", 401

    # トークンを検証
    response = requests.get(
        f"{AUTH_SERVER_URL}/api/verify",
        params={"token": token}
    )

    if response.status_code == 200:
        session["user"] = response.json()
        session["token"] = token
        return redirect("/")

    return "認証に失敗しました", 401

@app.route("/logout")
def logout():
    """ログアウト"""
    session.clear()
    return redirect(f"{AUTH_SERVER_URL}/logout?return_url={request.host_url}")

if __name__ == "__main__":
    app.run(port=3000, debug=True)
```

### React アプリの場合

```javascript
// auth.js
const AUTH_SERVER_URL = "https://auth.example.com";
const PROJECT_ID = "your-project-id";

// ログインURLを取得
export const getLoginUrl = (returnUrl) => {
  const params = new URLSearchParams({
    redirect_uri: returnUrl || window.location.origin + "/callback",
  });
  return `${AUTH_SERVER_URL}/login/${PROJECT_ID}?${params}`;
};

// トークンを検証
export const verifyToken = async (token) => {
  const response = await fetch(`${AUTH_SERVER_URL}/api/verify?token=${token}`);
  if (response.ok) {
    return await response.json();
  }
  throw new Error("Token verification failed");
};

// コールバックコンポーネント
export const AuthCallback = () => {
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");

    if (token) {
      verifyToken(token)
        .then((user) => {
          localStorage.setItem("token", token);
          localStorage.setItem("user", JSON.stringify(user));
          window.location.href = "/";
        })
        .catch((error) => {
          console.error("Auth error:", error);
          window.location.href = "/login";
        });
    }
  }, []);

  return <div>認証中...</div>;
};
```

---

## APIエンドポイント一覧

### 認証エンドポイント

#### `GET /login/{project_id}`

**説明:** ログインフローを開始します。Google OAuth 画面にリダイレクトされます。

**パラメータ:**
| パラメータ | 種別 | 必須 | 説明 |
|-----------|------|------|------|
| `project_id` | path | ✅ | プロジェクトID |
| `redirect_uri` | query | - | カスタムリダイレクト先 |
| `state` | query | - | クライアント側の状態保持用 |

**使用例:**
```
GET https://auth.example.com/login/my-project
GET https://auth.example.com/login/my-project?redirect_uri=http://localhost:8501/
```

---

#### `GET /callback/{project_id}`

**説明:** Google OAuth のコールバックを処理します（内部使用）。

---

#### `GET /api/verify`

**説明:** JWT トークンを検証し、ユーザー情報を返します。

**パラメータ:**
| パラメータ | 種別 | 必須 | 説明 |
|-----------|------|------|------|
| `token` | query | ※ | JWT トークン |
| `Authorization` | header | ※ | `Bearer {token}` 形式 |

※ いずれか一方が必須

**レスポンス（成功時）:**
```json
{
  "email": "user@i-seifu.jp",
  "name": "山田太郎",
  "project_id": "my-project",
  "exp": 1738819200,
  "valid": true
}
```

**レスポンス（失敗時）:**
```json
{
  "error": "AUTH_004",
  "detail": "Token has expired",
  "message": "Invalid token"
}
```

**使用例:**
```python
# クエリパラメータで渡す場合
response = requests.get(
    "https://auth.example.com/api/verify",
    params={"token": "eyJhbG..."}
)

# Authorizationヘッダーで渡す場合
response = requests.get(
    "https://auth.example.com/api/verify",
    headers={"Authorization": f"Bearer eyJhbG..."}
)
```

---

#### `POST /api/refresh`

**説明:** トークンを更新し、新しいトークンを発行します。

**パラメータ:**
| パラメータ | 種別 | 必須 | 説明 |
|-----------|------|------|------|
| `token` | query | ※ | 現在のJWTトークン |
| `Authorization` | header | ※ | `Bearer {token}` 形式 |
| `expiry_days` | query | - | 新しい有効期限（日数） |

**レスポンス（成功時）:**
```json
{
  "token": "eyJhbG...(新しいトークン)",
  "expiry": "2025-02-06T12:00:00+00:00"
}
```

---

#### `GET /logout`

**説明:** ログアウトし、指定されたURLにリダイレクトします。

**パラメータ:**
| パラメータ | 種別 | 必須 | 説明 |
|-----------|------|------|------|
| `return_url` | query | - | ログアウト後のリダイレクト先 |

---

### APIプロキシエンドポイント

#### `POST /api/proxy`

**説明:** 外部 API への呼び出しを中継します（API キーを秘匿化）。

**ヘッダー:**
| ヘッダー | 必須 | 説明 |
|---------|------|------|
| `Authorization` | ✅ | `Bearer {token}` 形式 |
| `Content-Type` | ✅ | `application/json` |

**リクエストボディ:**
```json
{
  "endpoint": "/api/openai/images/generate",
  "method": "POST",
  "data": {
    "prompt": "A beautiful landscape",
    "size": "1024x1024"
  }
}
```

**レスポンス:** 外部 API のレスポンスがそのまま返されます。

---

### 監査ログエンドポイント

#### `GET /api/audit/logs`

**説明:** 監査ログを取得します（管理者用）。

---

### ヘルスチェック

#### `GET /health`

**説明:** サーバーの稼働状態を確認します。

**レスポンス:**
```json
{
  "status": "healthy",
  "environment": "production",
  "debug": false
}
```

---

## 認証フロー詳細

### フロー図

```
[ユーザー] → [あなたのアプリ] → [認証サーバー] → [Google] → [認証サーバー] → [あなたのアプリ]
    │              │                  │              │              │              │
    │   (1) アクセス                                                              │
    │──────────────>                                                              │
    │              │                                                              │
    │              │   (2) 未認証検出                                              │
    │              │   ログインURLにリダイレクト                                    │
    │<─────────────────────────────────>                                          │
    │                                  │                                          │
    │   (3) /login/{project_id}        │                                          │
    │─────────────────────────────────>│                                          │
    │                                  │                                          │
    │                                  │   (4) Google OAuth開始                   │
    │                                  │─────────────────────────────>            │
    │                                                                 │            │
    │   (5) Googleログイン画面         │                              │            │
    │<────────────────────────────────────────────────────────────────│            │
    │                                                                 │            │
    │   (6) ユーザーがログイン         │                              │            │
    │─────────────────────────────────────────────────────────────────>            │
    │                                                                 │            │
    │                                  │   (7) 認証コード             │            │
    │                                  │<─────────────────────────────│            │
    │                                  │                                          │
    │                                  │   (8) ユーザー検証                        │
    │                                  │   • ドメインチェック                      │
    │                                  │   • 学生チェック                          │
    │                                  │   • グループチェック                      │
    │                                  │   • OUチェック                            │
    │                                  │                                          │
    │                                  │   (9) JWTトークン発行                     │
    │                                  │                                          │
    │                                  │   (10) リダイレクト                       │
    │                                  │──────────────────────────────────────────>│
    │                                                                              │
    │   (11) トークン付きでリダイレクト                                            │
    │<─────────────────────────────────────────────────────────────────────────────│
    │              │                                                              │
    │              │   (12) トークン保存                                          │
    │              │   セッションに保存                                            │
    │              │                                                              │
    │   (13) メインコンテンツ表示                                                  │
    │<─────────────│                                                              │
```

### トークン返却方法

#### URL パラメータ（Streamlit 向け）

```
http://localhost:8501/?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

#### HttpOnly Cookie（Web アプリ向け）

```
Set-Cookie: auth_token=eyJhbG...; HttpOnly; Secure; SameSite=Lax; Max-Age=2592000
```

---

## アクセス制御オプション

### ドメイン制限

特定のメールドメインのユーザーのみ許可：

```python
"allowed_domains": ["i-seifu.jp", "i-seifu.ac.jp"]
```

### 学生制限

学生アカウント（8桁数字@domain）を制限：

```python
"student_allowed": False  # 教職員のみ
"student_allowed": True   # 学生も許可
```

### 管理者限定

特定のメールアドレスのみ許可：

```python
"admin_emails": ["admin@i-seifu.jp", "principal@i-seifu.jp"]
```

### グループベース認証

Google Workspace グループによる制御：

```python
# いずれかのグループに所属していれば許可（OR条件）
"allowed_groups": ["teachers@i-seifu.jp", "staff@i-seifu.jp"]

# 全てのグループに所属している必要がある（AND条件）
"required_groups": ["security-team@i-seifu.jp", "approved-users@i-seifu.jp"]
```

**注意:** グループ認証では、ネストされたグループ（グループの中にあるグループ）も自動的に検出されます。

### 組織部門（OU）ベース認証

Google Workspace の組織部門による制御：

```python
# いずれかのOUに所属していれば許可（OR条件）
"allowed_org_units": ["/教職員", "/管理部門"]

# 全てのOUに所属している必要がある（AND条件）
"required_org_units": ["/教職員/専任教員"]
```

**階層的な検証:** `/教職員` を許可した場合、`/教職員/専任教員` や `/教職員/非常勤講師` も自動的に許可されます。

### 検証の優先順位

1. ドメイン検証（`allowed_domains`）
2. 学生アカウントチェック（`student_allowed`）
3. 管理者限定チェック（`admin_emails`）
4. 必須グループチェック（`required_groups`）
5. 許可グループチェック（`allowed_groups`）
6. 必須組織部門チェック（`required_org_units`）
7. 許可組織部門チェック（`allowed_org_units`）

---

## APIプロキシ機能

### 概要

APIプロキシ機能を使用すると、OpenAI や Anthropic などの外部 API を、API キーを秘匿化したまま呼び出すことができます。

### 設定

プロジェクト登録時に以下を設定：

```python
{
    "api_proxy_enabled": True,
    "product_id": "product-YourApp"
}
```

### 使用方法

```python
import requests

def call_openai_api(prompt: str, token: str) -> dict:
    """OpenAI APIを認証サーバー経由で呼び出す"""
    response = requests.post(
        f"{AUTH_SERVER_URL}/api/proxy",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json={
            "endpoint": "/api/openai/chat/completions",
            "data": {
                "model": "gpt-4",
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
        }
    )
    return response.json()

def call_anthropic_api(prompt: str, token: str) -> dict:
    """Anthropic APIを認証サーバー経由で呼び出す"""
    response = requests.post(
        f"{AUTH_SERVER_URL}/api/proxy",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json={
            "endpoint": "/api/anthropic/messages",
            "data": {
                "model": "claude-3-5-sonnet-20241022",
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 4096
            }
        }
    )
    return response.json()
```

### 対応エンドポイント

| エンドポイント | 説明 |
|---------------|------|
| `/api/openai/chat/completions` | OpenAI Chat API |
| `/api/openai/images/generate` | OpenAI Image Generation |
| `/api/anthropic/messages` | Anthropic Claude API |
| `/api/gemini/generateContent` | Google Gemini API |

---

## トラブルシューティング

### エラーコード一覧

| コード | エラー | 原因 | 対処法 |
|-------|-------|------|--------|
| `AUTH_001` | Invalid domain | 許可されていないドメイン | `allowed_domains` を確認 |
| `AUTH_002` | Student not allowed | 学生アカウント不可 | `student_allowed: true` に変更 |
| `AUTH_003` | Admin only | 管理者専用 | `admin_emails` に追加 |
| `AUTH_004` | Invalid token | トークンが無効 | 再ログイン |
| `AUTH_005` | Token expired | トークン期限切れ | `/api/refresh` で更新 |
| `AUTH_006` | Project not found | プロジェクトID不正 | プロジェクト登録を確認 |
| `AUTH_007` | Group membership required | 必須グループに未所属 | グループに追加 |
| `AUTH_008` | No matching group | 許可グループに未所属 | グループに追加 |
| `AUTH_009` | Org unit required | 必須OUに未所属 | 組織部門を確認 |
| `AUTH_010` | No matching org unit | 許可OUに未所属 | 組織部門を確認 |

### よくある問題

#### 1. リダイレクト後にトークンが取得できない

**原因:** `redirect_uris` の設定が正しくない

**確認事項:**
- 末尾のスラッシュ有無（`http://localhost:8501/` vs `http://localhost:8501`）
- プロトコル（`http` vs `https`）
- ポート番号

#### 2. グループ認証が通らない

**原因:** ネストされたグループの問題、または権限不足

**確認事項:**
- Google Admin Console でグループのメンバーシップを確認
- 認証サーバーのログで取得されたグループリストを確認

#### 3. トークン検証が失敗する

**原因:** トークンの期限切れ、または不正なトークン

**対処:**
```python
# トークンを更新
response = requests.post(
    f"{AUTH_SERVER_URL}/api/refresh",
    params={"token": old_token}
)
new_token = response.json()["token"]
```

---

## サンプルコード

### 完全な Streamlit アプリ例

```python
# app.py
import streamlit as st
import requests
from datetime import datetime

# 設定
AUTH_SERVER_URL = "https://auth.example.com"
PROJECT_ID = "my-streamlit-app"

def init_session():
    """セッション状態を初期化"""
    if "token" not in st.session_state:
        st.session_state.token = None
    if "user" not in st.session_state:
        st.session_state.user = None

def check_auth():
    """認証チェック"""
    # URLパラメータからトークンを取得
    query_params = st.query_params

    if "token" in query_params:
        token = query_params["token"]
        user = verify_token(token)

        if user:
            st.session_state.token = token
            st.session_state.user = user
            st.query_params.clear()
            return True
        else:
            st.error("トークンの検証に失敗しました")
            return False

    return st.session_state.token is not None

def verify_token(token):
    """トークン検証"""
    try:
        resp = requests.get(
            f"{AUTH_SERVER_URL}/api/verify",
            params={"token": token},
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return None

def show_login():
    """ログイン画面"""
    st.title("🔐 ログインが必要です")
    st.write("このアプリを使用するにはログインが必要です。")

    login_url = f"{AUTH_SERVER_URL}/login/{PROJECT_ID}"

    if st.button("Googleアカウントでログイン", type="primary"):
        st.markdown(f'<meta http-equiv="refresh" content="0;url={login_url}">', unsafe_allow_html=True)

def show_sidebar():
    """サイドバー"""
    user = st.session_state.user

    with st.sidebar:
        st.write(f"👤 **{user['name']}**")
        st.write(f"📧 {user['email']}")

        # トークン有効期限
        exp = datetime.fromtimestamp(user['exp'])
        st.write(f"⏰ 有効期限: {exp.strftime('%Y/%m/%d')}")

        if st.button("ログアウト"):
            st.session_state.token = None
            st.session_state.user = None
            st.rerun()

def main_content():
    """メインコンテンツ"""
    st.title("🎉 マイアプリ")
    st.success("認証に成功しました！")

    # ここにアプリのメインロジックを記述
    st.write("ここにアプリのコンテンツを追加してください。")

def main():
    st.set_page_config(
        page_title="マイアプリ",
        page_icon="🎉",
        layout="wide"
    )

    init_session()

    if not check_auth():
        show_login()
        return

    show_sidebar()
    main_content()

if __name__ == "__main__":
    main()
```

---

## 📞 サポート

### 問い合わせ先

- プロジェクト登録の申請
- 設定変更の依頼
- 技術的な質問

### 関連ドキュメント

- [設計書 (DESIGN.md)](./DESIGN.md) - システム全体の設計
- [API仕様書 (auth_server_api.yaml)](./auth_server_api.yaml) - OpenAPI形式の詳細仕様
- [実装サマリー (IMPLEMENTATION_SUMMARY.md)](./IMPLEMENTATION_SUMMARY.md) - 実装の詳細

---

**最終更新日:** 2025-12-11
