"""Firestoreにプロジェクト設定を初期化するスクリプト"""

import os
import sys

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.cloud import firestore

# GCPプロジェクトID
PROJECT_ID = "interview-api-472500"

# Firestoreに登録するプロジェクト設定
PROJECT_CONFIGS = {
    "test-project": {
        "name": "テストプロジェクト",
        "type": "streamlit_local",
        "description": "開発用テストプロジェクト",
        "allowed_domains": ["i-seifu.jp", "i-seifu.ac.jp", "gmail.com"],
        "student_allowed": False,
        "admin_emails": [],
        "required_groups": [],
        "allowed_groups": [],
        "required_org_units": [],
        "allowed_org_units": [],
        "redirect_uris": ["http://localhost:8501/", "http://localhost:3000/callback"],
        "token_delivery": "query_param",
        "token_expiry_days": 30,
        "api_proxy_enabled": True,
        "product_id": "product-TestProject"
    },
    "slide-video": {
        "name": "スライド動画生成システム",
        "type": "streamlit_local",
        "description": "PowerPointから動画を生成するツール",
        "allowed_domains": ["i-seifu.jp", "i-seifu.ac.jp"],
        "student_allowed": False,
        "admin_emails": [],
        "required_groups": [],
        "allowed_groups": [],
        "required_org_units": [],
        "allowed_org_units": [],
        "redirect_uris": ["http://localhost:8501/"],
        "token_delivery": "query_param",
        "token_expiry_days": 30,
        "api_proxy_enabled": True,
        "product_id": "product-SlideVideo",
        "api_proxy_credentials_path": "projects/xxx/secrets/slidevideo-users"
    },
    "group-ou-test": {
        "name": "グループ・OU認証テスト",
        "type": "streamlit_local",
        "description": "Google Workspaceグループと組織部門のテスト用プロジェクト",
        "allowed_domains": ["i-seifu.jp", "i-seifu.ac.jp"],
        "student_allowed": False,
        "admin_emails": [],
        "required_groups": [],
        "allowed_groups": ["staff@i-seifu.jp"],
        "required_org_units": [],
        "allowed_org_units": [],
        "redirect_uris": ["http://localhost:8501/", "http://localhost:3000/callback"],
        "token_delivery": "query_param",
        "token_expiry_days": 30,
        "api_proxy_enabled": False
    }
}


def init_firestore():
    """Firestoreにプロジェクト設定を初期化"""
    print(f"Firestoreに接続中... (project: {PROJECT_ID})")

    # Firestoreクライアントを初期化
    db = firestore.Client(project=PROJECT_ID)

    # プロジェクト設定を登録
    collection_ref = db.collection("project_configs")

    for project_id, config in PROJECT_CONFIGS.items():
        print(f"  登録中: {project_id}")
        doc_ref = collection_ref.document(project_id)
        doc_ref.set(config)
        print(f"    -> 完了: {config['name']}")

    print(f"\n合計 {len(PROJECT_CONFIGS)} 件のプロジェクト設定を登録しました。")


def list_firestore_configs():
    """Firestoreのプロジェクト設定を一覧表示"""
    print(f"Firestoreのプロジェクト設定を確認中... (project: {PROJECT_ID})")

    db = firestore.Client(project=PROJECT_ID)
    collection_ref = db.collection("project_configs")

    docs = collection_ref.stream()

    print("\n登録済みプロジェクト:")
    count = 0
    for doc in docs:
        count += 1
        data = doc.to_dict()
        print(f"  - {doc.id}: {data.get('name', 'N/A')}")
        if data.get('allowed_groups'):
            print(f"      allowed_groups: {data['allowed_groups']}")
        if data.get('allowed_org_units'):
            print(f"      allowed_org_units: {data['allowed_org_units']}")

    print(f"\n合計: {count} 件")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Firestore プロジェクト設定管理")
    parser.add_argument("--list", action="store_true", help="設定を一覧表示")
    parser.add_argument("--init", action="store_true", help="設定を初期化")

    args = parser.parse_args()

    if args.list:
        list_firestore_configs()
    elif args.init:
        init_firestore()
    else:
        print("使用方法:")
        print("  python scripts/init_firestore.py --init   # 設定を初期化")
        print("  python scripts/init_firestore.py --list   # 設定を一覧表示")
