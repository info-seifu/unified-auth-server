# プロジェクト AI ガイド（統合認証サーバー）

> このファイルは、**統合認証サーバー専用の AI 向けルール集**です。
> 共通ルール（`~/.claude/AI_COMMON_RULES.md`）に加えて、このプロジェクト固有の前提・例外・開発規約を定義します。

---

## 1. プロジェクト概要

- **プロジェクト名**: 統合認証サーバー (Unified Auth Server)
- **概要**:
  - Google OAuth 2.0による統一認証
  - プロジェクト別アクセス制御（ドメイン、学生、グループ、組織部門）
  - JWTトークンの発行・検証
  - APIプロキシ中継機能（client_secret秘匿化）
  - 複数のStreamlit/Webアプリケーションで利用可能
- **想定ユーザー**:
  - 情政府高校の教職員・学生
  - Streamlitアプリケーション開発者
  - システム管理者

---

## 2. 技術スタック（このプロジェクト専用）

### 2.1 フレームワーク・言語
- **言語**: Python 3.9+
- **フレームワーク**: FastAPI 0.104.1
- **主要ライブラリ**:
  - PyJWT 2.8.0 (JWT処理)
  - Authlib 1.3.0 (OAuth統合)
  - google-cloud-firestore 2.14.0 (プロジェクト設定)
  - google-cloud-secret-manager 2.17.0 (機密情報管理)
  - httpx 0.25.2 (非同期HTTPクライアント)
  - pydantic 2.5.2 (データバリデーション)

### 2.2 外部API・サービス
- **Google OAuth 2.0**: ユーザー認証
- **Google Cloud Firestore**: プロジェクト設定・監査ログ
- **Google Secret Manager**: 機密情報管理（本番環境）
- **APIプロキシサーバー**: 外部API呼び出しの中継

### 2.3 認証・セキュリティ
- **認証方式**: Google OAuth 2.0 + JWT
- **セキュリティ対策**:
  - HMAC-SHA256署名
  - JWTトークン（30日有効期限）
  - ドメインベースアクセス制御
  - CORS設定
  - 環境変数による機密情報管理

> AI への指示：
> 「このプロジェクトでは FastAPI + Python 3.9+ を使用します。
> 新しい機能追加時は既存のアーキテクチャパターンに従ってください。
> 非同期処理（async/await）を適切に使用してください。」

---

## 3. ディレクトリ構成ルール

```text
auth-server/
├── app/                    # アプリケーション本体
│   ├── __init__.py
│   ├── config.py          # 環境設定
│   ├── main.py           # FastAPIアプリケーション
│   ├── core/             # コア機能
│   │   ├── errors.py     # エラー定義
│   │   ├── firestore_client.py
│   │   ├── hmac_signer.py
│   │   ├── jwt_handler.py
│   │   ├── oauth.py      # Google OAuth
│   │   ├── project_config.py
│   │   ├── secret_manager.py
│   │   └── validators.py
│   ├── models/           # データモデル
│   │   └── schemas.py    # Pydanticスキーマ
│   └── routes/           # APIルート
│       ├── auth.py       # 認証エンドポイント
│       └── proxy.py      # プロキシエンドポイント
├── tests/                # テストコード（未実装）
├── .claude/              # AI向けルール
├── .env.example         # 環境変数サンプル
├── requirements.txt     # Pythonパッケージ
├── run_dev.py          # 開発サーバー起動
├── test_setup.py       # 初期セットアップテスト
├── DESIGN.md           # 設計書
├── auth_server_api.yaml # OpenAPI仕様
└── README.md           # プロジェクト説明

```

### ディレクトリに関するルール

- `app/core/`: 認証・JWT・バリデーション等のコア機能
- `app/routes/`: APIエンドポイント定義（FastAPIルーター）
- `app/models/`: Pydanticモデル（リクエスト/レスポンススキーマ）
- `.env`: 環境変数設定（絶対にコミットしない、.gitignoreで除外済み）
- `.claude/`: AI向けのプロジェクト固有ルール

> AI への指示例：
> 「新しいエンドポイントはapp/routes/以下に配置し、
> コア機能はapp/core/以下に実装してください。
> Pydanticスキーマはapp/models/schemas.pyに追加してください。」

---

## 4. コーディング規約（このプロジェクト専用）

### 4.1 Python コーディングスタイル

```python
# ✅ 良い例：型ヒント付き非同期関数
from typing import Dict, Any, Optional
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)

async def process_auth_request(
    email: str,
    project_id: str,
    user_groups: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    認証リクエストを処理する

    Args:
        email: ユーザーのメールアドレス
        project_id: プロジェクトID
        user_groups: ユーザーが属するグループリスト

    Returns:
        認証結果を含む辞書

    Raises:
        HTTPException: 認証エラー時
    """
    try:
        # 実装
        logger.info(f"Processing auth for {email} in project {project_id}")
        result = await validate_user_access(email, project_id)
        return result
    except Exception as e:
        logger.error(f"Auth processing failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=401, detail=str(e))
```

### 4.2 プロジェクト固有のパターン

#### FastAPI エンドポイントパターン
```python
@router.get(
    "/api/endpoint",
    response_model=ResponseSchema,  # 必ず response_model を指定
    responses={
        200: {"description": "成功", "model": ResponseSchema},
        401: {"description": "認証エラー", "model": ErrorResponse},
        404: {"description": "Not Found", "model": ErrorResponse}
    },
    summary="エンドポイントの概要",
    description="詳細な説明"
)
async def endpoint_handler(
    param: str = Query(..., description="パラメータの説明"),
    token_payload: Dict[str, Any] = Depends(verify_token_dependency)
):
    """docstring でも説明を記載"""
    pass
```

#### エラーレスポンスパターン
```python
# 統一されたエラーレスポンス形式
raise HTTPException(
    status_code=401,
    detail={
        "error": "AUTH_004",  # エラーコード
        "detail": str(e),     # 詳細情報
        "message": "User-friendly message"  # ユーザー向けメッセージ
    }
)
```

---

## 5. ビルド・リンタエラー解消ルール

### 5.1 実装完了時の必須チェック

実装完了後、以下のコマンドを実行してエラーがないことを確認：

```bash
# 構文チェック
python -m py_compile app/**/*.py

# 型チェック（オプション）
mypy app/ --ignore-missing-imports

# import順序の確認
# - 標準ライブラリ
# - サードパーティライブラリ
# - ローカルモジュール

# 実際のチェックコマンド例
cd c:\Users\濱田英樹\Documents\dev\auth-server
python -c "import ast; files = ['app/main.py', 'app/config.py', 'app/routes/auth.py', 'app/routes/proxy.py', 'app/core/oauth.py', 'app/core/jwt_handler.py', 'app/core/validators.py', 'app/core/firestore_client.py', 'app/core/project_config.py', 'app/core/errors.py', 'app/core/secret_manager.py', 'app/core/hmac_signer.py', 'app/models/schemas.py']; [ast.parse(open(f, encoding='utf-8').read()) for f in files]; print('All files passed syntax check')"
```

### 5.2 よくあるエラーと対処法

| エラー種別 | 例 | 対処法 |
|-----------|-----|--------|
| Import順序 | `E402 module level import not at top of file` | 標準→サードパーティ→ローカルの順に整理 |
| 型ヒント不足 | `Missing type hints` | `Dict[str, Any]`, `Optional[str]`等を追加 |
| 未使用import | `F401 imported but unused` | 削除または `# noqa: F401` を追加 |
| async/await | `SyntaxError: 'await' outside async function` | 関数を `async def` に変更 |
| Pydantic | `ValidationError` | Field()でデフォルト値と検証を設定 |

### 5.3 プロジェクト固有の除外設定

```python
# pyproject.toml (将来的に追加予定)
[tool.black]
line-length = 120
target-version = ['py39']

[tool.isort]
profile = "black"
line_length = 120

# .flake8 (将来的に追加予定)
[flake8]
max-line-length = 120
exclude = __pycache__, .venv, migrations/
ignore = E203, W503  # blackと互換性のため
```

> AI への指示：
> 「実装完了時は必ず構文チェックを実行し、すべてのエラーと警告を解消してください。
> import文は標準ライブラリ→サードパーティ→ローカルの順に整理し、
> 型ヒントを完全に記述してください。」

---

## 6. エラーハンドリング・ロギング

### 6.1 エラーハンドリングパターン

```python
# 基本的なエラーハンドリング（認証サーバー用）
from app.core.errors import InvalidDomainError, StudentNotAllowedError
import logging

logger = logging.getLogger(__name__)

try:
    # Google OAuth処理
    user_info = await google_oauth_handler.handle_callback(
        request, code, state, project_id
    )

    # ドメイン検証
    validate_user_access(user_info['email'], project_config)

except InvalidDomainError as e:
    # 監査ログ記録
    await firestore_manager.log_audit_event(
        event_type='login_failed',
        project_id=project_id,
        user_email=user_info['email'],
        details={'reason': 'invalid_domain'},
        ip_address=request.client.host
    )
    logger.warning(f"Invalid domain access attempt: {user_info['email']}")
    raise HTTPException(status_code=403, detail=e.detail)

except Exception as e:
    logger.error(f"Unexpected error in auth: {str(e)}", exc_info=True)
    raise HTTPException(
        status_code=500,
        detail={
            "error": "INTERNAL_ERROR",
            "message": "認証処理中にエラーが発生しました"
        }
    )
```

### 6.2 プロジェクト固有のログ設定

#### 必須のログポイント

| 処理 | ログレベル | 記録内容 |
|------|----------|----------|
| ユーザーログイン成功 | INFO | email, project_id, timestamp |
| ユーザーログイン失敗 | WARNING | email, reason, ip_address |
| トークン発行 | INFO | email, project_id, expiry |
| トークン検証エラー | WARNING | error_type, detail |
| APIプロキシ呼び出し | INFO | email, endpoint, product_id |
| APIプロキシエラー | ERROR | status_code, error_detail |
| Secret Manager エラー | ERROR | secret_name, error |

#### ログ出力例

```python
# 認証成功
logger.info(f"Login successful: user={email}, project={project_id}")

# APIプロキシ呼び出し
logger.info(f"Proxy request: user={email}, endpoint={endpoint}, product={product_id}")

# エラーログ（スタックトレース付き）
logger.error(f"API proxy failed: status={status}, error={error}", exc_info=True)

# デバッグログ（コミット前に削除）
logger.debug(f"[DEBUG] OAuth state: {state}")  # TODO: Remove before commit
```

---

## 7. セキュリティ・認証ルール

### 7.1 APIキー・秘密情報の管理

```python
# ✅ 良い例：環境変数とSecret Manager
from app.config import settings
from app.core.secret_manager import secret_manager_client

# 開発環境：環境変数から取得
if settings.is_development:
    oauth_creds = {
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret
    }
else:
    # 本番環境：Secret Managerから取得
    oauth_creds = secret_manager_client.get_oauth_credentials()

# ❌ 悪い例：ハードコーディング
client_secret = "GOCSPX-xxxxxxxxxxxx"  # 絶対にやらない
```

### 7.2 認証・認可の実装

```python
# JWTトークン検証の依存関数
async def verify_token_dependency(
    authorization: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """Bearer トークンを検証"""
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=401, detail="Token required")

    token = authorization[7:]
    try:
        payload = jwt_handler.verify_token(token)
        return payload
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

# エンドポイントでの使用
@router.post("/api/proxy")
async def proxy_request(
    request: Request,
    proxy_req: ProxyRequest,
    token_payload: Dict[str, Any] = Depends(verify_token_dependency)
):
    email = token_payload.get("email")
    # 認証済みユーザーとして処理
```

---

## 8. テスト方針

### 8.1 テスト実行方法

```bash
# 単体テスト（将来実装予定）
pytest tests/unit/

# 統合テスト（将来実装予定）
pytest tests/integration/

# 開発環境での動作確認
python test_setup.py  # 環境確認
python run_dev.py     # サーバー起動

# 手動テスト用URL
# 1. ログイン: http://localhost:8000/login/test-project
# 2. API Docs: http://localhost:8000/docs
# 3. 健全性確認: http://localhost:8000/health
```

### 8.2 重要なテスト項目

- Google OAuth フロー（モック使用）
- JWTトークン発行・検証
- ドメイン検証（@i-seifu.jp, @i-seifu.ac.jp）
- 学生アカウント判定（8桁数字@domain）
- APIプロキシのHMAC署名生成
- エラーレスポンスの形式
- CORS設定の動作

---

## 9. AI への依頼テンプレート（このプロジェクト専用）

このプロジェクトで AI にコードを書いてもらうときの依頼例：

```text
あなたは FastAPI + Python 3.9+ を使用した統合認証サーバーの
開発アシスタントです。

共通ルール（~/.claude/AI_COMMON_RULES.md）に加えて、
次のプロジェクト固有ルールを守ってください：
- FastAPIの async/await を適切に使用
- Pydanticスキーマで型安全性を確保
- HTTPExceptionは統一形式（error, detail, message）で返す
- import順序は標準→サードパーティ→ローカル
- 実装完了後は構文チェックでエラーゼロを確認

【依頼内容】
[具体的なタスク]

コード提示後、以下を確認してください：
1. 構文エラーの有無
2. 型ヒントの完全性
3. import順序の適切性
4. エラーハンドリングの実装
```

---

## 10. プロジェクト固有の注意事項

### 10.1 フレームワークの制約
- FastAPIは自動的にPydanticモデルからOpenAPIドキュメントを生成
- 非同期関数（async def）内では await を使用
- Dependsを使った依存性注入パターンを活用

### 10.2 API利用制限
- Google OAuth: レート制限あり（1分あたり20リクエスト程度）
- Secret Manager: 読み取り専用、キャッシュ推奨
- Firestore: 監査ログは非同期で書き込み（エラーでも処理継続）

### 10.3 パフォーマンス要件
- トークン検証: 100ms以内
- OAuth callback: 2秒以内
- APIプロキシ: 外部API応答時間 + 500ms以内

---

## 11. デバッグ・トラブルシューティング

### 11.1 よくある問題と解決策

| 問題 | 原因 | 解決策 |
|------|------|--------|
| `ModuleNotFoundError` | パッケージ未インストール | `pip install -r requirements.txt` |
| OAuth redirect_uri_mismatch | Google Console設定不一致 | 開発: `http://localhost:8000/callback/{project_id}` を追加 |
| JWT signature verification failed | SECRET_KEY不一致 | `.env`の`JWT_SECRET_KEY`を確認 |
| CORS error | オリジン未許可 | `.env`の`CORS_ORIGINS`にURLを追加 |
| Secret Manager 403 | 権限不足 | サービスアカウントに`Secret Manager Secret Accessor`ロールを付与 |

### 11.2 デバッグ方法

```python
# 環境変数でデバッグモード設定
# .env
DEBUG=true
LOG_LEVEL=DEBUG

# コード内でのデバッグ
if settings.debug:
    logger.debug(f"OAuth state: {request.session}")
    logger.debug(f"Token payload: {payload}")

# FastAPI自動ドキュメント
# http://localhost:8000/docs でAPIテスト可能
```

---

## 12. プロジェクト固有のコードレビュー観点

### 12.1 認証サーバー特有のセキュリティチェック

#### OAuth/JWT関連
- [ ] JWT_SECRET_KEYがハードコーディングされていないか
- [ ] Google OAuth client_secretが直接コード内に記載されていないか
- [ ] JWTトークンの有効期限が適切か（デフォルト30日）
- [ ] トークン検証でexpiry checkが実装されているか
- [ ] CORS設定が適切か（allowed_originsの確認）

#### アクセス制御
- [ ] ドメイン検証ロジックが正しいか（@i-seifu.jp, @i-seifu.ac.jp）
- [ ] 学生アカウント判定が正しいか（8桁数字パターン）
- [ ] プロジェクト設定に基づくアクセス制御が機能しているか
- [ ] 管理者限定エンドポイントの権限チェック

#### APIプロキシ
- [ ] HMAC署名の生成・検証が正しいか
- [ ] client_id/client_secretのマッピングが適切か
- [ ] プロキシリクエストのタイムアウト設定（60秒）
- [ ] エラー時の機密情報漏洩防止

### 12.2 FastAPI固有のチェックポイント

#### 非同期処理
- [ ] async/awaitが適切に使用されているか
- [ ] 非同期関数内でブロッキング処理をしていないか
- [ ] httpxを使った非同期HTTPリクエスト

#### エンドポイント設計
- [ ] Pydanticモデルでのrequest/response検証
- [ ] 適切なHTTPステータスコード
- [ ] OpenAPI仕様との整合性
- [ ] Dependsを使った依存性注入の活用

### 12.3 監査ログ関連

- [ ] ログイン成功/失敗が記録されているか
- [ ] API呼び出しが記録されているか
- [ ] 機密情報がログに含まれていないか
- [ ] Firestoreが利用できない場合のフォールバック

### 12.4 レビュー実施例（認証サーバー用）

```bash
# 新しい認証エンドポイント追加時
"app/routes/auth.pyの新しいエンドポイントをレビューして。
特にOAuth処理とトークン発行のセキュリティを重点的に確認"

# APIプロキシ機能の変更時
"app/routes/proxy.pyのHMAC署名処理をレビューして。
署名の生成と検証が正しく実装されているか確認"

# バリデーション追加時
"app/core/validators.pyの新しいバリデーション関数をレビューして。
エッジケースとエラーハンドリングを確認"
```

### 12.5 Phase別チェックリスト

#### Phase 1（基本認証）
- [ ] Google OAuth統合の実装確認
- [ ] JWTトークンの生成・検証
- [ ] プロジェクト設定の読み込み

#### Phase 2（APIプロキシ）
- [ ] Secret Manager統合
- [ ] HMAC署名の実装
- [ ] プロキシリクエストの転送

#### Phase 3（監査ログ）
- [ ] Firestoreへのログ書き込み
- [ ] ログ検索・フィルタリング
- [ ] 統計情報の集計
- [ ] 古いログの削除処理

> AI への指示：
> 「認証サーバーのコードをレビューする際は、上記のプロジェクト固有観点も
> 必ず確認し、セキュリティと認証フローに特に注意を払ってください。」

---

## 13. このファイルの運用ルール

- 新エンドポイント追加時: セクション3, 4, 12を更新
- エラーパターン発見時: セクション11.1に追記
- 外部サービス追加時: セクション2.2を更新
- レビュー観点追加時: セクション12を更新

---

### 更新履歴

- 2024-12-10: 初版作成（Phase 1, 2実装完了時点）
- 2024-12-15: プロジェクト固有のコードレビュー観点を追加（セクション12）