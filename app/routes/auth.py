"""Authentication routes"""

from fastapi import APIRouter, Request, Query, HTTPException, Header
from fastapi.responses import RedirectResponse
from typing import Optional
import logging
import urllib.parse
import jwt as pyjwt

from app.config import settings
from app.core.oauth import google_oauth_handler
from app.core.jwt_handler import jwt_handler
from app.core.project_config import project_config_manager
from app.core.validators import validate_user_access, validate_redirect_uri
from app.core import validators  # Import validators module for is_student_email()
from app.core.firestore_client import firestore_manager
from app.core.workspace_admin import workspace_admin_client
from app.core.errors import ProjectNotFoundError
from app.core.token_store import token_store
from app.models.schemas import UserInfo, ErrorResponse, TokenResponse, RefreshTokenRequest, TokenRefreshResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/login/{project_id}")
async def login(
    request: Request,
    project_id: str,
    redirect_uri: Optional[str] = Query(None),
    state: Optional[str] = Query(None)
):
    """
    Initiate OAuth login flow

    Args:
        request: FastAPI request
        project_id: Project identifier
        redirect_uri: Optional custom redirect URI
        state: Optional state parameter from client

    Returns:
        Redirect to Google OAuth
    """
    try:
        # Get project configuration
        project_config = await project_config_manager.get_project_config(project_id)

        # Validate redirect URI if provided
        if redirect_uri:
            allowed_uris = project_config.get('redirect_uris', [])
            if not validate_redirect_uri(redirect_uri, allowed_uris):
                # セキュリティ: 本番環境では許可URIリストを露出しない
                detail_msg = "Invalid redirect_uri"
                if settings.is_development:
                    detail_msg += f". Allowed URIs: {allowed_uris}"
                raise HTTPException(
                    status_code=400,
                    detail=detail_msg
                )

        # Store redirect_uri and state in session for later use
        if redirect_uri:
            request.session['client_redirect_uri'] = redirect_uri
        if state:
            request.session['client_state'] = state

        # Create Google OAuth authorization URL
        auth_url, oauth_state = await google_oauth_handler.create_authorization_url(
            request, project_id
        )

        logger.info(f"Initiating OAuth for project: {project_id}")
        return RedirectResponse(url=auth_url)

    except ProjectNotFoundError as e:
        logger.error(f"Project not found: {project_id}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/callback/{project_id}")
async def callback(
    request: Request,
    project_id: str,
    code: str = Query(...),
    state: str = Query(...)
):
    """
    Handle OAuth callback

    Args:
        request: FastAPI request
        project_id: Project identifier
        code: Authorization code from Google
        state: State token for CSRF protection

    Returns:
        Redirect to client with token
    """
    try:
        # Get project configuration
        project_config = await project_config_manager.get_project_config(project_id)

        # Handle OAuth callback and get user info
        user_info, _ = await google_oauth_handler.handle_callback(
            request, code, state, project_id
        )

        # グループと組織部門の情報を取得（設定されている場合のみ）
        # サービスアカウントを使用するため、ユーザーのaccess_tokenは不要
        user_groups = None
        user_org_unit = None

        # role_rulesでgroup_membershipが使われているかチェック
        role_rules = project_config.get('role_rules', [])
        needs_groups_for_role = any(
            rule.get('condition_type') == 'group_membership'
            for rule in role_rules
        ) if role_rules else False

        # プロジェクト設定にグループまたはOU検証が含まれている場合、またはrole_rulesでグループが必要な場合
        if (project_config.get('required_groups') or
            project_config.get('allowed_groups') or
            project_config.get('required_org_units') or
            project_config.get('allowed_org_units') or
            needs_groups_for_role):

            # サービスアカウントが初期化されているか確認
            if workspace_admin_client.is_initialized:
                try:
                    # グループ情報の取得（サービスアカウント使用）
                    # allowed_groups/required_groupsまたはrole_rulesでグループが必要な場合
                    if (project_config.get('required_groups') or
                        project_config.get('allowed_groups') or
                        needs_groups_for_role):
                        user_groups = await workspace_admin_client.get_user_groups(
                            user_info['email']
                        )
                        logger.info(f"Retrieved {len(user_groups)} groups for {user_info['email']}")

                    # 組織部門情報の取得（サービスアカウント使用）
                    if project_config.get('required_org_units') or project_config.get('allowed_org_units'):
                        user_org_unit = await workspace_admin_client.get_user_org_unit(
                            user_info['email']
                        )
                        logger.info(f"Retrieved org unit '{user_org_unit}' for {user_info['email']}")

                except Exception as e:
                    logger.warning(f"Failed to retrieve workspace info: {str(e)}")
                    # グループ・OU情報の取得に失敗した場合でも、検証は続行
                    # （空リスト/Noneとして扱われる）
            else:
                logger.warning("Workspace Admin client not initialized. Group/OU validation will be skipped.")

        # Validate user access with groups and org unit
        try:
            validate_user_access(
                user_info['email'],
                project_config,
                user_groups=user_groups,
                user_org_unit=user_org_unit
            )
        except Exception as e:
            # Log failed attempt with enhanced details
            # ドメイン抽出（バリデーション付き）
            domain = validators.extract_domain(user_info['email'])
            await firestore_manager.log_audit_event(
                event_type='login_failed',
                project_id=project_id,
                user_email=user_info['email'],
                details={
                    'reason': str(e),
                    'error_code': getattr(e, 'error_code', 'UNKNOWN'),
                    'domain': domain if domain else 'unknown',
                    'is_student': validators.is_student_email(user_info['email']),
                    'groups': user_groups,
                    'org_unit': user_org_unit
                },
                ip_address=request.client.host,
                user_agent=request.headers.get('user-agent')
            )
            raise

        # ロール判定（role_rulesが設定されている場合）
        user_role = None
        if role_rules:
            # priorityでソートしてルールを評価
            sorted_rules = sorted(role_rules, key=lambda r: r.get('priority', 999))
            for rule in sorted_rules:
                condition_type = rule.get('condition_type')
                role = rule.get('role')

                if not condition_type or not role:
                    continue

                matched = False

                if condition_type == 'default':
                    # デフォルトルールは常にマッチ
                    matched = True

                elif condition_type == 'group_membership':
                    # グループメンバーシップ判定
                    group_email = rule.get('group_email')
                    if group_email and user_groups:
                        # user_groupsはメールアドレスのリスト
                        matched = group_email.lower() in [g.lower() for g in user_groups]

                elif condition_type == 'email_pattern':
                    # メールパターンマッチ
                    import re
                    pattern = rule.get('email_pattern')
                    if pattern:
                        try:
                            matched = bool(re.match(pattern, user_info['email']))
                        except re.error:
                            logger.warning(f"Invalid regex pattern: {pattern}")

                elif condition_type == 'email_list':
                    # メールリストマッチ
                    email_list = rule.get('email_list', [])
                    matched = user_info['email'].lower() in [e.lower() for e in email_list]

                if matched:
                    user_role = role
                    logger.info(f"Role resolved: {user_info['email']} -> {user_role} (condition: {condition_type})")
                    break

            if not user_role:
                logger.warning(f"No matching role rule for {user_info['email']}")

        # アクセストークン生成（1時間固定）
        additional_claims = {}
        # Google OAuthから取得したpictureとsubも追加
        if user_info.get('picture'):
            additional_claims['picture'] = user_info['picture']
        if user_info.get('sub'):
            additional_claims['sub'] = user_info['sub']

        access_token = jwt_handler.create_access_token(
            email=user_info['email'],
            name=user_info['name'],
            project_id=project_id,
            role=user_role,
            additional_claims=additional_claims if additional_claims else None
        )

        # リフレッシュトークン生成（プロダクト設定に基づく）
        refresh_expiry_days = project_config.get('refresh_token_expiry_days', 30)
        refresh_token = jwt_handler.create_refresh_token(
            email=user_info['email'],
            project_id=project_id,
            expiry_days=refresh_expiry_days
        )

        # Log successful login with enhanced details
        domain = validators.extract_domain(user_info['email'])
        await firestore_manager.log_audit_event(
            event_type='login_success',
            project_id=project_id,
            user_email=user_info['email'],
            details={
                'name': user_info['name'],
                'domain': domain if domain else 'unknown',
                'is_student': validators.is_student_email(user_info['email']),
                'login_method': 'google_oauth',
                'token_expiry_days': project_config.get('token_expiry_days', 30),
                'groups': user_groups,
                'org_unit': user_org_unit,
                'role': user_role
            },
            ip_address=request.client.host,
            user_agent=request.headers.get('user-agent')
        )

        # Determine redirect URL (セッションから取得後、削除してクリーンアップ)
        client_redirect_uri = request.session.pop('client_redirect_uri', None)
        if not client_redirect_uri:
            # Use default redirect URI from project config
            redirect_uris = project_config.get('redirect_uris', [])
            if not redirect_uris:
                raise ValueError("No redirect_uris configured for project")
            client_redirect_uri = redirect_uris[0]

        # Get client state if provided (セッションから取得後、削除してクリーンアップ)
        client_state = request.session.pop('client_state', None)

        # Build redirect URL based on token delivery method
        token_delivery = project_config.get('token_delivery', 'query_param')

        if token_delivery == 'query_param':
            # トークンをquery_parameterで返す（新方式）
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

        elif token_delivery == 'cookie':
            # Set token as HttpOnly cookie
            response = RedirectResponse(url=client_redirect_uri)
            response.set_cookie(
                key='auth_token',
                value=access_token,
                httponly=True,
                secure=settings.is_production,
                samesite='lax',
                max_age=3600  # 1時間
            )
            response.set_cookie(
                key='refresh_token',
                value=refresh_token,
                httponly=True,
                secure=settings.is_production,
                samesite='lax',
                max_age=refresh_expiry_days * 24 * 3600
            )
            if client_state:
                # Add state as query parameter even with cookie delivery
                separator = '&' if '?' in client_redirect_uri else '?'
                response.headers['Location'] = f"{client_redirect_uri}{separator}state={client_state}"

            return response

        else:
            raise ValueError(f"Unknown token delivery method: {token_delivery}")

    except ProjectNotFoundError as e:
        logger.error(f"Project not found: {project_id}")
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Callback error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/api/verify",
    response_model=UserInfo,
    responses={
        200: {
            "description": "Token is valid",
            "model": UserInfo
        },
        401: {
            "description": "Token is invalid or expired",
            "model": ErrorResponse
        }
    },
    summary="Verify JWT token",
    description="Verify the JWT token and return user information"
)
async def verify_token(
    token: Optional[str] = Query(None, description="JWT token from query parameter"),
    authorization: Optional[str] = Header(None, description="Authorization header (Bearer token)")
):
    """
    Verify JWT token

    Accepts token from either:
    - Query parameter: ?token=xxx
    - Authorization header: Bearer xxx

    Returns user information if token is valid.
    """
    # Get token from header or query parameter
    token_str: Optional[str] = None
    if authorization and authorization.startswith('Bearer '):
        token_str = authorization[7:]
    elif token:
        token_str = token

    if not token_str:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "AUTH_004",
                "detail": "No token provided",
                "message": "Authentication token is required"
            }
        )

    try:
        # Verify token
        payload = jwt_handler.verify_token(token_str)
        return UserInfo(
            email=payload['email'],
            name=payload['name'],
            project_id=payload['project_id'],
            exp=payload['exp'],
            valid=True
        )

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
    "/api/refresh",
    response_model=TokenRefreshResponse,
    responses={
        200: {
            "description": "Token refreshed successfully",
            "model": TokenRefreshResponse
        },
        401: {
            "description": "Token refresh failed",
            "model": ErrorResponse
        }
    },
    summary="Refresh JWT token",
    description="リフレッシュトークンを使用して新しいアクセストークン・リフレッシュトークンを取得（ローテーション方式）"
)
async def refresh_token_endpoint(
    request: Request,
    body: RefreshTokenRequest
):
    """
    リフレッシュトークンを使用して新しいトークンを取得

    ローテーション: 使用済みトークンは無効化
    """
    refresh_token_str = body.refresh_token
    project_id = body.project_id

    try:
        # 1. リフレッシュトークン検証
        payload = jwt_handler.verify_refresh_token(refresh_token_str)
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
                    "detail": "Refresh token has already been used",
                    "message": "セキュリティ上の理由でログアウトされました。別の場所でログインされた可能性があります。"
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
        # リフレッシュトークンにはnameやroleが含まれていないため、
        # プロジェクト設定から取得するか、空として扱う
        new_access_token = jwt_handler.create_access_token(
            email=email,
            name="",  # リフレッシュトークンにはnameがないため空
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

    except pyjwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "REFRESH_TOKEN_EXPIRED",
                "detail": "Refresh token has expired",
                "message": "セッションの有効期限が切れました。再度ログインしてください。"
            }
        )
    except HTTPException:
        # 既に HTTPException の場合はそのまま再度 raise
        raise
    except Exception as e:
        logger.error(f"Refresh token error: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail={
                "error": "AUTH_005",
                "detail": str(e),
                "message": "Cannot refresh token"
            }
        )


@router.get("/logout")
async def logout(
    return_url: Optional[str] = Query(None)
):
    """
    Logout user

    Args:
        return_url: URL to return to after logout

    Returns:
        Redirect to Google logout
    """
    logout_url = google_oauth_handler.get_logout_url(return_url)
    return RedirectResponse(url=logout_url)