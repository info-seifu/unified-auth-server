# 統合認証サーバー (Authentication Server)

複数のStreamlitプロジェクトで使用する統合認証サーバー。

## 機能

- **Google OAuth認証**: Google Workspaceアカウントでの認証
- **プロジェクト別アクセス制御**: プロジェクトごとに異なるアクセスルール
- **JWTトークン発行**: 安全なトークンベース認証
- **APIプロキシ中継**: client_secretを秘匿化してAPIプロキシサーバーに転送

## API仕様

詳細は [auth_server_api.yaml](auth_server_api.yaml) を参照してください。

## エンドポイント

- `GET /login/{project_id}` - Google OAuth認証開始
- `GET /callback/{project_id}` - OAuth認証完了後のコールバック
- `GET /api/verify` - トークン検証
- `POST /api/proxy` - APIプロキシへの中継

## 開発環境

- Python 3.9+
- Flask または FastAPI
- Google OAuth 2.0

## 実装予定

1. Phase 1: 基本的な認証フロー
   - Google OAuth統合
   - トークン発行
   - プロジェクト別設定

2. Phase 2: APIプロキシ統合
   - `/api/proxy` エンドポイント実装
   - client_secret管理
   - HMAC署名生成

## 関連プロジェクト

- **APIプロキシサーバー**: `C:\Users\濱田英樹\Documents\dev\api-key-server\api-key-server`
- **クライアント（スライド動画生成）**: `C:\Users\濱田英樹\Documents\dev\SlideMovie\sogo-slide-local-video`

## セットアップ

（実装後に記載）
