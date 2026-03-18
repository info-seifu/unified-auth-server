# APIプロキシサーバー修正ガイド

## 概要

統合認証サーバーでリフレッシュトークン方式を導入したことに伴い、APIプロキシサーバー側でも対応が必要です。

このドキュメントでは、APIプロキシサーバーの修正内容を説明します。

---

## 変更点サマリー

| 項目 | 変更前 | 変更後 |
|------|--------|--------|
| アクセストークン有効期限 | 30日 | **1時間** |
| トークン検証 | 変更なし | 変更なし（互換性維持） |
| 401エラー時の処理 | クライアント任せ | **クライアントがリフレッシュを試行** |

---

## APIプロキシサーバーの修正は基本的に不要

**重要**: APIプロキシサーバー自体の修正は最小限です。

### 理由

1. トークン検証ロジックは変更なし（JWT署名検証）
2. アクセストークンの形式は同じ（`token_type: "access"` が追加されるのみ）
3. 有効期限が短くなるだけで、検証処理は同じ

### 変更が必要な場合

以下の場合のみ修正が必要：

| 条件 | 修正内容 |
|------|---------|
| トークンの `token_type` を検証している | `"access"` を許可するよう変更 |
| トークンキャッシュを長時間保持している | キャッシュ期間を1時間以下に変更 |

---

## クライアントアプリ側の対応（重要）

APIプロキシを呼び出すクライアントアプリで、以下の対応が必要です。

### 1. 401エラー時のリフレッシュ処理

```python
# Python（Streamlit等）の例

import httpx

async def call_api_with_refresh(endpoint: str, access_token: str) -> dict:
    """APIプロキシ呼び出し（自動リフレッシュ付き）"""

    # 1. 通常のAPI呼び出し
    response = await httpx.post(
        f"{PROXY_URL}{endpoint}",
        headers={"Authorization": f"Bearer {access_token}"}
    )

    # 2. 401エラーの場合はリフレッシュを試行
    if response.status_code == 401:
        # リフレッシュトークンで新しいアクセストークンを取得
        new_access_token = await refresh_access_token()

        if new_access_token:
            # 新しいトークンで再試行
            response = await httpx.post(
                f"{PROXY_URL}{endpoint}",
                headers={"Authorization": f"Bearer {new_access_token}"}
            )
        else:
            # リフレッシュ失敗 → 再ログインが必要
            raise AuthenticationError("セッションの有効期限が切れました")

    return response.json()


async def refresh_access_token() -> Optional[str]:
    """認証サーバーでアクセストークンをリフレッシュ"""

    response = await httpx.post(
        f"{AUTH_SERVER_URL}/api/refresh",
        # リフレッシュトークンはCookieで自動送信される
        # credentials="include" が必要（ブラウザの場合）
    )

    if response.status_code == 200:
        data = response.json()
        return data["access_token"]
    else:
        # リフレッシュトークンも期限切れ
        return None
```

### 2. JavaScript（フロントエンド）の例

```javascript
// fetch API with auto-refresh

async function callApiWithRefresh(endpoint, accessToken) {
    // 1. 通常のAPI呼び出し
    let response = await fetch(`${PROXY_URL}${endpoint}`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${accessToken}`,
            'Content-Type': 'application/json'
        }
    });

    // 2. 401エラーの場合はリフレッシュを試行
    if (response.status === 401) {
        const newToken = await refreshAccessToken();

        if (newToken) {
            // 新しいトークンで再試行
            response = await fetch(`${PROXY_URL}${endpoint}`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${newToken}`,
                    'Content-Type': 'application/json'
                }
            });
        } else {
            // 再ログインへリダイレクト
            window.location.href = `${AUTH_SERVER_URL}/login/${PROJECT_ID}`;
            return null;
        }
    }

    return response.json();
}

async function refreshAccessToken() {
    const response = await fetch(`${AUTH_SERVER_URL}/api/refresh`, {
        method: 'POST',
        credentials: 'include'  // Cookieを送信するために必要
    });

    if (response.ok) {
        const data = await response.json();
        // 新しいアクセストークンを保存
        localStorage.setItem('access_token', data.access_token);
        return data.access_token;
    }

    return null;
}
```

---

## CORS設定の確認

リフレッシュリクエストでCookieを送信するため、認証サーバーのCORS設定を確認してください。

### 認証サーバー側（設定済み）

```python
# app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,  # ← 重要：Cookieを許可
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### クライアント側

```javascript
// fetch時に credentials: 'include' を指定
fetch(url, {
    credentials: 'include'  // ← 必須
});
```

```python
# httpx使用時
httpx.post(url, cookies=request.cookies)

# または requests使用時
requests.post(url, cookies=request.cookies)
```

---

## シーケンス図

### 正常系：API呼び出し成功

```
クライアント              APIプロキシ              認証サーバー
    │                        │                        │
    │  POST /api/proxy       │                        │
    │  Authorization: Bearer │                        │
    │  {access_token}        │                        │
    │───────────────────────→│                        │
    │                        │                        │
    │                        │  トークン検証          │
    │                        │  (JWT署名確認)         │
    │                        │                        │
    │  200 OK                │                        │
    │  {result}              │                        │
    │←───────────────────────│                        │
    │                        │                        │
```

### 異常系：アクセストークン期限切れ → リフレッシュ成功

```
クライアント              APIプロキシ              認証サーバー
    │                        │                        │
    │  POST /api/proxy       │                        │
    │  Authorization: Bearer │                        │
    │  {expired_token}       │                        │
    │───────────────────────→│                        │
    │                        │                        │
    │  401 Unauthorized      │                        │
    │  (トークン期限切れ)     │                        │
    │←───────────────────────│                        │
    │                        │                        │
    │  POST /api/refresh     │                        │
    │  Cookie: refresh_token │                        │
    │────────────────────────────────────────────────→│
    │                        │                        │
    │  200 OK                │                        │
    │  {new_access_token}    │                        │
    │  Set-Cookie: new_refresh_token                  │
    │←────────────────────────────────────────────────│
    │                        │                        │
    │  POST /api/proxy       │                        │
    │  Authorization: Bearer │                        │
    │  {new_access_token}    │                        │
    │───────────────────────→│                        │
    │                        │                        │
    │  200 OK                │                        │
    │  {result}              │                        │
    │←───────────────────────│                        │
    │                        │                        │
```

### 異常系：リフレッシュトークンも期限切れ → 再ログイン

```
クライアント              APIプロキシ              認証サーバー
    │                        │                        │
    │  POST /api/proxy       │                        │
    │  (expired_token)       │                        │
    │───────────────────────→│                        │
    │                        │                        │
    │  401 Unauthorized      │                        │
    │←───────────────────────│                        │
    │                        │                        │
    │  POST /api/refresh     │                        │
    │  Cookie: expired_refresh_token                  │
    │────────────────────────────────────────────────→│
    │                        │                        │
    │  401 Unauthorized      │                        │
    │  {"error": "REFRESH_TOKEN_EXPIRED"}             │
    │←────────────────────────────────────────────────│
    │                        │                        │
    │  → /login/{project_id} へリダイレクト           │
    │    （再ログイン）       │                        │
    │                        │                        │
```

---

## チェックリスト

### APIプロキシサーバー

- [ ] トークン検証ロジックが `token_type: "access"` を許可するか確認
- [ ] トークンキャッシュの有効期限が1時間以下であることを確認
- [ ] 特に修正不要であれば、そのまま

### クライアントアプリ

- [ ] 401エラー時にリフレッシュを試行するロジックを実装
- [ ] リフレッシュ失敗時に再ログインへリダイレクトする処理を実装
- [ ] fetch/httpx で `credentials: 'include'` を設定
- [ ] 新しいアクセストークンの保存処理を実装

### 認証サーバー（対応済み予定）

- [ ] リフレッシュエンドポイント `/api/refresh` の実装
- [ ] リフレッシュトークンのHttpOnly Cookie設定
- [ ] CORS設定で `allow_credentials=True`

---

## 移行時の注意事項

### 1. 既存トークンとの互換性

- 既存の30日トークンは、有効期限まで引き続き使用可能
- 新方式のトークンと旧方式のトークンは `token_type` フィールドで区別可能
- 旧方式（`token_type` なし）も引き続き受け入れる

### 2. 段階的な移行

1. 認証サーバーを新方式にアップデート
2. クライアントアプリを新方式に対応
3. 新規ログインユーザーから新方式を適用
4. 30日後には全ユーザーが新方式に移行完了

### 3. ロールバック

問題が発生した場合：
- 認証サーバーを旧方式に戻す
- クライアントアプリは旧方式でも動作可能（リフレッシュが不要になるだけ）

---

## お問い合わせ

実装でご不明な点があれば、認証サーバー管理者にお問い合わせください。
