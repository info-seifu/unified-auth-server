# リフレッシュトークン方式 設計書

## 1. 概要

### 1.1 背景と目的

現在の認証方式では、JWTトークン（30日有効）をクライアント側で保持しているため、以下の課題がある：

- トークン漏洩時に長期間（30日）悪用されるリスク
- 漏洩を検知する手段がない
- プロダクトごとの再ログイン頻度を調整できない

リフレッシュトークン方式を導入することで、セキュリティを向上させつつ、運用の柔軟性を確保する。

### 1.2 現状との比較

| 項目 | 現状 | 新方式 |
|------|------|--------|
| トークン数 | 1つ（30日有効） | 2つ（アクセス1時間 + リフレッシュ1〜30日） |
| API呼び出し用トークンの有効期限 | 30日 | **1時間** |
| 漏洩時の被害期間 | 30日間 | **1時間**（アクセストークン） |
| 漏洩の検知 | ❌ 不可 | ✅ **可能**（ローテーション） |
| プロダクト別設定 | ❌ 不可 | ✅ **可能** |
| 保存場所 | クライアント | クライアント（同じ） |

### 1.3 設計方針

| 項目 | 設定 |
|------|------|
| アクセストークン有効期限 | **1時間（全プロダクト共通）** |
| リフレッシュトークン有効期限 | **プロダクトごとに設定可能**（1日〜30日） |
| 保存場所 | **両方ともクライアント側**（Session State / LocalStorage） |
| トークンローテーション | **有効**（リフレッシュごとに新トークン発行） |

---

## 2. トークン仕様

### 2.1 アクセストークン

| 項目 | 値 |
|------|-----|
| 形式 | JWT |
| 有効期限 | 1時間（固定） |
| 署名アルゴリズム | HS256 |
| 用途 | APIプロキシへの認証、ユーザー情報の表示 |
| 保存場所 | クライアント（Session State / LocalStorage） |

**ペイロード構造**:
```json
{
  "email": "user@i-seifu.jp",
  "name": "山田太郎",
  "project_id": "shinro-compass",
  "role": "student",
  "picture": "https://...",
  "token_type": "access",
  "iat": 1234567890,
  "exp": 1234571490,
  "jti": "access-abc123"
}
```

### 2.2 リフレッシュトークン

| 項目 | 値 |
|------|-----|
| 形式 | JWT |
| 有効期限 | プロダクトごとに設定（1日〜30日） |
| 署名アルゴリズム | HS256 |
| 用途 | 新しいアクセストークン・リフレッシュトークンの取得 |
| 保存場所 | クライアント（Session State / LocalStorage） |

**ペイロード構造**:
```json
{
  "email": "user@i-seifu.jp",
  "project_id": "shinro-compass",
  "token_type": "refresh",
  "iat": 1234567890,
  "exp": 1237246290,
  "jti": "refresh-xyz789"
}
```

**注意**: リフレッシュトークンには `name`, `role`, `picture` を含めない。リフレッシュ時に最新情報を取得するため。

---

## 3. トークンローテーション

### 3.1 概要

リフレッシュするたびに、新しいリフレッシュトークンを発行し、古いものを無効化する方式。

### 3.2 目的

1. **漏洩検知**: 同じトークンが2回使われたら異常として検知
2. **被害限定**: 正規ユーザーがリフレッシュすると、攻撃者のトークンが無効化される

### 3.3 動作フロー

```
【通常のリフレッシュ】
リフレッシュトークンA でリフレッシュ
  → 新しいアクセストークン発行
  → 新しいリフレッシュトークンB 発行
  → トークンA のJTIを「使用済み」として記録
  → トークンA は無効化

【漏洩検知】
攻撃者がトークンA を使用（先にリフレッシュ）
  → トークンB' を取得
  → トークンA は「使用済み」

正規ユーザーがトークンA を使用
  → 「使用済み」エラー
  → 全トークン無効化
  → 「別の場所でログインされた可能性があります」と通知
  → 再ログイン要求
```

### 3.4 使用済みトークン管理

| 方式 | メリット | デメリット | 推奨環境 |
|------|---------|-----------|---------|
| メモリ（辞書） | 実装簡単、高速 | サーバー再起動で消える | 開発環境 |
| Firestore | 永続化、スケーラブル | レイテンシ | 本番環境 |

**保存する情報**:
```python
{
    "jti": "refresh-xyz789",      # トークン固有ID
    "email": "user@i-seifu.jp",   # ユーザー識別
    "project_id": "shinro-compass",
    "used_at": "2024-01-01T10:00:00Z",
    "ip_address": "192.168.1.1"   # 監査用
}
```

**TTL（自動削除）**: リフレッシュトークンの有効期限 + 1日

---

## 4. プロジェクト設定

### 4.1 設定項目

```python
{
    "project_id": "shinro-compass",

    # 既存設定（後方互換のため残す）
    "token_expiry_days": 30,

    # 新規追加
    "refresh_token_expiry_days": 1,    # リフレッシュトークン有効期限（日数）
}
```

**注意**: `token_expiry_days` は後方互換のため残すが、新方式ではアクセストークンは常に1時間固定。

### 4.2 プロダクト別推奨設定

| プロダクト | 用途 | refresh_token_expiry_days | 理由 |
|-----------|------|---------------------------|------|
| shinro-compass | 生徒向けポータル | **1**（導入期） | 毎日ログインで習慣化 |
| slide-video | 教職員向けツール | **30** | 利便性重視 |
| test-project | 開発用 | **1** | テスト用に短め |

### 4.3 段階的運用の例（shinro-compass）

| フェーズ | 期間 | refresh_token_expiry_days | ユーザー体験 |
|---------|------|---------------------------|-------------|
| 導入期 | 最初の1〜2ヶ月 | 1 | 毎日ログイン |
| 安定期 | 3ヶ月目以降 | 7 | 週1回ログイン |
| 定着後 | 半年以降 | 30 | 月1回ログイン |

---

## 5. 認証フロー

### 5.1 初回ログイン

```
┌─────────────┐     ┌─────────────────┐     ┌─────────────┐
│ クライアント │     │   認証サーバー   │     │   Google    │
└──────┬──────┘     └────────┬────────┘     └──────┬──────┘
       │                     │                     │
       │  /login/{project}   │                     │
       │────────────────────→│                     │
       │                     │  OAuth認証          │
       │                     │────────────────────→│
       │                     │                     │
       │                     │  認証コード         │
       │                     │←────────────────────│
       │                     │                     │
       │  リダイレクト                             │
       │  ?access_token=xxx                        │
       │  &refresh_token=yyy                       │
       │  &expires_in=3600                         │
       │←────────────────────│                     │
       │                     │                     │
       │  トークンをSession State/LocalStorageに保存
       │                     │                     │
```

### 5.2 トークンリフレッシュ

```
┌─────────────┐     ┌─────────────────┐
│ クライアント │     │   認証サーバー   │
└──────┬──────┘     └────────┬────────┘
       │                     │
       │  API呼び出し        │
       │  (access_token)     │
       │────────────────────→│
       │                     │
       │  401 Unauthorized   │
       │  (トークン期限切れ)  │
       │←────────────────────│
       │                     │
       │  POST /api/refresh  │
       │  {refresh_token: yyy}
       │────────────────────→│
       │                     │
       │                     │  ローテーション処理
       │                     │  ・旧トークンを使用済みに
       │                     │  ・新トークン生成
       │                     │
       │  {                  │
       │    access_token: xxx2,
       │    refresh_token: yyy2,
       │    expires_in: 3600 │
       │  }                  │
       │←────────────────────│
       │                     │
       │  新トークンを保存    │
       │  API再呼び出し      │
       │────────────────────→│
       │                     │
```

### 5.3 リフレッシュトークン期限切れ / 再利用検知

```
┌─────────────┐     ┌─────────────────┐
│ クライアント │     │   認証サーバー   │
└──────┬──────┘     └────────┬────────┘
       │                     │
       │  POST /api/refresh  │
       │  {refresh_token: yyy} (期限切れ or 使用済み)
       │────────────────────→│
       │                     │
       │  401 Unauthorized   │
       │  {                  │
       │    error: "REFRESH_TOKEN_INVALID",
       │    message: "セッションが無効です。再度ログインしてください。"
       │  }                  │
       │←────────────────────│
       │                     │
       │  Session Stateクリア│
       │  /login/{project}へリダイレクト
       │                     │
```

---

## 6. API仕様

### 6.1 認証コールバック（変更）

**エンドポイント**: `GET /callback/{project_id}`

**変更点**:
- アクセストークン（1時間）をquery_paramで返す
- リフレッシュトークンもquery_paramで返す

**レスポンス**:
```
HTTP/1.1 302 Found
Location: {redirect_uri}?access_token={access_token}&refresh_token={refresh_token}&expires_in=3600&state={state}
```

### 6.2 トークンリフレッシュ（変更）

**エンドポイント**: `POST /api/refresh`

**リクエスト**:
```json
{
    "refresh_token": "eyJ...",
    "project_id": "shinro-compass"
}
```

または Authorization ヘッダー:
```
POST /api/refresh HTTP/1.1
Authorization: Bearer {refresh_token}
Content-Type: application/json

{
    "project_id": "shinro-compass"
}
```

**成功レスポンス（200）**:
```json
{
    "access_token": "eyJ...",
    "refresh_token": "eyJ...",
    "token_type": "Bearer",
    "expires_in": 3600
}
```

**エラーレスポンス（401）- 期限切れ**:
```json
{
    "error": "REFRESH_TOKEN_EXPIRED",
    "detail": "Refresh token has expired",
    "message": "セッションの有効期限が切れました。再度ログインしてください。"
}
```

**エラーレスポンス（401）- 再利用検知**:
```json
{
    "error": "REFRESH_TOKEN_REUSED",
    "detail": "Refresh token has already been used",
    "message": "セキュリティ上の理由でログアウトされました。別の場所でログインされた可能性があります。"
}
```

### 6.3 トークン検証（変更なし）

**エンドポイント**: `GET /api/verify`

既存のまま。`token_type` フィールドが追加される。

### 6.4 ログアウト（変更）

**エンドポイント**: `GET /logout`

**変更点**:
- ユーザーの全リフレッシュトークンを無効化（オプション）

---

## 7. 実装詳細

### 7.1 変更対象ファイル

| ファイル | 変更内容 |
|---------|---------|
| `app/config.py` | プロジェクト設定に `refresh_token_expiry_days` 追加 |
| `app/core/jwt_handler.py` | リフレッシュトークン生成・検証・ローテーション |
| `app/core/token_store.py` | **新規**: 使用済みトークン管理 |
| `app/routes/auth.py` | コールバック変更、リフレッシュエンドポイント変更 |
| `app/models/schemas.py` | リクエスト/レスポンススキーマ追加 |

### 7.2 jwt_handler.py の変更

```python
class JWTHandler:
    # 既存メソッド...

    def create_access_token(
        self,
        email: str,
        name: str,
        project_id: str,
        role: Optional[str] = None,
        additional_claims: Optional[Dict] = None
    ) -> str:
        """
        アクセストークン生成（1時間固定）
        """
        now = datetime.utcnow()
        payload = {
            "email": email,
            "name": name,
            "project_id": project_id,
            "token_type": "access",
            "iat": now,
            "exp": now + timedelta(hours=1),  # 1時間固定
            "jti": f"access-{secrets.token_urlsafe(16)}"
        }
        if role:
            payload["role"] = role
        if additional_claims:
            payload.update(additional_claims)

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def create_refresh_token(
        self,
        email: str,
        project_id: str,
        expiry_days: int = 30
    ) -> str:
        """
        リフレッシュトークン生成（プロダクトごとの有効期限）
        """
        now = datetime.utcnow()
        payload = {
            "email": email,
            "project_id": project_id,
            "token_type": "refresh",
            "iat": now,
            "exp": now + timedelta(days=expiry_days),
            "jti": f"refresh-{secrets.token_urlsafe(16)}"
        }

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_refresh_token(self, token: str) -> Dict[str, Any]:
        """
        リフレッシュトークン検証
        """
        payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

        if payload.get("token_type") != "refresh":
            raise ValueError("Invalid token type")

        return payload
```

### 7.3 token_store.py（新規）

```python
"""使用済みトークン管理"""

from typing import Optional, Dict
from datetime import datetime, timedelta
import threading


class TokenStore:
    """
    使用済みリフレッシュトークンを管理

    開発環境: メモリ（辞書）
    本番環境: Firestore（将来実装）
    """

    def __init__(self):
        self._used_tokens: Dict[str, Dict] = {}
        self._lock = threading.Lock()

    async def is_token_used(self, jti: str) -> bool:
        """トークンが使用済みかチェック"""
        with self._lock:
            return jti in self._used_tokens

    async def mark_token_as_used(
        self,
        jti: str,
        email: str,
        project_id: str,
        ip_address: Optional[str] = None
    ) -> None:
        """トークンを使用済みとしてマーク"""
        with self._lock:
            self._used_tokens[jti] = {
                "email": email,
                "project_id": project_id,
                "used_at": datetime.utcnow().isoformat(),
                "ip_address": ip_address
            }

    async def revoke_all_tokens_for_user(
        self,
        email: str,
        project_id: str
    ) -> None:
        """ユーザーの全トークンを無効化（再利用検知時）"""
        # 実装: 該当ユーザーの全てのリフレッシュを拒否するフラグを設定
        pass

    def cleanup_expired(self, max_age_days: int = 31) -> None:
        """古い使用済みトークンを削除"""
        with self._lock:
            cutoff = datetime.utcnow() - timedelta(days=max_age_days)
            self._used_tokens = {
                jti: data for jti, data in self._used_tokens.items()
                if datetime.fromisoformat(data["used_at"]) > cutoff
            }


# シングルトンインスタンス
token_store = TokenStore()
```

### 7.4 auth.py の変更

```python
@router.get("/callback/{project_id}")
async def callback(request: Request, project_id: str, code: str, state: str):
    # ... 既存の認証処理 ...

    # アクセストークン生成（1時間固定）
    access_token = jwt_handler.create_access_token(
        email=user_info['email'],
        name=user_info['name'],
        project_id=project_id,
        role=user_role,
        additional_claims=additional_claims
    )

    # リフレッシュトークン生成（プロダクト設定に基づく）
    refresh_expiry_days = project_config.get('refresh_token_expiry_days', 30)
    refresh_token = jwt_handler.create_refresh_token(
        email=user_info['email'],
        project_id=project_id,
        expiry_days=refresh_expiry_days
    )

    # リダイレクトURLにトークンを含める
    params = {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'expires_in': 3600,
        'token_type': 'Bearer'
    }
    if client_state:
        params['state'] = client_state

    separator = '&' if '?' in client_redirect_uri else '?'
    redirect_url = f"{client_redirect_uri}{separator}{urllib.parse.urlencode(params)}"

    return RedirectResponse(url=redirect_url)


@router.post("/api/refresh", response_model=TokenRefreshResponse)
async def refresh_token(
    request: Request,
    body: RefreshTokenRequest
):
    """
    リフレッシュトークンを使用して新しいトークンを取得

    ローテーション: 使用済みトークンは無効化
    """
    refresh_token = body.refresh_token
    project_id = body.project_id

    try:
        # 1. リフレッシュトークン検証
        payload = jwt_handler.verify_refresh_token(refresh_token)
        jti = payload.get("jti")
        email = payload.get("email")
        token_project_id = payload.get("project_id")

        # project_id の確認
        if project_id and project_id != token_project_id:
            raise HTTPException(status_code=400, detail="Project ID mismatch")

        project_id = token_project_id

        # 2. 使用済みチェック（ローテーション）
        if await token_store.is_token_used(jti):
            # 再利用検知 → セキュリティイベント
            logger.warning(f"Refresh token reuse detected: {email}, {project_id}")
            await firestore_manager.log_audit_event(
                event_type='refresh_token_reuse',
                project_id=project_id,
                user_email=email,
                details={'jti': jti},
                ip_address=request.client.host
            )
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "REFRESH_TOKEN_REUSED",
                    "message": "セキュリティ上の理由でログアウトされました。"
                }
            )

        # 3. 使用済みとしてマーク
        await token_store.mark_token_as_used(
            jti=jti,
            email=email,
            project_id=project_id,
            ip_address=request.client.host
        )

        # 4. プロジェクト設定を取得
        project_config = await project_config_manager.get_project_config(project_id)

        # 5. 新しいアクセストークン生成
        new_access_token = jwt_handler.create_access_token(
            email=email,
            name=payload.get("name", ""),  # リフレッシュトークンにはnameがないので空
            project_id=project_id
        )

        # 6. 新しいリフレッシュトークン生成（ローテーション）
        refresh_expiry_days = project_config.get('refresh_token_expiry_days', 30)
        new_refresh_token = jwt_handler.create_refresh_token(
            email=email,
            project_id=project_id,
            expiry_days=refresh_expiry_days
        )

        # 7. 監査ログ
        await firestore_manager.log_audit_event(
            event_type='token_refresh',
            project_id=project_id,
            user_email=email,
            details={'old_jti': jti},
            ip_address=request.client.host
        )

        return TokenRefreshResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="Bearer",
            expires_in=3600
        )

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "REFRESH_TOKEN_EXPIRED",
                "message": "セッションの有効期限が切れました。再度ログインしてください。"
            }
        )
    except Exception as e:
        logger.error(f"Refresh token error: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
```

---

## 8. セキュリティ考慮事項

### 8.1 トークン漏洩時の被害比較

| シナリオ | 現状（30日JWT） | 新方式 |
|---------|---------------|--------|
| アクセストークン漏洩 | 30日間悪用 | **1時間のみ** |
| リフレッシュトークン漏洩 | - | 設定期間（ただし検知可能） |
| 両方漏洩 | 30日間悪用 | **検知後に無効化可能** |

### 8.2 XSS攻撃への対策

クライアント側でトークンを保持するため、XSS攻撃のリスクは残る。以下の対策を推奨：

- Content Security Policy (CSP) の設定
- 入力のサニタイズ
- 信頼できないスクリプトの実行防止

### 8.3 監査ログ

以下のイベントを記録：

| イベント | 記録内容 |
|---------|---------|
| `token_refresh` | 正常なリフレッシュ |
| `refresh_token_reuse` | 使用済みトークンの再利用（セキュリティアラート） |
| `refresh_token_expired` | 期限切れトークンの使用 |

---

## 9. 後方互換性

### 9.1 既存トークンの扱い

- 既存の30日トークンは、有効期限まで引き続き使用可能
- `token_type` フィールドがないトークンは旧方式として処理

### 9.2 移行期間

1. 新方式をデプロイ
2. 新規ログインユーザーから新方式を適用
3. 既存トークンは期限切れまで有効
4. 最大30日後には全ユーザーが新方式に移行完了

---

## 10. テスト計画

### 10.1 単体テスト

- [ ] アクセストークン生成（1時間有効期限）
- [ ] リフレッシュトークン生成（設定に基づく有効期限）
- [ ] トークン検証（access / refresh 判別）
- [ ] 使用済みトークンの記録・チェック

### 10.2 統合テスト

- [ ] 初回ログイン → 両トークン取得
- [ ] アクセストークン期限切れ → リフレッシュ → 新トークン取得
- [ ] リフレッシュトークン期限切れ → 401エラー → 再ログイン
- [ ] 使用済みトークン再利用 → 401エラー（セキュリティ）
- [ ] ログアウト → トークン無効化

### 10.3 セキュリティテスト

- [ ] 改ざんされたトークンの拒否
- [ ] 期限切れトークンの拒否
- [ ] 異なるproject_idでのリフレッシュ拒否
- [ ] トークンローテーションの動作確認

---

## 11. 実装スケジュール

| フェーズ | 作業内容 | 見積もり |
|---------|---------|---------|
| Phase 1 | jwt_handler.py の拡張 | 1時間 |
| Phase 2 | token_store.py（使用済み管理） | 1時間 |
| Phase 3 | auth.py の変更（コールバック、リフレッシュ） | 2時間 |
| Phase 4 | スキーマ追加、設定追加 | 30分 |
| Phase 5 | テスト | 1.5時間 |
| Phase 6 | ドキュメント更新 | 30分 |
| **合計** | | **6.5時間** |

---

## 12. 関連ドキュメント

- [認証サーバー設計書](./DESIGN.md)
- [API仕様書](../auth_server_api.yaml)
- [クライアント統合ガイド](./INTEGRATION_GUIDE.md)
- [クライアントアプリ修正ガイド](./CLIENT_APP_MODIFICATION_GUIDE.md)
- [プロキシサーバー修正ガイド](./PROXY_SERVER_MODIFICATION_GUIDE.md)
