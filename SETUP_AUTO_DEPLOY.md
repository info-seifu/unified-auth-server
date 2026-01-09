# 自動デプロイ設定手順書

> **目的**: GitHub の master ブランチへのプッシュ時に、Cloud Run へ自動的にデプロイする

---

## 前提条件

- Google Cloud Platform アカウント
- プロジェクト: `interview-api-472500`
- gcloud CLI がインストール済み
- Cloud Build API が有効
- 必要な権限:
  - Cloud Build Editor
  - Cloud Run Admin
  - Service Account User

---

## 1. Cloud Build API の有効化

```bash
# プロジェクトIDを設定
export PROJECT_ID=interview-api-472500

# Cloud Build API を有効化
gcloud services enable cloudbuild.googleapis.com --project=$PROJECT_ID
gcloud services enable run.googleapis.com --project=$PROJECT_ID
```

---

## 2. Cloud Build サービスアカウントへの権限付与

Cloud Build がCloud Run にデプロイできるよう、権限を付与します。

```bash
# Cloud Build のサービスアカウントを取得
export PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
export CLOUD_BUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

# Cloud Run Admin ロールを付与
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${CLOUD_BUILD_SA}" \
  --role="roles/run.admin"

# Service Account User ロールを付与（Cloud Run がサービスアカウントとして実行するため）
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${CLOUD_BUILD_SA}" \
  --role="roles/iam.serviceAccountUser"
```

---

## 3. GitHub リポジトリの接続

Google Cloud Console でGitHub リポジトリを接続します。

### 3.1 Cloud Console でリポジトリ接続

1. [Cloud Build - トリガー](https://console.cloud.google.com/cloud-build/triggers) にアクセス
2. 「トリガーを作成」をクリック
3. 「リポジトリを選択」→「GitHub に接続」
4. GitHub アカウントで認証
5. リポジトリ `info-seifu/unified-auth-server` を選択

### 3.2 または gcloud コマンドで接続

```bash
# GitHub App 経由でリポジトリを接続
gcloud alpha builds connections create github unified-auth-server-connection \
  --region=asia-northeast1

# リポジトリをリンク
gcloud alpha builds repositories create unified-auth-server-repo \
  --remote-uri=https://github.com/info-seifu/unified-auth-server.git \
  --connection=unified-auth-server-connection \
  --region=asia-northeast1
```

---

## 4. Cloud Build トリガーの作成

### 4.1 Cloud Console での作成（推奨）

1. [Cloud Build - トリガー](https://console.cloud.google.com/cloud-build/triggers) にアクセス
2. 「トリガーを作成」をクリック
3. 以下の設定を入力:

| 項目 | 設定値 |
|-----|--------|
| **名前** | `unified-auth-server-deploy` |
| **説明** | `master ブランチへのプッシュ時に Cloud Run へ自動デプロイ` |
| **イベント** | ブランチにプッシュ |
| **リポジトリ** | `info-seifu/unified-auth-server` |
| **ブランチ** | `^master$` （正規表現） |
| **構成** | Cloud Build 構成ファイル（yaml または json） |
| **Cloud Build 構成ファイルの場所** | `/cloudbuild.yaml` |
| **サービスアカウント** | デフォルト（Cloud Build サービスアカウント） |

4. 「作成」をクリック

### 4.2 gcloud コマンドでの作成

```bash
gcloud builds triggers create github \
  --name="unified-auth-server-deploy" \
  --description="master ブランチへのプッシュ時に Cloud Run へ自動デプロイ" \
  --repo-name="unified-auth-server" \
  --repo-owner="info-seifu" \
  --branch-pattern="^master$" \
  --build-config="cloudbuild.yaml" \
  --region=global \
  --project=$PROJECT_ID
```

---

## 5. 動作確認

### 5.1 手動でトリガーを実行

```bash
# トリガー一覧を確認
gcloud builds triggers list --project=$PROJECT_ID

# 手動で実行（テスト）
gcloud builds triggers run unified-auth-server-deploy \
  --branch=master \
  --project=$PROJECT_ID
```

### 5.2 GitHub へプッシュして確認

```bash
# テスト用コミットを作成
git commit --allow-empty -m "test: Cloud Build トリガーのテスト"

# master ブランチへプッシュ
git push origin master
```

### 5.3 ビルドログの確認

```bash
# 最新のビルドログを確認
gcloud builds list --project=$PROJECT_ID --limit=5

# 特定のビルドの詳細を確認
gcloud builds log <BUILD_ID> --project=$PROJECT_ID
```

または、[Cloud Build - 履歴](https://console.cloud.google.com/cloud-build/builds) で確認

---

## 6. トラブルシューティング

### 6.1 権限エラー

```
ERROR: (gcloud.builds.submit) PERMISSION_DENIED: The caller does not have permission
```

**解決策**: Cloud Build サービスアカウントに必要な権限を付与（手順2を参照）

### 6.2 環境変数が消える問題

**重要**: `cloudbuild.yaml` では `--set-env-vars` や `--set-secrets` を使用していません。
これにより、既存の環境変数とシークレット設定が保持されます。

新しい環境変数を追加する場合:

```yaml
# cloudbuild.yaml の deploy ステップに追加
- '--update-env-vars=NEW_VAR=value'
```

### 6.3 デプロイ失敗時の確認

```bash
# Cloud Run のログを確認
gcloud run services logs read unified-auth-server \
  --region=asia-northeast1 \
  --project=$PROJECT_ID \
  --limit=50
```

---

## 7. 環境変数の管理

### 7.1 現在の環境変数を確認

```bash
gcloud run services describe unified-auth-server \
  --region=asia-northeast1 \
  --project=$PROJECT_ID \
  --format="yaml(spec.template.spec.containers[0].env)"
```

### 7.2 環境変数を追加・更新する場合

**方法1: Cloud Console で手動更新**
1. [Cloud Run - unified-auth-server](https://console.cloud.google.com/run) にアクセス
2. 「新しいリビジョンの編集とデプロイ」をクリック
3. 「変数とシークレット」タブで環境変数を追加・編集

**方法2: gcloud コマンドで更新**

```bash
# 環境変数を追加（既存は保持）
gcloud run services update unified-auth-server \
  --region=asia-northeast1 \
  --project=$PROJECT_ID \
  --update-env-vars="NEW_VAR=value"
```

**方法3: cloudbuild.yaml に記述（非推奨）**

環境変数が多い場合、cloudbuild.yaml に記述するとメンテナンスが煩雑になるため、
Secret Manager または Cloud Console での管理を推奨します。

---

## 8. セキュリティのベストプラクティス

### 8.1 シークレットの管理

機密情報は必ず Secret Manager で管理:

```bash
# シークレットの確認
gcloud secrets list --project=$PROJECT_ID

# シークレットの値を確認（注意: 本番環境では実行しない）
gcloud secrets versions access latest --secret="jwt-secret-key" --project=$PROJECT_ID
```

### 8.2 Cloud Build ログの確認

Cloud Build のログには環境変数の値が表示される場合があるため、
シークレットは必ず Secret Manager 経由で参照してください。

---

## 9. ロールバック手順

デプロイに失敗した場合や、前のバージョンに戻したい場合:

```bash
# リビジョン一覧を確認
gcloud run revisions list \
  --service=unified-auth-server \
  --region=asia-northeast1 \
  --project=$PROJECT_ID

# 特定のリビジョンにトラフィックを切り替え
gcloud run services update-traffic unified-auth-server \
  --to-revisions=<REVISION_NAME>=100 \
  --region=asia-northeast1 \
  --project=$PROJECT_ID
```

---

## 10. 自動デプロイの無効化

自動デプロイを一時的に無効化する場合:

```bash
# トリガーを無効化
gcloud builds triggers update unified-auth-server-deploy \
  --disabled \
  --project=$PROJECT_ID

# トリガーを再度有効化
gcloud builds triggers update unified-auth-server-deploy \
  --no-disabled \
  --project=$PROJECT_ID
```

---

## まとめ

- ✅ master ブランチへのプッシュで自動デプロイ
- ✅ 既存の環境変数・シークレット設定を保持
- ✅ ビルド時間: 約5-10分
- ✅ ロールバック可能

**作成日**: 2026-01-09
**対象バージョン**: unified-auth-server v1.0.0
