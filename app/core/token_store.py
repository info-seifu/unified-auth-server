"""使用済みリフレッシュトークン管理"""

import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class TokenStore:
    """
    使用済みリフレッシュトークンを管理

    開発環境: メモリ（辞書）
    本番環境: Firestore（将来実装）
    """

    def __init__(self):
        self._used_tokens: Dict[str, Dict] = {}
        self._lock = threading.Lock()

    async def is_token_used(self, jti: str) -> bool:
        """
        トークンが使用済みかチェック

        Args:
            jti: トークン固有ID

        Returns:
            使用済みならTrue
        """
        with self._lock:
            return jti in self._used_tokens

    async def mark_token_as_used(
        self,
        jti: str,
        email: str,
        project_id: str,
        ip_address: Optional[str] = None
    ) -> None:
        """
        トークンを使用済みとしてマーク

        Args:
            jti: トークン固有ID
            email: ユーザーのメールアドレス
            project_id: プロジェクトID
            ip_address: IPアドレス（オプション）
        """
        with self._lock:
            self._used_tokens[jti] = {
                "email": email,
                "project_id": project_id,
                "used_at": datetime.now(timezone.utc).isoformat(),
                "ip_address": ip_address
            }
            logger.info(f"Marked token as used: jti={jti}, email={email}, project={project_id}")

    async def revoke_all_tokens_for_user(
        self,
        email: str,
        project_id: str
    ) -> None:
        """
        ユーザーの全トークンを無効化（再利用検知時）

        Args:
            email: ユーザーのメールアドレス
            project_id: プロジェクトID

        Note:
            将来実装用のスタブ。現在は何もしない。
        """
        # 将来実装: 該当ユーザーの全てのリフレッシュを拒否するフラグを設定
        logger.warning(f"revoke_all_tokens_for_user called (not implemented): email={email}, project={project_id}")
        pass

    def cleanup_expired(self, max_age_days: int = 31) -> None:
        """
        古い使用済みトークンを削除

        Args:
            max_age_days: 削除対象の日数
        """
        with self._lock:
            cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
            initial_count = len(self._used_tokens)

            self._used_tokens = {
                jti: data for jti, data in self._used_tokens.items()
                if datetime.fromisoformat(data["used_at"]) > cutoff
            }

            removed_count = initial_count - len(self._used_tokens)
            if removed_count > 0:
                logger.info(f"Cleaned up {removed_count} expired tokens (older than {max_age_days} days)")


# シングルトンインスタンス
token_store = TokenStore()
