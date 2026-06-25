# プロジェクト AI ガイド（統合認証サーバー）

> 統合認証サーバー専用の AI 向けルール集。共通ルール（`~/.claude/CLAUDE.md`）に加えて、
> **コードを見ても分からないこのプロジェクト固有の前提・ルール**だけをここに書く。
> 詳細な設計・手順は `docs/` 配下を参照（後述のポインタ）。

---

## 1. プロジェクト概要

- **目的**: Google OAuth 2.0 による統一認証 + JWT発行/検証 + APIプロキシ中継（client_secret秘匿化）
- **アクセス制御**: ドメイン / 学生 / グループ / 組織部門の4軸でプロジェクト別に制御
- **利用元**: 複数の Streamlit / Web アプリ（情政府高校の教職員・学生向け）

---

## 2. 技術スタック

- **言語/FW**: Python 3.9+ / FastAPI 0.104.1（async/await 必須）
- **主要ライブラリ**: PyJWT 2.8.0・Authlib 1.3.0・google-cloud-firestore 2.14.0・
  google-cloud-secret-manager 2.17.0・httpx 0.25.2・pydantic 2.5.2
- **外部サービス**: Google OAuth 2.0 / Firestore（設定・監査ログ）/ Secret Manager（本番の機密情報）/ APIプロキシサーバー
- バージョンの正は `requirements.txt`。ライブラリ追加・変更は理由と代替案を添えて提案してから。

---

## 3. ディレクトリ構成ルール

- `app/core/`: 認証・JWT・バリデーション等のコア機能
- `app/routes/`: APIエンドポイント定義（FastAPIルーター）。新エンドポイントはここに追加
- `app/models/schemas.py`: Pydanticスキーマ（request/response）
- `app/config.py`: 環境設定
- `.env`: 機密情報（**コミット禁止**、.gitignore済み）。サービスアカウントJSONも同様
- `docs/`: 設計書・各種手順書（下記ポインタ参照）

---

## 4. コーディング規約（固有部分のみ）

既存コードのスタイルに合わせることを最優先。その上で以下を守る。

- **非同期**: I/O を伴う処理は `async def` + `await`。同期ブロッキングを async 内に入れない
- **型ヒント必須**: `Dict[str, Any]`, `Optional[str]` 等を完全に記述
- **import順序**: 標準ライブラリ → サードパーティ → ローカル
- **エンドポイント**: `response_model` を必ず指定し、`responses={...}` でエラー時スキーマも宣言。
  認証が要るものは `Depends(verify_token_dependency)` を使う
- **エラーレスポンスは統一形式**（HTTPException の detail）:
  ```python
  detail={"error": "AUTH_004", "detail": str(e), "message": "ユーザー向けメッセージ"}
  ```
- **例外は握りつぶさない**。予期せぬ例外は `logger.error(..., exc_info=True)` でスタックトレースを残す

---

## 5. 実装完了時のチェック

```bash
# 構文チェック（macOS / 現在の作業ディレクトリで実行）
python -m py_compile app/**/*.py

# 型チェック（任意）
mypy app/ --ignore-missing-imports

# Lint（ruff 設定あり: .ruff_cache）
ruff check app/
```

よくあるエラー: import順序（E402）/ 型ヒント不足 / 未使用import（F401）/
`await` を async 外で使用 / Pydantic ValidationError → `Field()` で既定値と検証を設定。

---

## 6. ロギング（必須ログポイント）

| 処理 | レベル | 記録内容 |
|------|--------|----------|
| ログイン成功 | INFO | email, project_id |
| ログイン失敗 | WARNING | email, reason, ip_address |
| トークン発行 | INFO | email, project_id, expiry |
| トークン検証エラー | WARNING | error_type, detail |
| APIプロキシ呼び出し | INFO | email, endpoint, product_id |
| APIプロキシ/Secret Manager エラー | ERROR | status_code/secret_name, error |

- **機密情報（secret, トークン本体, client_secret）はログに出さない**
- デバッグログ（`logger.debug`）はコミット前に削除
- Firestore 監査ログは非同期書き込み。失敗しても本処理は継続させる

---

## 7. セキュリティ・固有仕様

機密情報は環境変数（開発）/ Secret Manager（本番）から取得。**ハードコーディング禁止**。

固有の判定ルール（コードレビュー・実装時の基準）:

- **許可ドメイン**: `@i-seifu.jp`, `@i-seifu.ac.jp`
- **学生アカウント判定**: ローカル部が8桁数字（`12345678@domain`）
- **JWT有効期限**: 30日。検証時に expiry チェック必須
- **APIプロキシ**: HMAC-SHA256署名の生成/検証。タイムアウト60秒。エラー時に機密情報を漏らさない
- **CORS**: 許可オリジンは `.env` の `CORS_ORIGINS` で管理

パフォーマンス目安: トークン検証 100ms以内 / OAuth callback 2秒以内 / プロキシ 外部応答+500ms以内。

---

## 8. テスト・動作確認

```bash
pytest tests/            # テスト（tests/ 配下）
python test_setup.py     # 環境確認
python run_dev.py        # 開発サーバー起動

# 手動確認: http://localhost:8000/{login/test-project, docs, health}
```

ビジネスロジック追加時はテストもセットで提案する。

---

## 9. Cloud Run デプロイ（運用事故防止のため厳守）

**環境変数・シークレットを消さないこと。** デプロイ時のオプション:

| オプション | 動作 | 可否 |
|-----------|------|------|
| `--set-env-vars` / `--set-secrets` | 既存を全上書き | ❌ **禁止** |
| `--update-env-vars` / `--update-secrets` | 追加・更新のみ | ✅ 推奨 |
| 指定なし | 既存を保持 | ✅ OK |

```bash
# コードのみ更新（env/secret は保持される）— 標準デプロイ
gcloud run deploy unified-auth-server \
  --project=interview-api-472500 --region=asia-northeast1 --source=.

# env/secret を追加・更新する場合
gcloud run deploy unified-auth-server \
  --project=interview-api-472500 --region=asia-northeast1 --source=. \
  --update-env-vars=NEW_VAR=value --update-secrets=NEW_SECRET=secret-name:latest

# 現在の設定確認
gcloud run services describe unified-auth-server \
  --project=interview-api-472500 --region=asia-northeast1 \
  --format="yaml(spec.template.spec.containers[0])"
```

シークレットのマウント（初回のみ）: `GOOGLE_CLIENT_ID`→`google-client-id` /
`GOOGLE_CLIENT_SECRET`→`google-client-secret` / `JWT_SECRET_KEY`→`jwt-secret-key`（いずれも `:latest`）。

デプロイ後の確認:
```bash
curl https://unified-auth-server-856773980753.asia-northeast1.run.app/health
# 期待: {"status":"healthy","environment":"production","debug":false}
```

詳細手順は `docs/DEPLOY_CLOUDRUN.md` / `docs/SETUP_AUTO_DEPLOY.md` を参照。

---

## 10. レビュー重点観点（このプロジェクト）

通常のレビュー（共通ルール準拠）に加え、以下を必ず確認:

- **OAuth/JWT**: secret のハードコーディング無し / expiry チェック / CORS設定
- **アクセス制御**: ドメイン判定・学生判定（8桁）・プロジェクト設定ベースの制御・管理者権限チェック
- **APIプロキシ**: HMAC署名の生成/検証 / client_id・secret マッピング / タイムアウト / 機密漏洩防止
- **非同期**: ブロッキング処理の混入が無いか / httpx を非同期で使っているか
- **監査ログ**: ログイン成否・API呼び出しが記録され、機密が含まれず、Firestore障害時にフォールバックするか

---

## 11. 詳細ドキュメントへのポインタ（docs/）

困ったら新規に書かず、まず該当ドキュメントを参照・更新する。

| 内容 | ファイル |
|------|----------|
| 設計全体 | `docs/DESIGN.md` |
| Cloud Runデプロイ / 自動デプロイ | `docs/DEPLOY_CLOUDRUN.md`, `SETUP_AUTO_DEPLOY.md` |
| 環境変数一覧 | `ENVIRONMENT_VARIABLES.md` |
| クライアントアプリ連携 | `docs/INTEGRATION_GUIDE.md`, `CLIENT_APP_MODIFICATION_GUIDE.md` |
| プロキシサーバー変更 | `docs/PROXY_SERVER_MODIFICATION_GUIDE.md` |
| リフレッシュトークン設計 | `docs/REFRESH_TOKEN_DESIGN.md` |
| タイムアウト設定 | `docs/TIMEOUT_CONFIGURATION.md` |
| 過去のコードレビュー結果 | `docs/CODE_REVIEW_REPORT.md` |
| API仕様(OpenAPI) | `auth_server_api.yaml` |

---

### 更新履歴

- 2024-12-10: 初版作成（Phase 1, 2実装完了時点）
- 2024-12-15: コードレビュー観点を追加
- 2025-01-06: Cloud Runデプロイ注意事項を追加
- 2026-06-02: 全体スリム化（660行→約190行）。長いコード例・チェックリスト・トラブルシュートは
  `docs/` へ委譲し、固有ルールに集約。古いWindowsパスを除去。
