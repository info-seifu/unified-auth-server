"""API Proxy routes for forwarding requests to API proxy server"""

from typing import Optional, Dict, Any
import logging

from fastapi import APIRouter, Request, HTTPException, Depends, Header
import httpx

from app.config import settings
from app.core.jwt_handler import jwt_handler
from app.core.secret_manager import secret_manager_client
from app.core.hmac_signer import hmac_signer
from app.core.project_config import project_config_manager
from app.core.firestore_client import firestore_manager
from app.core.errors import ClientSecretNotFoundError, APIProxyFailedError
from app.models.schemas import ProxyRequest, ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter()


async def verify_token_dependency(
    authorization: Optional[str] = Header(None, description="Authorization header (Bearer token)")
) -> Dict[str, Any]:
    """
    Dependency to verify JWT token

    Args:
        authorization: Authorization header

    Returns:
        Decoded token payload

    Raises:
        HTTPException: If token is invalid or missing
    """
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(
            status_code=401,
            detail={
                "error": "AUTH_004",
                "detail": "No token provided",
                "message": "Authentication token is required"
            }
        )

    token = authorization[7:]  # Remove "Bearer " prefix

    try:
        payload = jwt_handler.verify_token(token)
        return payload
    except Exception as e:
        logger.warning(f"Token verification failed: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail={
                "error": "AUTH_004",
                "detail": str(e),
                "message": "Invalid token"
            }
        )


@router.post(
    "/api/proxy",
    responses={
        200: {
            "description": "API proxy request successful",
            "content": {
                "application/json": {
                    "example": {
                        "url": "https://example.com/generated-image.png",
                        "revised_prompt": "A professional background image"
                    }
                }
            }
        },
        401: {
            "description": "Authentication failed",
            "model": ErrorResponse
        },
        404: {
            "description": "Client credentials not found",
            "model": ErrorResponse
        },
        502: {
            "description": "API proxy server error",
            "model": ErrorResponse
        }
    },
    summary="Proxy API request",
    description="Forward API request to API proxy server with HMAC signature"
)
async def proxy_request(
    request: Request,
    proxy_req: ProxyRequest,
    token_payload: Dict[str, Any] = Depends(verify_token_dependency)
):
    """
    Proxy API request to API proxy server

    This endpoint:
    1. Verifies the JWT token
    2. Retrieves user's API proxy credentials from Secret Manager
    3. Generates HMAC signature
    4. Forwards request to API proxy server
    5. Returns the response

    The client's API keys are never exposed to the client application.
    """
    email = token_payload.get("email")
    project_id = token_payload.get("project_id")

    if not email or not project_id:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "AUTH_004",
                "detail": "Invalid token payload",
                "message": "Token missing required fields"
            }
        )

    logger.info(f"Proxy request from {email} for project {project_id} to {proxy_req.endpoint}")

    # Get project configuration
    try:
        project_config = await project_config_manager.get_project_config(project_id)
    except Exception as e:
        logger.error(f"Failed to get project config: {str(e)}")
        raise HTTPException(
            status_code=404,
            detail={
                "error": "AUTH_006",
                "detail": f"Project {project_id} not found",
                "message": "Project configuration not found"
            }
        )

    # Check if API proxy is enabled for this project
    if not project_config.get("api_proxy_enabled", False):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "PROXY_003",
                "detail": "API proxy not enabled for this project",
                "message": "API proxy feature is not enabled"
            }
        )

    # Get API proxy credentials for the user
    # 注意: Secret Managerからの取得は非同期処理（awaitが必須）
    # 開発環境では環境変数から、本番環境ではSecret Managerから取得
    credentials = await secret_manager_client.get_api_proxy_credentials_async(email, project_id)

    if not credentials:
        logger.error(f"No API proxy credentials found for {email}")
        raise ClientSecretNotFoundError(email)

    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")

    if not client_id or not client_secret:
        logger.error(f"Invalid credentials for {email}")
        raise ClientSecretNotFoundError(email)

    # Get product_id from project config
    product_id = project_config.get("product_id")
    if not product_id:
        logger.error(f"No product_id configured for project {project_id}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "PROXY_004",
                "detail": "Product ID not configured",
                "message": "Project configuration is incomplete"
            }
        )

    # Generate timestamp
    timestamp = hmac_signer.get_current_timestamp()

    # Determine the full API proxy URL
    # DESIGN.md の標準フォーマット: POST {API_PROXY_SERVER_URL}/v1/chat/{product_id}
    api_proxy_base_url = settings.api_proxy_server_url.rstrip('/')

    # URL構築ロジックを簡素化
    # 1. プレースホルダー {product_id} を置換
    # 2. 絶対パス (/) で始まる場合はそのまま使用
    # 3. それ以外は標準パス /v1/chat/{product_id} を使用
    if "{product_id}" in proxy_req.endpoint:
        request_path = proxy_req.endpoint.replace("{product_id}", product_id)
    elif proxy_req.endpoint.startswith('/'):
        request_path = proxy_req.endpoint
    else:
        # デフォルト: 標準の chat エンドポイント
        request_path = f"/v1/chat/{product_id}"

    # Full URL construction
    full_url = f"{api_proxy_base_url}{request_path}"

    # Create signed headers (URLと同じパスを使用してHMAC署名を生成)
    headers = hmac_signer.create_signed_headers(
        client_id=client_id,
        client_secret=client_secret,
        timestamp=timestamp,
        method="POST",
        path=request_path,  # 重要: full_urlと同じパスを使用
        body=proxy_req.data
    )

    # Log the API call with enhanced details
    from datetime import datetime, timezone
    log_details = {
        'endpoint': proxy_req.endpoint,
        'product_id': product_id,
        'method': proxy_req.method.upper(),
        'request_size': len(str(proxy_req.data)) if proxy_req.data else 0,
        'has_headers': bool(proxy_req.headers),
        'timestamp': datetime.now(timezone.utc).isoformat()
    }

    await firestore_manager.log_audit_event(
        event_type='api_proxy_call',
        project_id=project_id,
        user_email=email,
        details=log_details,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get('user-agent')
    )

    # Forward request to API proxy server
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                full_url,
                headers=headers,
                json=proxy_req.data
            )

            # Check response status
            if response.status_code >= 400:
                logger.error(
                    f"API proxy error: {response.status_code} - {response.text}"
                )
                # セキュリティ: 本番環境では詳細なエラーメッセージを隠す
                from app.config import settings
                if settings.is_development:
                    error_detail = f"API proxy returned {response.status_code}: {response.text[:200]}"
                else:
                    error_detail = f"API proxy returned status {response.status_code}"
                raise APIProxyFailedError(error_detail)

            # Return the response from API proxy
            logger.info(f"API proxy request successful for {email}")
            return response.json()

    except httpx.RequestError as e:
        logger.error(f"Failed to connect to API proxy: {str(e)}")
        raise APIProxyFailedError(f"Failed to connect to API proxy: {str(e)}")
    except Exception as e:
        logger.error(f"API proxy request failed: {str(e)}")
        raise APIProxyFailedError(str(e))