"""Bearer token authentication implementation that can be enabled via environment variables."""

import logging
import os
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWK, PyJWKClient

_logger = logging.getLogger("anyvar.restapi.auth")


@dataclass
class BearerTokenAuthConfig:
    """Configuration for bearer token authentication.

    Supports both literal token validation and JWT token validation
    via OpenID Connect workflow.
    """

    token_list: list[str] = field(default_factory=list)
    issuer_url: str | None = None
    audiences: list[str] = field(default_factory=list)
    appids: list[str] = field(default_factory=list)
    scopes: list[str] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)
    subjects: list[str] = field(default_factory=list)
    jwks_uri: str | None = None
    _jwk_client: PyJWKClient | None = field(init=False, default=None)

    @classmethod
    def from_env(cls) -> "BearerTokenAuthConfig":
        """Load configuration from environment variables.

        All environment variables should begin with ANYVAR_AUTH_.

        Environment variables:
        - ANYVAR_AUTH_TOKEN_LIST: Comma-separated list of literal tokens
        - ANYVAR_AUTH_ISSUER_URL: JWT issuer URL (iss claim)
        - ANYVAR_AUTH_AUDIENCES: Comma-separated list of allowed audiences (aud claim)
        - ANYVAR_AUTH_APPIDS: Comma-separated list of allowed app IDs (appid claim)
        - ANYVAR_AUTH_SCOPES: Comma-separated list of required scopes (scope claim)
        - ANYVAR_AUTH_EMAILS: Comma-separated list of allowed emails (email claim)
        - ANYVAR_AUTH_SUBJECTS: Comma-separated list of allowed subjects (sub claim)
        - ANYVAR_AUTH_JWKS_URI: JWKS URI for JWT validation

        :return: BearerTokenAuthConfig instance
        """

        def parse_list(env_var: str) -> list[str]:
            """Parse comma-separated list from environment variable."""
            value = os.getenv(env_var, "")
            return [item.strip() for item in value.split(",") if item.strip()]

        return cls(
            token_list=parse_list("ANYVAR_AUTH_TOKEN_LIST"),
            issuer_url=os.getenv("ANYVAR_AUTH_ISSUER_URL"),
            audiences=parse_list("ANYVAR_AUTH_AUDIENCES"),
            appids=parse_list("ANYVAR_AUTH_APPIDS"),
            scopes=parse_list("ANYVAR_AUTH_SCOPES"),
            emails=[s.lower() for s in parse_list("ANYVAR_AUTH_EMAILS")],
            subjects=parse_list("ANYVAR_AUTH_SUBJECTS"),
            jwks_uri=os.getenv("ANYVAR_AUTH_JWKS_URI"),
        )

    def get_signing_key_from_jwt(self, token: str) -> PyJWK:
        """Get signing key from JWT token."""
        if not self.jwks_uri:
            raise ValueError("JWKS URI is not configured")

        if not self._jwk_client:
            self._jwk_client = PyJWKClient(
                self.jwks_uri, cache_keys=True, lifespan=3600
            )

        signing_key = self._jwk_client.get_signing_key_from_jwt(token)
        return signing_key


class ValidTokenCache:
    """Cache for validated JWT tokens to avoid repeated validations."""

    PURGE_INTERVAL_SECONDS = 3600  # Purge every hour

    def __init__(self) -> None:
        """Create a new token and initialize the last purge time."""
        self.last_purge = time.time()
        self.cache = {}

    def is_token_valid(self, token: str) -> bool:
        """Check if token is in cache and still valid."""
        expiry = self.cache.get(token, None)
        if expiry is not None:
            if time.time() < expiry:
                return True
            del self.cache[token]
        return False

    def add_token(self, token: str, exp: int) -> None:
        """Add token to cache with expiry."""
        self.cache[token] = exp

    def purge(self) -> None:
        """Purge expired tokens from cache every hour."""
        current_time = time.time()
        if current_time - self.last_purge < self.PURGE_INTERVAL_SECONDS:
            return
        self.last_purge = current_time
        tokens_to_delete = [
            token for token, exp in self.cache.items() if exp < current_time
        ]
        for token in tokens_to_delete:
            del self.cache[token]


def is_jwt_token_valid(
    auth_cfg: BearerTokenAuthConfig,
    token: str,
    token_cache: ValidTokenCache,
) -> bool:
    """Validate a JWT token using OpenID Connect configuration.

    :param auth_cfg: Authentication configuration
    :param token: JWT token to validate
    :return: True if token is valid, False otherwise
    """
    if not token or not auth_cfg.jwks_uri or not auth_cfg.issuer_url:
        return False

    if token_cache.is_token_valid(token):
        _logger.debug(
            "Token found in cache and is valid: %s...%s", token[0:20], token[-10:]
        )
        return True

    token_cache.purge()

    try:
        # Get JWKS signing key
        signing_key = auth_cfg.get_signing_key_from_jwt(token)
        _logger.debug("Using signing key with kid: %s", signing_key.key_id)

        # Decode and validate JWT
        decoded = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={
                "require": ["iat", "exp", "iss", "sub"],
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "verify_nbf": True,
                "verify_aud": False,  # Audience verified manually below
                "verify_iss": False,  # Issuer verified manually below
                "verify_jti": False,
                "verify_sub": True,  # Require subject claim to be present
            },
        )
        _logger.debug("Decoded JWT token: %s", decoded)

        # Validate issuer
        if decoded.get("iss") != auth_cfg.issuer_url:
            _logger.debug(
                "Token issuer mismatch: expected %s, got %s",
                auth_cfg.issuer_url,
                decoded.get("iss"),
            )
            return False

        # Validate audiences if configured
        if auth_cfg.audiences:
            token_audiences = (
                decoded.get("aud", [])
                if isinstance(decoded.get("aud"), list)
                else [decoded.get("aud")]
            )
            if not any(aud in token_audiences for aud in auth_cfg.audiences):
                _logger.debug(
                    "Token audience mismatch: expected %s, got %s",
                    auth_cfg.audiences,
                    token_audiences,
                )
                return False

        # Validate appids if configured
        if auth_cfg.appids:
            token_appid = decoded.get("appid")
            if token_appid not in auth_cfg.appids:
                _logger.debug(
                    "Token appid mismatch: expected %s, got %s",
                    auth_cfg.appids,
                    token_appid,
                )
                return False

        # Validate scopes if configured
        if auth_cfg.scopes:
            token_scopes = (
                decoded.get("scope", "").split()
                if isinstance(decoded.get("scope"), str)
                else decoded.get("scope", [])
            )
            if not any(scope in token_scopes for scope in auth_cfg.scopes):
                _logger.debug(
                    "Token scopes mismatch: expected %s, got %s",
                    auth_cfg.scopes,
                    token_scopes,
                )
                return False

        # Validate emails if configured
        if auth_cfg.emails:
            token_email = decoded.get("email")
            if token_email.lower() not in auth_cfg.emails:
                _logger.debug(
                    "Token email mismatch: expected %s, got %s",
                    auth_cfg.emails,
                    token_email,
                )
                return False

        # Validate subjects if configured
        if auth_cfg.subjects:
            token_subject = decoded.get("sub")
            if token_subject not in auth_cfg.subjects:
                _logger.debug(
                    "Token subject mismatch: expected %s, got %s",
                    auth_cfg.subjects,
                    token_subject,
                )
                return False

        token_cache.add_token(token, decoded["exp"])
        _logger.debug(
            "JWT token validated successfully: %s...%s", token[0:20], token[-10:]
        )

        return True  # noqa: TRY300
    except Exception:
        _logger.exception("JWT token validation failed")
        return False


def get_token_auth_dependency() -> Callable[[], Awaitable[None]]:
    """Get FastAPI dependency for token authentication.
    Uses environment variables to validate a Bearer token.

    :return: FastAPI dependency callable
    """
    auth_cfg = BearerTokenAuthConfig.from_env()

    if auth_cfg.token_list or auth_cfg.issuer_url:
        token_cache = ValidTokenCache()
        security_scheme = HTTPBearer(scheme_name="Bearer Auth")

        async def check_bearer_token(
            auth_token: HTTPAuthorizationCredentials = Depends(security_scheme),  # noqa: B008
        ) -> None:
            """FastAPI dependency to enforce token authentication.

            :param auth_token: Authorization header value
            :raises HTTPException: if authentication fails
            """
            try:
                if (
                    auth_cfg.token_list
                    and auth_token.credentials in auth_cfg.token_list
                ) or is_jwt_token_valid(auth_cfg, auth_token.credentials, token_cache):
                    return
            except Exception as exc:
                raise HTTPException(status_code=401, detail="Invalid token") from exc

            raise HTTPException(status_code=401, detail="Invalid token")

        return check_bearer_token

    async def no_auth_required() -> None:
        """No authentication required dependency."""
        return

    return no_auth_required
