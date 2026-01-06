"""Tests for HMAC signature generation"""

import hashlib
import hmac
import json
from app.core.hmac_signer import HMACSignatureGenerator


def test_hmac_signature_matches_api_proxy():
    """
    認証サーバーの署名がAPIプロキシサーバーの検証ロジックと一致することを確認

    このテストは、APIプロキシサーバー（api-key-server）の検証ロジックと
    認証サーバーの署名生成ロジックが一致することを保証します。

    APIプロキシサーバーの検証ロジック（api-key-server/app/auth.py Line 68-72）:
    ```python
    def _calculate_hmac_signature(secret: str, timestamp: str, method: str, path: str, body: bytes) -> str:
        body_hash = hashlib.sha256(body).hexdigest()
        message = f"{timestamp}\\n{method.upper()}\\n{path}\\n{body_hash}"
        mac = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256)
        return mac.hexdigest()
    ```
    """
    # テストデータ
    client_secret = "test-secret"
    timestamp = "1234567890"
    method = "post"  # 小文字で渡す（実際のHTTPリクエストでは小文字の場合がある）
    path = "/v1/chat/product-SlideVideo"
    body = {
        "model": "claude-3-sonnet",
        "messages": [{"role": "user", "content": "test"}]
    }

    # 認証サーバー側の署名生成
    auth_signature = HMACSignatureGenerator.generate_signature(
        client_secret=client_secret,
        timestamp=timestamp,
        method=method,
        path=path,
        body=body
    )

    # APIプロキシサーバー側の検証ロジックを再現
    body_bytes = json.dumps(body, sort_keys=True, separators=(',', ':')).encode()
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    message = f"{timestamp}\n{method.upper()}\n{path}\n{body_hash}"  # method.upper()が重要
    api_proxy_signature = hmac.new(
        client_secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    # 署名が一致することを確認
    assert auth_signature == api_proxy_signature, \
        f"Signature mismatch: auth={auth_signature}, proxy={api_proxy_signature}"


def test_hmac_signature_with_uppercase_method():
    """
    HTTPメソッドが既に大文字の場合でも正しく動作することを確認
    """
    client_secret = "test-secret"
    timestamp = "1234567890"
    method = "POST"  # 大文字で渡す
    path = "/v1/images/generate/product-SlideVideo"
    body = {
        "model": "dall-e-3",
        "prompt": "A beautiful sunset",
        "n": 1,
        "size": "1024x1024"
    }

    # 認証サーバー側の署名生成
    auth_signature = HMACSignatureGenerator.generate_signature(
        client_secret=client_secret,
        timestamp=timestamp,
        method=method,
        path=path,
        body=body
    )

    # APIプロキシサーバー側の検証ロジックを再現
    body_bytes = json.dumps(body, sort_keys=True, separators=(',', ':')).encode()
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    message = f"{timestamp}\n{method.upper()}\n{path}\n{body_hash}"
    api_proxy_signature = hmac.new(
        client_secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    # 署名が一致することを確認
    assert auth_signature == api_proxy_signature


def test_hmac_signature_with_empty_body():
    """
    空のボディでも正しく署名が生成されることを確認
    """
    client_secret = "test-secret"
    timestamp = "1234567890"
    method = "get"
    path = "/v1/models"
    body = {}

    # 認証サーバー側の署名生成
    auth_signature = HMACSignatureGenerator.generate_signature(
        client_secret=client_secret,
        timestamp=timestamp,
        method=method,
        path=path,
        body=body
    )

    # APIプロキシサーバー側の検証ロジックを再現
    body_bytes = json.dumps(body, sort_keys=True, separators=(',', ':')).encode()
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    message = f"{timestamp}\n{method.upper()}\n{path}\n{body_hash}"
    api_proxy_signature = hmac.new(
        client_secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    # 署名が一致することを確認
    assert auth_signature == api_proxy_signature


def test_create_signed_headers():
    """
    create_signed_headers メソッドが正しいヘッダーを生成することを確認
    """
    client_id = "test-client-id"
    client_secret = "test-secret"
    timestamp = "1234567890"
    method = "post"
    path = "/v1/chat/product-Test"
    body = {"test": "data"}

    headers = HMACSignatureGenerator.create_signed_headers(
        client_id=client_id,
        client_secret=client_secret,
        timestamp=timestamp,
        method=method,
        path=path,
        body=body
    )

    # 必要なヘッダーが含まれていることを確認
    assert "X-Client-ID" in headers
    assert "X-Signature" in headers
    assert "X-Timestamp" in headers
    assert "Content-Type" in headers

    # 値が正しいことを確認
    assert headers["X-Client-ID"] == client_id
    assert headers["X-Timestamp"] == timestamp
    assert headers["Content-Type"] == "application/json"

    # 署名が正しいことを確認
    expected_signature = HMACSignatureGenerator.generate_signature(
        client_secret=client_secret,
        timestamp=timestamp,
        method=method,
        path=path,
        body=body
    )
    assert headers["X-Signature"] == expected_signature
