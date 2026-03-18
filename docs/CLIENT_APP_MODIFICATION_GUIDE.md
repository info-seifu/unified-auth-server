# クライアントアプリ修正ガイド（リフレッシュトークン対応）

## 概要

統合認証サーバーでリフレッシュトークン方式を導入したことに伴い、クライアントアプリ（Streamlit等）での対応が必要です。

このドキュメントでは、クライアントアプリの修正内容を詳細に説明します。

---

## 変更点サマリー

| 項目 | 変更前 | 変更後 |
|------|--------|--------|
| トークン数 | 1つ（30日JWT） | **2つ**（アクセス1時間 + リフレッシュ1〜30日） |
| アクセストークン有効期限 | 30日 | **1時間** |
| アクセストークン保存 | Session State | Session State（変更なし） |
| リフレッシュトークン保存 | なし | **Session State / LocalStorage** |
| トークン更新 | 手動リフレッシュ | **自動リフレッシュ**（401エラー時） |
| ログイン後のURL | `?token=xxx` | `?access_token=xxx&refresh_token=yyy` |

---

## 対象アプリケーション

- Streamlitアプリ（sogo-slide等）
- Next.js / React アプリ
- その他Webアプリケーション

---

## Streamlitアプリの修正

### 修正対象ファイル

| ファイル | 修正内容 |
|---------|---------|
| `app/services/auth_client.py` | リフレッシュ処理の追加 |
| `streamlit_app.py` | 認証フローの変更 |
| `app/services/api_proxy_client.py` | 401エラー時のリフレッシュ処理 |

---

### 1. auth_client.py の修正

#### 変更前

```python
class AuthClient:
    def __init__(self, auth_server_url: str, project_id: str):
        self.auth_server_url = auth_server_url
        self.project_id = project_id

    def get_login_url(self, redirect_uri: str) -> str:
        """ログインURLを取得"""
        return f"{self.auth_server_url}/login/{self.project_id}?redirect_uri={redirect_uri}"

    def verify_token(self, token: str) -> Optional[Dict]:
        """トークンを検証"""
        response = httpx.get(
            f"{self.auth_server_url}/api/verify",
            params={"token": token}
        )
        if response.status_code == 200:
            return response.json()
        return None

    def refresh_token(self, token: str) -> Optional[str]:
        """トークンをリフレッシュ（旧方式）"""
        response = httpx.post(
            f"{self.auth_server_url}/api/refresh",
            params={"token": token}
        )
        if response.status_code == 200:
            return response.json().get("token")
        return None
```

#### 変更後

```python
import httpx
from typing import Optional, Dict, Tuple
import streamlit as st


class AuthClient:
    def __init__(self, auth_server_url: str, project_id: str):
        self.auth_server_url = auth_server_url
        self.project_id = project_id

    def get_login_url(self, redirect_uri: str, state: Optional[str] = None) -> str:
        """ログインURLを取得"""
        url = f"{self.auth_server_url}/login/{self.project_id}?redirect_uri={redirect_uri}"
        if state:
            url += f"&state={state}"
        return url

    def verify_token(self, token: str) -> Optional[Dict]:
        """アクセストークンを検証"""
        try:
            response = httpx.get(
                f"{self.auth_server_url}/api/verify",
                params={"token": token},
                timeout=30.0
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            st.error(f"トークン検証エラー: {e}")
            return None

    def refresh_tokens(self, refresh_token: str) -> Optional[Dict]:
        """
        リフレッシュトークンを使用して新しいトークンペアを取得

        Args:
            refresh_token: 現在のリフレッシュトークン

        Returns:
            {
                "access_token": "新しいアクセストークン",
                "refresh_token": "新しいリフレッシュトークン",
                "expires_in": 3600
            }
            または失敗時はNone
        """
        try:
            response = httpx.post(
                f"{self.auth_server_url}/api/refresh",
                json={
                    "refresh_token": refresh_token,
                    "project_id": self.project_id
                },
                timeout=30.0
            )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                # リフレッシュトークン期限切れ or 再利用検知
                data = response.json()
                error = data.get("error", "")
                if error == "REFRESH_TOKEN_REUSED":
                    st.warning("セキュリティ上の理由でログアウトされました。")
                return None
            else:
                st.warning(f"トークンリフレッシュ失敗: {response.status_code}")
                return None
        except Exception as e:
            st.error(f"リフレッシュエラー: {e}")
            return None

    def logout(self, return_url: Optional[str] = None) -> str:
        """ログアウトURLを取得"""
        url = f"{self.auth_server_url}/logout"
        if return_url:
            url += f"?return_url={return_url}"
        return url
```

---

### 2. streamlit_app.py の修正

#### 変更前

```python
def main():
    # 認証チェック
    if "access_token" not in st.session_state:
        # URLからトークンを取得
        token = st.query_params.get("token")

        if token:
            # トークン検証
            user_info = auth_client.verify_token(token)
            if user_info:
                st.session_state["access_token"] = token
                st.session_state["user_info"] = user_info
                st.query_params.clear()
                st.rerun()
            else:
                st.error("無効なトークンです")
                st.stop()
        else:
            # ログインページへリダイレクト
            login_url = auth_client.get_login_url(redirect_uri)
            st.markdown(f'<a href="{login_url}">ログイン</a>', unsafe_allow_html=True)
            st.stop()

    # トークン有効期限チェック
    user_info = auth_client.verify_token(st.session_state["access_token"])
    if not user_info:
        # トークンリフレッシュ試行（旧方式）
        new_token = auth_client.refresh_token(st.session_state["access_token"])
        if new_token:
            st.session_state["access_token"] = new_token
            st.rerun()
        else:
            del st.session_state["access_token"]
            st.rerun()

    # メインアプリケーション
    show_main_app()
```

#### 変更後

```python
import streamlit as st
from app.services.auth_client import AuthClient

# 認証クライアント初期化
auth_client = AuthClient(
    auth_server_url=AUTH_SERVER_URL,
    project_id=PROJECT_ID
)


def handle_authentication() -> bool:
    """
    認証処理を行う

    Returns:
        True: 認証成功、False: 認証失敗（再ログイン必要）
    """

    # 1. URLからトークンを取得（初回ログイン後のリダイレクト）
    access_token_from_url = st.query_params.get("access_token")
    refresh_token_from_url = st.query_params.get("refresh_token")

    if access_token_from_url and refresh_token_from_url:
        # トークン検証
        user_info = auth_client.verify_token(access_token_from_url)
        if user_info:
            # 両方のトークンをSession Stateに保存
            st.session_state["access_token"] = access_token_from_url
            st.session_state["refresh_token"] = refresh_token_from_url
            st.session_state["user_info"] = user_info
            st.query_params.clear()  # URLからトークンを削除
            st.rerun()
        else:
            st.error("無効なトークンです。再度ログインしてください。")
            return False

    # 2. Session Stateにトークンがあるか確認
    if "access_token" not in st.session_state:
        return False

    # 3. アクセストークン有効性を確認
    user_info = auth_client.verify_token(st.session_state["access_token"])

    if user_info:
        # トークン有効
        st.session_state["user_info"] = user_info
        return True

    # 4. アクセストークン期限切れ → リフレッシュ試行
    if "refresh_token" not in st.session_state:
        # リフレッシュトークンがない → 再ログイン必要
        clear_session()
        return False

    st.info("セッションを更新中...")
    new_tokens = auth_client.refresh_tokens(st.session_state["refresh_token"])

    if new_tokens:
        # リフレッシュ成功 → 新しいトークンペアを保存
        st.session_state["access_token"] = new_tokens["access_token"]
        st.session_state["refresh_token"] = new_tokens["refresh_token"]  # ローテーション
        user_info = auth_client.verify_token(new_tokens["access_token"])
        st.session_state["user_info"] = user_info
        st.rerun()

    # 5. リフレッシュも失敗 → 再ログイン必要
    clear_session()
    return False


def clear_session():
    """認証関連のSession Stateをクリア"""
    for key in ["access_token", "refresh_token", "user_info"]:
        if key in st.session_state:
            del st.session_state[key]


def show_login_page():
    """ログインページを表示"""
    st.title("ログインが必要です")

    # 現在のURLをリダイレクト先として設定
    redirect_uri = get_current_url()
    login_url = auth_client.get_login_url(redirect_uri)

    st.markdown(
        f"""
        <div style="text-align: center; padding: 50px;">
            <p>このアプリケーションを使用するには、学校アカウントでログインしてください。</p>
            <a href="{login_url}" target="_self">
                <button style="
                    background-color: #4285f4;
                    color: white;
                    padding: 12px 24px;
                    border: none;
                    border-radius: 4px;
                    font-size: 16px;
                    cursor: pointer;
                ">
                    Googleでログイン
                </button>
            </a>
        </div>
        """,
        unsafe_allow_html=True
    )


def get_current_url() -> str:
    """現在のURLを取得"""
    # Streamlit Cloudの場合
    # return st.get_option("browser.serverAddress")

    # ローカル開発の場合
    return "http://localhost:8501/"


def main():
    st.set_page_config(page_title="アプリケーション名", layout="wide")

    # 認証チェック
    if not handle_authentication():
        show_login_page()
        st.stop()

    # ユーザー情報を表示（デバッグ用）
    user_info = st.session_state.get("user_info", {})
    with st.sidebar:
        st.write(f"ログイン中: {user_info.get('name', 'Unknown')}")
        st.write(f"メール: {user_info.get('email', 'Unknown')}")

        if st.button("ログアウト"):
            # Session Stateをクリア
            for key in ["access_token", "user_info"]:
                if key in st.session_state:
                    del st.session_state[key]
            # ログアウトURLへリダイレクト
            logout_url = auth_client.logout(return_url=get_current_url())
            st.markdown(f'<meta http-equiv="refresh" content="0;url={logout_url}">', unsafe_allow_html=True)
            st.stop()

    # メインアプリケーション
    show_main_app()


def show_main_app():
    """メインアプリケーションを表示"""
    st.title("アプリケーション")
    st.write("ここにメインコンテンツを表示")


if __name__ == "__main__":
    main()
```

---

### 3. api_proxy_client.py の修正

#### 変更前

```python
class APIProxyClient:
    def __init__(self, proxy_url: str):
        self.proxy_url = proxy_url

    def call_api(self, endpoint: str, token: str, data: dict) -> dict:
        """APIプロキシ経由でAPIを呼び出す"""
        response = httpx.post(
            f"{self.proxy_url}/api/proxy",
            headers={"Authorization": f"Bearer {token}"},
            json={"endpoint": endpoint, "data": data}
        )
        response.raise_for_status()
        return response.json()
```

#### 変更後

```python
import httpx
from typing import Optional, Dict, Any
import streamlit as st


class APIProxyClient:
    def __init__(
        self,
        proxy_url: str,
        auth_client: 'AuthClient'
    ):
        """
        APIプロキシクライアント

        Args:
            proxy_url: プロキシサーバーのURL
            auth_client: 認証クライアント（リフレッシュ用）
        """
        self.proxy_url = proxy_url
        self.auth_client = auth_client

    def call_api(
        self,
        endpoint: str,
        data: Optional[Dict] = None,
        method: str = "POST",
        retry_on_401: bool = True
    ) -> Dict[str, Any]:
        """
        APIプロキシ経由でAPIを呼び出す（自動リフレッシュ付き）

        Args:
            endpoint: APIエンドポイント
            data: リクエストデータ
            method: HTTPメソッド
            retry_on_401: 401エラー時にリフレッシュして再試行するか

        Returns:
            APIレスポンス

        Raises:
            AuthenticationError: 認証エラー（再ログイン必要）
            APIError: API呼び出しエラー
        """
        access_token = st.session_state.get("access_token")

        if not access_token:
            raise AuthenticationError("アクセストークンがありません")

        # 1. API呼び出し
        response = self._make_request(endpoint, access_token, data, method)

        # 2. 成功時はそのまま返す
        if response.status_code == 200:
            return response.json()

        # 3. 401エラー時はリフレッシュを試行
        if response.status_code == 401 and retry_on_401:
            new_tokens = self._try_refresh()

            if new_tokens:
                # 新しいトークンで再試行
                response = self._make_request(
                    endpoint,
                    new_tokens["access_token"],
                    data,
                    method
                )

                if response.status_code == 200:
                    return response.json()

            # リフレッシュ失敗または再試行も失敗
            raise AuthenticationError(
                "セッションの有効期限が切れました。再度ログインしてください。"
            )

        # 4. その他のエラー
        raise APIError(
            f"API呼び出しエラー: {response.status_code}",
            status_code=response.status_code,
            detail=response.text
        )

    def _make_request(
        self,
        endpoint: str,
        token: str,
        data: Optional[Dict],
        method: str
    ) -> httpx.Response:
        """HTTPリクエストを実行"""
        headers = {"Authorization": f"Bearer {token}"}

        if method.upper() == "POST":
            return httpx.post(
                f"{self.proxy_url}/api/proxy",
                headers=headers,
                json={"endpoint": endpoint, "data": data or {}},
                timeout=60.0
            )
        elif method.upper() == "GET":
            return httpx.get(
                f"{self.proxy_url}/api/proxy",
                headers=headers,
                params={"endpoint": endpoint},
                timeout=60.0
            )
        else:
            raise ValueError(f"Unsupported method: {method}")

    def _try_refresh(self) -> Optional[Dict]:
        """トークンリフレッシュを試行"""
        refresh_token = st.session_state.get("refresh_token")

        if not refresh_token:
            return None

        try:
            new_tokens = self.auth_client.refresh_tokens(refresh_token)

            if new_tokens:
                # 新しいトークンペアをSession Stateに保存（ローテーション）
                st.session_state["access_token"] = new_tokens["access_token"]
                st.session_state["refresh_token"] = new_tokens["refresh_token"]
                return new_tokens

            return None
        except Exception as e:
            st.warning(f"トークンリフレッシュエラー: {e}")
            return None


class AuthenticationError(Exception):
    """認証エラー（再ログイン必要）"""
    pass


class APIError(Exception):
    """API呼び出しエラー"""
    def __init__(self, message: str, status_code: int = None, detail: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


# 使用例
def create_api_client(auth_client: 'AuthClient') -> APIProxyClient:
    """APIクライアントを作成"""
    return APIProxyClient(
        proxy_url=PROXY_SERVER_URL,
        auth_client=auth_client
    )
```

---

### 4. 使用例（統合）

```python
# streamlit_app.py

import streamlit as st
from app.services.auth_client import AuthClient
from app.services.api_proxy_client import APIProxyClient, AuthenticationError, APIError

# 設定
AUTH_SERVER_URL = "https://unified-auth-server-xxx.run.app"
PROXY_SERVER_URL = "https://unified-auth-server-xxx.run.app"  # 同じサーバー
PROJECT_ID = "shinro-compass"

# クライアント初期化
auth_client = AuthClient(AUTH_SERVER_URL, PROJECT_ID)
api_client = APIProxyClient(
    proxy_url=PROXY_SERVER_URL,
    auth_client=auth_client,
    get_token=lambda: st.session_state.get("access_token"),
    set_token=lambda token: st.session_state.__setitem__("access_token", token)
)


def main():
    # 認証チェック
    if not handle_authentication():
        show_login_page()
        st.stop()

    # API呼び出し例
    try:
        result = api_client.call_api(
            endpoint="/generate",
            data={"prompt": "Hello, world!"}
        )
        st.success(f"結果: {result}")

    except AuthenticationError as e:
        st.error(str(e))
        # Session Stateをクリアして再ログインを促す
        if "access_token" in st.session_state:
            del st.session_state["access_token"]
        st.rerun()

    except APIError as e:
        st.error(f"APIエラー: {e}")
```

---

## Next.js / Reactアプリの修正

### 1. 認証ユーティリティ

```typescript
// lib/auth.ts

const AUTH_SERVER_URL = process.env.NEXT_PUBLIC_AUTH_SERVER_URL;
const PROJECT_ID = process.env.NEXT_PUBLIC_PROJECT_ID;

interface UserInfo {
  email: string;
  name: string;
  project_id: string;
  role?: string;
  exp: number;
}

interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

/**
 * アクセストークンを検証
 */
export async function verifyToken(token: string): Promise<UserInfo | null> {
  try {
    const response = await fetch(`${AUTH_SERVER_URL}/api/verify?token=${token}`);
    if (response.ok) {
      return response.json();
    }
    return null;
  } catch (error) {
    console.error('Token verification failed:', error);
    return null;
  }
}

/**
 * リフレッシュトークンを使用して新しいトークンペアを取得
 */
export async function refreshTokens(refreshToken: string): Promise<TokenResponse | null> {
  try {
    const response = await fetch(`${AUTH_SERVER_URL}/api/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        refresh_token: refreshToken,
        project_id: PROJECT_ID
      }),
    });

    if (response.ok) {
      const data: TokenResponse = await response.json();
      // 新しいトークンペアを保存（ローテーション）
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);
      return data;
    }

    if (response.status === 401) {
      // リフレッシュトークン期限切れ or 再利用検知
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
    }

    return null;
  } catch (error) {
    console.error('Token refresh failed:', error);
    return null;
  }
}

/**
 * ログインURLを取得
 */
export function getLoginUrl(redirectUri: string): string {
  return `${AUTH_SERVER_URL}/login/${PROJECT_ID}?redirect_uri=${encodeURIComponent(redirectUri)}`;
}

/**
 * ログアウトURLを取得
 */
export function getLogoutUrl(returnUrl: string): string {
  return `${AUTH_SERVER_URL}/logout?return_url=${encodeURIComponent(returnUrl)}`;
}
```

### 2. API呼び出しユーティリティ

```typescript
// lib/api.ts

import { refreshAccessToken } from './auth';

const PROXY_URL = process.env.NEXT_PUBLIC_PROXY_URL;

/**
 * APIを呼び出す（自動リフレッシュ付き）
 */
export async function callApi<T>(
  endpoint: string,
  data?: Record<string, any>,
  options?: {
    method?: 'GET' | 'POST';
    retryOn401?: boolean;
  }
): Promise<T> {
  const { method = 'POST', retryOn401 = true } = options || {};

  const token = localStorage.getItem('access_token');

  if (!token) {
    throw new AuthenticationError('アクセストークンがありません');
  }

  // 1. API呼び出し
  let response = await makeRequest(endpoint, token, data, method);

  // 2. 401エラー時はリフレッシュを試行
  if (response.status === 401 && retryOn401) {
    const newToken = await refreshAccessToken();

    if (newToken) {
      // 新しいトークンを保存
      localStorage.setItem('access_token', newToken);

      // 再試行
      response = await makeRequest(endpoint, newToken, data, method);
    } else {
      // リフレッシュ失敗
      localStorage.removeItem('access_token');
      throw new AuthenticationError('セッションの有効期限が切れました');
    }
  }

  if (!response.ok) {
    throw new APIError(`API error: ${response.status}`, response.status);
  }

  return response.json();
}

async function makeRequest(
  endpoint: string,
  token: string,
  data: Record<string, any> | undefined,
  method: string
): Promise<Response> {
  return fetch(`${PROXY_URL}/api/proxy`, {
    method,
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: method === 'POST' ? JSON.stringify({ endpoint, data }) : undefined,
  });
}

export class AuthenticationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'AuthenticationError';
  }
}

export class APIError extends Error {
  statusCode: number;

  constructor(message: string, statusCode: number) {
    super(message);
    this.name = 'APIError';
    this.statusCode = statusCode;
  }
}
```

### 3. React Hookの例

```typescript
// hooks/useAuth.ts

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/router';
import { verifyToken, refreshAccessToken, getLoginUrl } from '@/lib/auth';

interface UseAuthResult {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: UserInfo | null;
  login: () => void;
  logout: () => void;
}

export function useAuth(): UseAuthResult {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState<UserInfo | null>(null);

  useEffect(() => {
    const checkAuth = async () => {
      // URLからトークンを取得（ログイン後のリダイレクト）
      const tokenFromUrl = router.query.token as string;

      if (tokenFromUrl) {
        const userInfo = await verifyToken(tokenFromUrl);
        if (userInfo) {
          localStorage.setItem('access_token', tokenFromUrl);
          setUser(userInfo);

          // URLからトークンを削除
          const { token, ...rest } = router.query;
          router.replace({ pathname: router.pathname, query: rest }, undefined, { shallow: true });
        }
        setIsLoading(false);
        return;
      }

      // LocalStorageからトークンを取得
      const savedToken = localStorage.getItem('access_token');

      if (!savedToken) {
        setIsLoading(false);
        return;
      }

      // トークン検証
      let userInfo = await verifyToken(savedToken);

      if (!userInfo) {
        // リフレッシュ試行
        const newToken = await refreshAccessToken();

        if (newToken) {
          localStorage.setItem('access_token', newToken);
          userInfo = await verifyToken(newToken);
        } else {
          localStorage.removeItem('access_token');
        }
      }

      setUser(userInfo);
      setIsLoading(false);
    };

    checkAuth();
  }, [router]);

  const login = useCallback(() => {
    const currentUrl = window.location.href;
    window.location.href = getLoginUrl(currentUrl);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('access_token');
    setUser(null);
    // ログアウトURLへリダイレクト
    window.location.href = getLogoutUrl(window.location.origin);
  }, []);

  return {
    isAuthenticated: !!user,
    isLoading,
    user,
    login,
    logout,
  };
}
```

---

## チェックリスト

### Streamlitアプリ

- [ ] `auth_client.py` に `refresh_tokens()` メソッドを追加
- [ ] `streamlit_app.py` でURLから両トークンを取得するよう変更
- [ ] Session Stateに `access_token` と `refresh_token` の両方を保存
- [ ] `api_proxy_client.py` に401エラー時の自動リフレッシュを追加
- [ ] リフレッシュ成功時に新しいリフレッシュトークンも保存（ローテーション対応）
- [ ] Session Stateのクリア処理（`access_token`, `refresh_token`, `user_info`）

### Next.js / Reactアプリ

- [ ] `lib/auth.ts` に `refreshTokens()` 関数を作成
- [ ] URLから `access_token` と `refresh_token` の両方を取得
- [ ] LocalStorageに両トークンを保存
- [ ] `lib/api.ts` にAPI呼び出しユーティリティを作成
- [ ] 401エラー時の自動リフレッシュ処理
- [ ] リフレッシュ成功時に新しいリフレッシュトークンも保存（ローテーション対応）

### 共通

- [ ] エラーハンドリングの実装（期限切れ、再利用検知）
- [ ] ユーザー向けエラーメッセージの表示
- [ ] ログアウト処理の実装（両トークンをクリア）
- [ ] 「別の場所でログインされた可能性があります」メッセージ対応

---

## トラブルシューティング

### 1. リフレッシュが失敗する

**原因**: CORSエラー、またはCookieが送信されていない

**対策**:
```javascript
// credentials: 'include' を必ず設定
fetch(url, { credentials: 'include' });
```

### 2. 401エラーが無限ループする

**原因**: リフレッシュ後も401が返る

**対策**:
```python
# retry_on_401=False で再試行を防ぐ
response = api_client.call_api(endpoint, data, retry_on_401=False)
```

### 3. トークンがSession Stateに保存されない

**原因**: Streamlitの再実行でSession Stateがリセットされる

**対策**:
```python
# st.rerun() の前にSession Stateを更新
st.session_state["access_token"] = new_token
st.rerun()
```

---

## お問い合わせ

実装でご不明な点があれば、認証サーバー管理者にお問い合わせください。
