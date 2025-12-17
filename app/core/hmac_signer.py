"""HMAC signature generation for API proxy requests"""

from typing import Dict, Any
import hmac
import hashlib
import json
import time
import logging

logger = logging.getLogger(__name__)


class HMACSignatureGenerator:
    """Generate HMAC signatures for API proxy requests"""

    @staticmethod
    def generate_signature(
        client_secret: str,
        timestamp: str,
        method: str,
        path: str,
        body: Dict[str, Any]
    ) -> str:
        """
        Generate HMAC-SHA256 signature for API proxy request

        Args:
            client_secret: Client secret for signing
            timestamp: Request timestamp
            method: HTTP method (POST, GET, etc.)
            path: Request path
            body: Request body as dictionary

        Returns:
            HMAC signature as hex string
        """
        # Serialize body to JSON
        body_json = json.dumps(body, sort_keys=True, separators=(',', ':'))

        # Create hash of body
        body_hash = hashlib.sha256(body_json.encode()).hexdigest()

        # Create signature string
        # Format: timestamp\nmethod\npath\nbody_hash
        # Note: method must be uppercase to match API proxy server verification logic
        signature_string = f"{timestamp}\n{method.upper()}\n{path}\n{body_hash}"

        # Generate HMAC signature
        signature = hmac.new(
            client_secret.encode(),
            signature_string.encode(),
            hashlib.sha256
        ).hexdigest()

        logger.debug(f"Generated HMAC signature for {method} {path}")
        return signature

    @staticmethod
    def generate_simple_signature(
        client_secret: str,
        timestamp: str,
        data: Dict[str, Any]
    ) -> str:
        """
        Generate simple HMAC signature (alternative format)

        Args:
            client_secret: Client secret for signing
            timestamp: Request timestamp
            data: Request data as dictionary

        Returns:
            HMAC signature as hex string
        """
        # Serialize data to JSON
        data_json = json.dumps(data, sort_keys=True, separators=(',', ':'))

        # Create signature string
        # Format: timestamp + data
        signature_string = f"{timestamp}{data_json}"

        # Generate HMAC signature
        signature = hmac.new(
            client_secret.encode(),
            signature_string.encode(),
            hashlib.sha256
        ).hexdigest()

        logger.debug("Generated simple HMAC signature")
        return signature

    @staticmethod
    def get_current_timestamp() -> str:
        """
        Get current timestamp as string

        Returns:
            Current timestamp as string
        """
        return str(int(time.time()))

    @staticmethod
    def create_signed_headers(
        client_id: str,
        client_secret: str,
        timestamp: str,
        method: str,
        path: str,
        body: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Create signed headers for API proxy request

        Args:
            client_id: Client ID
            client_secret: Client secret
            timestamp: Request timestamp
            method: HTTP method
            path: Request path
            body: Request body

        Returns:
            Dictionary of headers with signature
        """
        signature = HMACSignatureGenerator.generate_signature(
            client_secret=client_secret,
            timestamp=timestamp,
            method=method,
            path=path,
            body=body
        )

        headers = {
            "X-Client-ID": client_id,
            "X-Signature": signature,
            "X-Timestamp": timestamp,
            "Content-Type": "application/json"
        }

        logger.debug(f"Created signed headers for client: {client_id}")
        return headers


# Create singleton instance
hmac_signer = HMACSignatureGenerator()