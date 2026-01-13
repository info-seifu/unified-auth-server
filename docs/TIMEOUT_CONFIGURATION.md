# タイムアウト設定ガイド

> 最終更新: 2026-01-13
> 関連システム: Unified Auth Server, API Proxy Server

## 📋 目次

- [概要](#概要)
- [現在の設定値](#現在の設定値)
- [設定の理由](#設定の理由)
- [タイムアウトの階層構造](#タイムアウトの階層構造)
- [設定変更の手順](#設定変更の手順)
- [トラブルシューティング](#トラブルシューティング)
- [変更履歴](#変更履歴)

---

## 概要

このドキュメントは、Unified Auth ServerとAPI Proxy Server間のAPI通信におけるタイムアウト設定の指針を定めます。

### 基本方針

**シンプルさと一貫性を重視**
- アプリ内部のタイムアウトは**240秒で統一**
- Cloud Runのタイムアウトは**300秒で統一**
- 複雑な階層設定は避け、2層構造を維持

---

## 現在の設定値

### 1. Unified Auth Server

| 設定項目 | 設定値 | 設定箇所 |
|---------|--------|---------|
| Cloud Run タイムアウト | 300秒 | `cloudbuild.yaml:34` |
| アプリ内部タイムアウト | 240秒 | `cloudbuild.yaml:37` (環境変数 `PROXY_TIMEOUT_SECONDS`) |

### 2. API Proxy Server

| 設定項目 | 設定値 | 設定箇所 |
|---------|--------|---------|
| Cloud Run タイムアウト | 300秒 | `cloudbuild.yaml:19` |
| アプリ内部タイムアウト | 240秒 | `cloudbuild.yaml:18` (環境変数 `API_KEY_SERVER_REQUEST_TIMEOUT_SECONDS`) |

### 3. クライアントアプリケーション

| 設定項目 | 設定値 | 備考 |
|---------|--------|------|
| デフォルトタイムアウト | 300秒 | `auth_client.py:150` |
| 推奨設定 | 設定不要 | デフォルト値を使用 |

---

## 設定の理由

### なぜ240秒で統一したのか

#### 当初の経緯
- 初期設定: 認証サーバー 60秒、API Proxy Server 90秒
- 長いシナリオ処理でタイムアウト発生
- 段階的に延長: 60秒 → 280秒（認証サーバー）、90秒 → 240秒（API Proxy）

#### 統一の判断
**2026-01-13に以下の理由で240秒に統一：**

1. **シンプルさ**: 280秒と240秒の中途半端な差が不要
2. **バッチ処理の改善**: 現在は処理を分割しており、280秒は不要
3. **一貫性**: 「アプリのタイムアウトは240秒」と覚えやすい
4. **十分なバッファ**: Cloud Run（300秒）との60秒差で十分

### なぜCloud Runは300秒なのか

- **最終防衛線**: アプリが240秒でタイムアウトしたエラーレスポンスを返す余裕（60秒）
- **エラーハンドリング**: 内側でタイムアウトし、外側で適切なエラーを返せる
- **リソース保護**: 完全にハングした場合の最終的な制限

---

## タイムアウトの階層構造

```
【2層構造（シンプル版）】

外側（インフラレベル）: Cloud Run = 300秒
    ↑ 最終防衛線
    ↑ アプリがエラーを返す余裕（60秒）
    ↓
内側（アプリレベル）: 統一 = 240秒
    ├─ 認証サーバー → API Proxy Server: 240秒
    │   ↑ httpx.AsyncClient(timeout=settings.proxy_timeout_seconds)
    │   ↑ app/routes/proxy.py:261
    │
    └─ API Proxy Server → 外部API: 240秒
        ↑ httpx.AsyncClient(timeout=settings.request_timeout_seconds)
        ↑ app/upstream.py:66,73,80
```

### タイムアウト発生時の流れ

```
【正常系】
外部APIが60秒で応答
    ↓
API Proxy Serverが処理（数秒）
    ↓
認証サーバーが処理（数秒）
    ↓
クライアントがレスポンス受信
合計: 約65秒 ✅

【タイムアウト系】
外部APIが240秒応答なし
    ↓ 240秒後
API Proxy Serverがタイムアウト
    ↓ エラーレスポンス返却（数秒）
    ↓
認証サーバーがエラー受信
    ↓ クライアントにエラー転送（数秒）
    ↓
クライアントがエラー受信
合計: 約245秒
Cloud Run制限（300秒）: 55秒の余裕 ✅
```

---

## 設定変更の手順

### タイムアウトを延長する必要がある場合

#### ケース1: アプリ内部のタイムアウト延長（240秒 → X秒）

**変更が必要な理由の例:**
- 外部APIの処理時間が恒常的に240秒を超える
- バッチ処理で大量データを扱う必要がある

**手順:**

1. **Cloud Runタイムアウトを確認**
   - 新しいタイムアウト値 + 60秒のバッファ ≦ Cloud Runタイムアウト
   - 例: 新タイムアウト270秒の場合、270 + 60 = 330秒必要
   - Cloud Runタイムアウトが300秒の場合、先に延長が必要

2. **両方のcloudbuild.yamlを修正**

   ```yaml
   # auth-server/cloudbuild.yaml
   - '--timeout=360s'  # 新タイムアウト + 60秒バッファ
   - '--update-env-vars=PROXY_TIMEOUT_SECONDS=270'  # 新タイムアウト
   ```

   ```yaml
   # api-key-server/cloudbuild.yaml
   - '--timeout=360s'  # 同じ値
   - '--set-env-vars=...API_KEY_SERVER_REQUEST_TIMEOUT_SECONDS=270'  # 新タイムアウト
   ```

3. **Git コミット & プッシュ**
   ```bash
   git commit -m "chore: タイムアウトを240秒→270秒に延長"
   git push
   ```

4. **自動デプロイを確認**
   - Cloud Build Triggerが発火
   - 両サービスがデプロイされることを確認

#### ケース2: Cloud Runタイムアウトのみ延長

**通常は不要です。** アプリ内部のタイムアウト + 60秒で設定してください。

### タイムアウトを短縮する場合

**変更前に以下を確認:**
- [ ] 既存のAPI呼び出しが新しいタイムアウト内に収まるか
- [ ] 本番環境でのAPIレスポンス時間を計測済みか
- [ ] 段階的にロールバック可能か

**手順は延長と同じですが、より慎重に。**

---

## 設定のベストプラクティス

### ✅ 推奨

1. **アプリ内部のタイムアウトは統一する**
   - 認証サーバー = API Proxy Server = 240秒
   - 異なる値にする明確な理由がない限り統一

2. **Cloud Runタイムアウトはアプリより60秒長く**
   - エラーレスポンスを返す余裕を確保
   - 300秒（アプリ240秒 + バッファ60秒）

3. **クライアントアプリはデフォルト値を使用**
   - timeout引数を指定しない（デフォルト300秒）
   - 特別な理由がある場合のみ明示的に設定

4. **設定変更時は両方のサービスを同時に更新**
   - 認証サーバーとAPI Proxy Serverの設定値を揃える
   - 片方だけ変更すると予期しない動作の原因になる

### ❌ 避けるべき

1. **中途半端な差分**
   - 280秒と240秒のような微妙な差は避ける
   - 明確な理由がない限り統一

2. **頻繁な変更**
   - タイムアウトは一度設定したら変更しない前提
   - 頻繁に変更が必要な場合はアーキテクチャを見直す

3. **過度に長いタイムアウト**
   - 600秒（10分）を超える場合は非同期処理を検討
   - Cloud Tasks、Pub/Sub、ポーリング方式などを検討

4. **Secret Managerでの管理**
   - タイムアウトは機密情報ではない
   - cloudbuild.yamlで明示的に管理

---

## トラブルシューティング

### 問題1: 504 Gateway Timeout

**症状:**
```
504 Server Error: Gateway Timeout
detail: upstream request timeout
```

**原因診断:**

1. **どこでタイムアウトしたか特定**
   ```bash
   # ログを確認
   gcloud logging read "resource.type=cloud_run_revision AND severity>=ERROR" --limit 50 --format json
   ```

2. **タイムアウト時間を確認**
   ```bash
   # 認証サーバー
   gcloud run services describe unified-auth-server --region=asia-northeast1 --format="value(spec.template.spec.timeoutSeconds)"

   # API Proxy Server
   gcloud run services describe api-key-server --region=asia-northeast1 --format="value(spec.template.spec.timeoutSeconds)"
   ```

3. **環境変数を確認**
   ```bash
   # 認証サーバー
   gcloud run services describe unified-auth-server --region=asia-northeast1 --format="yaml(spec.template.spec.containers[0].env)" | grep TIMEOUT

   # API Proxy Server
   gcloud run services describe api-key-server --region=asia-northeast1 --format="yaml(spec.template.spec.containers[0].env)" | grep TIMEOUT
   ```

**解決策:**

- **API処理が240秒を超える**: タイムアウトの延長を検討（上記手順参照）
- **Cloud Run設定とcloudbuild.yamlの不一致**: 再デプロイ実行

### 問題2: デプロイ後に環境変数が消える

**原因:**
- `--set-env-vars`を使用すると既存の環境変数が上書きされる

**解決策:**
- `--update-env-vars`を使用（認証サーバー）
- `--set-env-vars`で全ての環境変数を列挙（API Proxy Server）

**cloudbuild.yamlの正しい書き方:**

```yaml
# 認証サーバー: update-env-vars で追加のみ
- '--update-env-vars=PROXY_TIMEOUT_SECONDS=240'

# API Proxy Server: set-env-vars で全て列挙
- '--set-env-vars=USE_SECRET_MANAGER=true,API_KEY_SERVER_GCP_PROJECT_ID=$PROJECT_ID,API_KEY_SERVER_MAX_TOKENS=8192,API_KEY_SERVER_REQUEST_TIMEOUT_SECONDS=240'
```

### 問題3: タイムアウト設定を変更したのに反映されない

**原因:**
- Cloud Buildが実行されていない
- キャッシュされた古いイメージを使用している

**解決策:**

1. **Cloud Buildの実行確認**
   ```bash
   gcloud builds list --limit=5
   ```

2. **手動で再デプロイ**
   ```bash
   # 認証サーバー
   gcloud builds submit --config=cloudbuild.yaml
   ```

3. **現在のデプロイ設定を確認**
   ```bash
   gcloud run services describe unified-auth-server --region=asia-northeast1
   ```

---

## 関連ドキュメント

- [Cloud Run タイムアウト公式ドキュメント](https://cloud.google.com/run/docs/configuring/request-timeout)
- [API Proxy Server 設計書](../api-key-server/README.md)
- [認証フロー](./AUTHENTICATION.md)

---

## 変更履歴

### 2026-01-13: タイムアウト統一（240秒）

**変更内容:**
- 認証サーバーのタイムアウトを280秒 → 240秒に統一
- Cloud Runタイムアウトを60秒 → 300秒に延長
- ドキュメント作成

**理由:**
- シンプルさと一貫性の向上
- バッチ処理の分割により280秒が不要に
- 60秒のバッファで十分なエラーハンドリング

**変更箇所:**
- `cloudbuild.yaml:34`: `--timeout=300s`
- `cloudbuild.yaml:37`: `PROXY_TIMEOUT_SECONDS=240`

**影響:**
- なし（既存の処理は全て240秒以内に完了）

### 2025-XX-XX: 初期設定

**初期値:**
- 認証サーバー: 60秒
- API Proxy Server: 90秒

---

## 付録：タイムアウト設計の考え方

### 多層防御の原則

タイムアウトは「内側ほど短く」設定することで、適切なエラーハンドリングを実現します。

```
【悪い例】
Cloud Run: 240秒
    ↓
アプリ: 300秒 ❌ Cloud Runが先にタイムアウト
    ↓
外部API

→ アプリがエラーを返せず、Cloud Runが強制終了

【良い例】
Cloud Run: 300秒
    ↓
アプリ: 240秒 ✅ アプリが先にタイムアウト
    ↓
外部API

→ アプリが適切にエラーレスポンスを返せる
```

### バッファの考え方

**60秒のバッファで十分な理由:**

1. **エラーレスポンスの返却**: 数秒
2. **ネットワーク遅延**: 数秒
3. **ログ記録・クリーンアップ**: 数秒
4. **予期しない遅延**: 50秒の余裕

**計算例:**
```
アプリタイムアウト: 240秒
エラー処理: 5秒
Cloud Runへの返却: 245秒
Cloud Run制限: 300秒
余裕: 55秒 ✅
```

### 長時間処理への対応

240秒を超える処理が必要な場合の代替案:

1. **非同期処理（推奨）**
   - Cloud Tasks でジョブキュー
   - Pub/Sub でイベント駆動
   - ポーリング方式（クライアントが定期的にステータス確認）

2. **処理の分割**
   - 大きな処理を小さく分割
   - バッチ処理で並列実行
   - ストリーミング処理

3. **タイムアウトの延長**
   - 最終手段として検討
   - 600秒（10分）を超える場合はアーキテクチャを見直す

---

## 質問・フィードバック

このドキュメントに関する質問や改善提案は、以下に連絡してください:

- プロジェクトオーナー: h.hamada@i-seifu.jp
- GitHub Issues: [認証サーバーリポジトリ]

---

**最終更新**: 2026-01-13
**次回見直し**: 必要に応じて（タイムアウト設定変更時）
