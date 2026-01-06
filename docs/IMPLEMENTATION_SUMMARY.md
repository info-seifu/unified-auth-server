# 実装サマリー: Google Workspace グループ・組織部門認証

## 📅 実装日時
2025-12-11

## 🎯 実装内容
Google Workspaceのグループメンバーシップと組織部門（OU）によるアクセス制御機能を実装しました。

---

## ✅ 実装された機能

### 1. Google Workspace Admin SDK統合

#### 新規ファイル: `app/core/workspace_admin.py`
- **WorkspaceAdminClient クラス**
  - `get_user_groups()`: ユーザーが属するグループのリストを取得
  - `get_user_org_unit()`: ユーザーの組織部門パスを取得
  - `check_org_unit_hierarchy()`: 階層的なOU検証ロジック

#### 実装の特徴
- Cloud Run環境での動作を前提に、OAuth2アクセストークンを使用
- サービスアカウントではなく、ユーザー認証のアクセストークンでAdmin APIを呼び出し
- 権限不足時は空リスト/Noneを返し、エラーで停止しない設計

---

### 2. OAuth スコープの追加

#### 変更ファイル: `app/core/oauth.py`
```python
'scope': 'openid email profile '
         'https://www.googleapis.com/auth/admin.directory.group.readonly '
         'https://www.googleapis.com/auth/admin.directory.user.readonly'
```

#### 変更内容
- `handle_callback()` メソッドの返り値を変更
  - 変更前: `Dict[str, Any]` (user_infoのみ)
  - 変更後: `Tuple[Dict[str, Any], str]` (user_info, access_token)
- アクセストークンを返すことで、Admin SDK APIの呼び出しが可能に

---

### 3. 検証ロジックの実装

#### 変更ファイル: `app/core/validators.py`

##### 新規関数: `validate_org_unit_membership()`
```python
def validate_org_unit_membership(
    user_org_unit: Optional[str],
    required_org_units: List[str],
    allowed_org_units: List[str]
) -> Tuple[bool, Optional[str]]
```

- 必須OU（`required_org_units`）のANDチェック
- 許可OU（`allowed_org_units`）のORチェック
- 階層的検証のサポート（例: `/教職員/専任教員` → `/教職員` にマッチ）

##### 更新関数: `validate_user_access()`
```python
def validate_user_access(
    email: str,
    project_config: Dict[str, Any],
    user_groups: Optional[List[str]] = None,  # 追加
    user_org_unit: Optional[str] = None       # 追加
) -> Tuple[bool, str]
```

- グループと組織部門の検証を統合
- 既存の検証（ドメイン、学生、管理者）との組み合わせ

---

### 4. 認証フローへの統合

#### 変更ファイル: `app/routes/auth.py`

##### `/callback/{project_id}` エンドポイントの更新

**グループ・OU情報の取得:**
```python
# プロジェクト設定にグループまたはOU検証が含まれている場合のみ取得
if (project_config.get('required_groups') or
    project_config.get('allowed_groups') or
    project_config.get('required_org_units') or
    project_config.get('allowed_org_units')):

    if access_token:
        # グループ情報の取得
        if project_config.get('required_groups') or project_config.get('allowed_groups'):
            user_groups = await workspace_admin_client.get_user_groups(
                access_token, user_info['email']
            )

        # 組織部門情報の取得
        if project_config.get('required_org_units') or project_config.get('allowed_org_units'):
            user_org_unit = await workspace_admin_client.get_user_org_unit(
                access_token, user_info['email']
            )
```

**検証の実行:**
```python
validate_user_access(
    user_info['email'],
    project_config,
    user_groups=user_groups,      # グループリストを渡す
    user_org_unit=user_org_unit   # 組織部門パスを渡す
)
```

**監査ログへの記録:**
- 成功時・失敗時ともに、グループとOU情報を記録

---

### 5. エラーハンドリングの拡張

#### 変更ファイル: `app/core/errors.py`

##### 新規エラークラス
```python
class OrgUnitMembershipRequiredError(AuthError):
    """ユーザーが必須の組織部門に所属していない"""
    error_code = "AUTH_009"

class NoMatchingOrgUnitError(AuthError):
    """ユーザーが許可された組織部門に所属していない"""
    error_code = "AUTH_010"
```

---

## 🔧 依存関係の追加

### `requirements.txt`
```python
google-api-python-client==2.111.0  # Google Admin SDK for groups and org units
```

---

## 📊 プロジェクト設定フィールド

### Firestore スキーマ（既存から変更なし）

```python
projects/{project_id} = {
    # 既存フィールド
    "name": str,
    "type": str,
    "allowed_domains": [str],
    "student_allowed": bool,
    "admin_emails": [str],

    # グループベース認証（既存定義を活用）
    "required_groups": [str],      # AND条件: 全て必須
    "allowed_groups": [str],       # OR条件: いずれか許可

    # 組織部門ベース認証（既存定義を活用）
    "required_org_units": [str],   # AND条件: 全て必須
    "allowed_org_units": [str],    # OR条件: いずれか許可

    # 以下、既存フィールド
    "redirect_uris": [str],
    "token_delivery": str,
    "token_expiry_days": int,
    "api_proxy_enabled": bool,
    "product_id": str,
    ...
}
```

---

## 🧪 テスト方法

### 1. 基本動作確認

#### テストプロジェクトの設定例
```python
# Firestore: projects/group-ou-test
{
    "name": "グループ・OU認証テスト",
    "type": "streamlit_local",
    "allowed_domains": ["i-seifu.jp", "i-seifu.ac.jp"],
    "student_allowed": False,

    # グループ検証
    "required_groups": [],
    "allowed_groups": ["teachers@i-seifu.jp", "staff@i-seifu.jp"],

    # 組織部門検証
    "required_org_units": [],
    "allowed_org_units": ["/教職員"],

    "redirect_uris": ["http://localhost:8501/"],
    "token_delivery": "query_param",
    "token_expiry_days": 30,
    "api_proxy_enabled": False
}
```

#### 動作確認手順
1. 開発サーバーを起動: `python run_dev.py`
2. ログインURL: `http://localhost:8000/login/group-ou-test`
3. Google認証を実行
4. ログを確認:
   ```
   INFO: Retrieved 3 groups for user@i-seifu.jp
   INFO: Retrieved org unit '/教職員/専任教員' for user@i-seifu.jp
   INFO: User user@i-seifu.jp passed all validation checks
   ```

### 2. 検証パターン

#### パターン1: グループメンバーシップのみ
```python
"allowed_groups": ["teachers@i-seifu.jp"]
# → ユーザーが teachers@i-seifu.jp に所属していれば許可
```

#### パターン2: 組織部門のみ
```python
"allowed_org_units": ["/教職員"]
# → /教職員 または /教職員/専任教員 などの子OUに所属していれば許可
```

#### パターン3: グループと組織部門の組み合わせ
```python
"required_groups": ["research-team@i-seifu.jp"],
"required_org_units": ["/教職員/専任教員"]
# → 両方の条件を満たす必要がある
```

#### パターン4: 複数グループのOR条件
```python
"allowed_groups": [
    "teachers@i-seifu.jp",
    "staff@i-seifu.jp",
    "administrators@i-seifu.jp"
]
# → いずれかのグループに所属していれば許可
```

---

## ⚠️ 注意事項

### 1. Google Workspace Admin API の権限

#### 必要な権限
ユーザーがAdmin SDK APIを呼び出すには、以下のいずれかが必要です:
- Google Workspace の**管理者権限**（Super Admin または Delegated Admin）
- カスタムロールで Directory API の読み取り権限

#### 権限不足の場合の動作
- `get_user_groups()` → 空リスト `[]` を返す
- `get_user_org_unit()` → `None` を返す
- エラーログに警告を出力: `"Insufficient permissions to list groups for {email}"`
- 検証は続行され、グループ・OU条件がある場合は失敗する

### 2. OAuth スコープの再同意

新しいスコープを追加したため、既存ユーザーは再度OAuth同意画面が表示されます:
- `https://www.googleapis.com/auth/admin.directory.group.readonly`
- `https://www.googleapis.com/auth/admin.directory.user.readonly`

### 3. 階層的な組織部門の検証

組織部門は階層構造を持ちます:
```
/教職員
├── /教職員/専任教員
└── /教職員/非常勤講師
```

**検証の動作:**
- ユーザーのOU: `/教職員/専任教員`
- 許可OU: `/教職員`
- 結果: ✅ マッチ（子OUなので許可）

**実装:**
```python
# app/core/workspace_admin.py
def check_org_unit_hierarchy(self, user_org_unit: str, allowed_org_unit: str) -> bool:
    user_path = user_org_unit.rstrip('/')
    allowed_path = allowed_org_unit.rstrip('/')

    # Exact match
    if user_path == allowed_path:
        return True

    # Check if user's org unit is a child of allowed org unit
    if user_path.startswith(allowed_path + '/'):
        return True

    return False
```

---

## 🔍 デバッグ方法

### ログの確認

#### 成功時のログ例
```
INFO: OAuth successful for user: teacher@i-seifu.jp
INFO: Retrieved 2 groups for teacher@i-seifu.jp
INFO: Retrieved org unit '/教職員/専任教員' for teacher@i-seifu.jp
INFO: User teacher@i-seifu.jp passed all validation checks
INFO: Login successful: user=teacher@i-seifu.jp, project=group-ou-test
```

#### 失敗時のログ例（グループ不一致）
```
WARNING: User is not a member of any allowed groups: teachers@i-seifu.jp
ERROR: Login failed for student@i-seifu.jp: AUTH_008
```

#### 失敗時のログ例（OU不一致）
```
WARNING: User is not a member of any allowed organizational units: /教職員
ERROR: Login failed for student@i-seifu.jp: AUTH_010
```

---

## 📝 今後の拡張可能性

### 1. 管理画面でのグループ・OU選択
- Firestoreに保存されているプロジェクト設定をGUIで編集
- Google Workspace APIからグループリスト・OU階層を取得して選択可能に

### 2. グループ・OUキャッシュ
- 頻繁にアクセスされるグループ・OU情報をキャッシュ
- Redis等を使用してパフォーマンス向上

### 3. 動的グループ検証
- メールアドレスのパターンで動的にグループを判定
- 例: `*@students.i-seifu.jp` → 自動的に学生グループとして扱う

---

## 🚀 デプロイ前のチェックリスト

- [ ] `google-api-python-client` がインストールされている
- [ ] OAuth スコープが正しく設定されている
- [ ] プロジェクト設定に `required_groups` / `allowed_groups` / `required_org_units` / `allowed_org_units` フィールドが存在する
- [ ] テストプロジェクトで動作確認済み
- [ ] エラーハンドリングが適切に動作することを確認
- [ ] 監査ログにグループ・OU情報が記録されることを確認
- [ ] 権限不足の場合でもエラーで停止しないことを確認

---

## 📄 関連ドキュメント

- [DESIGN.md](./DESIGN.md) - システム全体の設計書
- [auth_server_api.yaml](./auth_server_api.yaml) - OpenAPI仕様書
- [README.md](./README.md) - プロジェクト概要

---

## 🔗 実装されたファイル一覧

### 新規ファイル
- `app/core/workspace_admin.py` - Google Workspace Admin SDK クライアント

### 変更ファイル
- `app/core/oauth.py` - OAuth スコープ追加、アクセストークン返却
- `app/core/validators.py` - OU検証ロジック、validate_user_access更新
- `app/core/errors.py` - AUTH_009, AUTH_010 エラークラス追加
- `app/routes/auth.py` - グループ・OU取得と検証の統合
- `requirements.txt` - google-api-python-client 追加

---

**実装完了日**: 2025-12-11
**ブランチ**: `feature/workspace-group-ou-auth`
**実装者**: Claude Code (AI Assistant)
