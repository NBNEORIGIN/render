"""Etsy OAuth 2.0 Authentication with PKCE for Render.

Handles OAuth token generation, storage, and refresh for Etsy API v3 write access.
Mirrors ebay_auth.py pattern.

Etsy OAuth specifics:
- PKCE required (code_verifier + SHA256 code_challenge)
- Access token expires in 1 hour
- Refresh token expires in 90 days
- Auth header: x-api-key: keystring:shared_secret + Authorization: Bearer {token}
"""
import base64
import hashlib
import json
import logging
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Etsy OAuth endpoints
ETSY_AUTH_URL = "https://www.etsy.com/oauth/connect"
ETSY_TOKEN_URL = "https://api.etsy.com/v3/public/oauth/token"

# Scopes for listing creation, image upload, and shop management
ETSY_SCOPES = [
    "listings_w",
    "listings_r",
    "transactions_r",
    "shops_r",
]


def _generate_code_verifier() -> str:
    """Generate a PKCE code verifier (43-128 chars from [A-Za-z0-9._~-])."""
    return secrets.token_urlsafe(64)[:96]


def _generate_code_challenge(verifier: str) -> str:
    """Generate S256 code challenge from verifier."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


@dataclass
class EtsyTokens:
    """Etsy OAuth tokens."""
    access_token: str
    refresh_token: str
    expires_at: float
    token_type: str = "Bearer"

    def is_expired(self, buffer_seconds: int = 300) -> bool:
        return time.time() >= (self.expires_at - buffer_seconds)

    def to_dict(self) -> dict:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "token_type": self.token_type,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EtsyTokens":
        return cls(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=data["expires_at"],
            token_type=data.get("token_type", "Bearer"),
        )


class EtsyAuth:
    """Etsy OAuth 2.0 authentication manager with PKCE."""

    def __init__(
        self,
        api_key: str,
        shared_secret: str,
        redirect_uri: str,
        token_file: Path = Path("etsy_tokens.json"),
    ):
        self.api_key = api_key
        self.shared_secret = shared_secret
        self.redirect_uri = redirect_uri
        self.token_file = token_file
        self._tokens: Optional[EtsyTokens] = None
        self._code_verifier: Optional[str] = None

    def get_api_key_header(self) -> str:
        """Etsy Feb 2026 format: keystring:shared_secret."""
        return f"{self.api_key}:{self.shared_secret}"

    def start_oauth_flow(self, state: str = "etsy_render") -> tuple[str, str]:
        """Generate authorization URL and code verifier.

        Returns (auth_url, code_verifier). Store the verifier in session
        to use in the callback.
        """
        code_verifier = _generate_code_verifier()
        code_challenge = _generate_code_challenge(code_verifier)
        self._code_verifier = code_verifier

        params = {
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(ETSY_SCOPES),
            "client_id": self.api_key,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        auth_url = f"{ETSY_AUTH_URL}?{urlencode(params)}"
        return auth_url, code_verifier

    def exchange_code_for_tokens(self, auth_code: str, code_verifier: str) -> EtsyTokens:
        """Exchange authorization code for access + refresh tokens."""
        data = {
            "grant_type": "authorization_code",
            "client_id": self.api_key,
            "redirect_uri": self.redirect_uri,
            "code": auth_code,
            "code_verifier": code_verifier,
        }

        response = requests.post(
            ETSY_TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        token_data = response.json()

        tokens = EtsyTokens(
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            expires_at=time.time() + token_data.get("expires_in", 3600),
            token_type=token_data.get("token_type", "Bearer"),
        )

        self._tokens = tokens
        self._save_tokens(tokens)
        logging.info("Etsy OAuth tokens acquired, expires at %s", time.ctime(tokens.expires_at))
        return tokens

    def refresh_access_token(self, refresh_token: str) -> EtsyTokens:
        """Refresh an expired access token."""
        data = {
            "grant_type": "refresh_token",
            "client_id": self.api_key,
            "refresh_token": refresh_token,
        }

        response = requests.post(
            ETSY_TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        token_data = response.json()

        tokens = EtsyTokens(
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token", refresh_token),
            expires_at=time.time() + token_data.get("expires_in", 3600),
            token_type=token_data.get("token_type", "Bearer"),
        )

        self._tokens = tokens
        self._save_tokens(tokens)
        logging.info("Etsy token refreshed, expires at %s", time.ctime(tokens.expires_at))
        return tokens

    def _save_tokens(self, tokens: EtsyTokens) -> None:
        with self.token_file.open("w") as f:
            json.dump(tokens.to_dict(), f, indent=2)
        logging.info("Saved Etsy tokens to %s", self.token_file)

    def _load_tokens(self) -> Optional[EtsyTokens]:
        if not self.token_file.exists():
            return None
        try:
            with self.token_file.open("r") as f:
                data = json.load(f)
            return EtsyTokens.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            logging.warning("Failed to load Etsy tokens: %s", e)
            return None

    def get_access_token(self) -> str:
        """Get a valid access token, refreshing if needed."""
        if self._tokens and not self._tokens.is_expired():
            return self._tokens.access_token

        tokens = self._load_tokens()
        if tokens:
            if not tokens.is_expired():
                self._tokens = tokens
                return tokens.access_token
            try:
                logging.info("Etsy access token expired, refreshing...")
                tokens = self.refresh_access_token(tokens.refresh_token)
                return tokens.access_token
            except requests.HTTPError as e:
                logging.error("Failed to refresh Etsy token: %s", e)

        raise RuntimeError(
            "No valid Etsy tokens available. Complete the OAuth flow at /etsy/oauth/connect"
        )

    def get_auth_headers(self) -> dict:
        """Get headers for authenticated Etsy API requests."""
        token = self.get_access_token()
        return {
            "x-api-key": self.get_api_key_header(),
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def get_upload_headers(self) -> dict:
        """Get headers for multipart uploads (no Content-Type — requests sets it)."""
        token = self.get_access_token()
        return {
            "x-api-key": self.get_api_key_header(),
            "Authorization": f"Bearer {token}",
        }

    def is_connected(self) -> bool:
        """Check if we have valid (or refreshable) tokens."""
        tokens = self._load_tokens()
        if not tokens:
            return False
        if not tokens.is_expired():
            return True
        # Try refresh
        try:
            self.refresh_access_token(tokens.refresh_token)
            return True
        except Exception:
            return False

    def get_status(self) -> dict:
        """Return connection status for UI display."""
        tokens = self._load_tokens()
        if not tokens:
            return {"connected": False}
        return {
            "connected": not tokens.is_expired(),
            "expires_at": tokens.expires_at,
            "expires_at_human": time.ctime(tokens.expires_at),
            "token_type": tokens.token_type,
        }


def get_etsy_auth_from_env(token_file: Path = None) -> EtsyAuth:
    """Create EtsyAuth instance from environment variables."""
    api_key = os.environ.get("ETSY_API_KEY", "")
    shared_secret = os.environ.get("ETSY_SHARED_SECRET", "")
    redirect_uri = os.environ.get("ETSY_REDIRECT_URI", "http://localhost:5000/etsy/oauth/callback")

    if not api_key:
        raise ValueError("Missing ETSY_API_KEY environment variable")
    if not shared_secret:
        raise ValueError("Missing ETSY_SHARED_SECRET environment variable")

    if token_file is None:
        token_file = Path(__file__).parent / "etsy_tokens.json"

    return EtsyAuth(
        api_key=api_key,
        shared_secret=shared_secret,
        redirect_uri=redirect_uri,
        token_file=token_file,
    )
