import os
from unittest.mock import MagicMock, Mock, patch

import jwt
import pytest
from fastapi import HTTPException

from anyvar.restapi.auth import (
    BearerTokenAuthConfig,
    ValidTokenCache,
    get_token_auth_dependency,
    is_jwt_token_valid,
)


@pytest.mark.asyncio
async def test_no_auth():
    """Test that no authentication is required when no auth config is set."""
    dependency = get_token_auth_dependency()
    assert callable(dependency)
    assert dependency.__name__ == "no_auth_required"
    assert (await dependency()) is None


def test_config_default_initialization():
    """Test default initialization of BearerTokenAuthConfig."""
    config = BearerTokenAuthConfig()
    assert config.token_list == []
    assert config.issuer_url is None
    assert config.audiences == []
    assert config.appids == []
    assert config.scopes == []
    assert config.emails == []
    assert config.subjects == []
    assert config.jwks_uri is None


def test_config_initialization_with_values():
    """Test initialization with explicit values."""
    config = BearerTokenAuthConfig(
        token_list=["token1", "token2"],
        issuer_url="https://issuer.example.com",
        audiences=["https://api.example.com"],
        appids=["app-id-123"],
        scopes=["read", "write"],
        emails=["user@example.com"],
        subjects=["sub123"],
        jwks_uri="https://issuer.example.com/.well-known/jwks.json",
    )
    assert config.token_list == ["token1", "token2"]
    assert config.issuer_url == "https://issuer.example.com"
    assert config.audiences == ["https://api.example.com"]
    assert config.appids == ["app-id-123"]
    assert config.scopes == ["read", "write"]
    assert config.emails == ["user@example.com"]
    assert config.subjects == ["sub123"]
    assert config.jwks_uri == "https://issuer.example.com/.well-known/jwks.json"


@patch.dict(os.environ, {}, clear=True)
def test_config_from_env_empty():
    """Test from_env with no environment variables set."""
    config = BearerTokenAuthConfig.from_env()
    assert config.token_list == []
    assert config.issuer_url is None
    assert config.audiences == []
    assert config.appids == []
    assert config.scopes == []
    assert config.emails == []
    assert config.subjects == []
    assert config.jwks_uri is None


@patch.dict(
    os.environ,
    {
        "ANYVAR_AUTH_TOKEN_LIST": "token1,token2,token3",
        "ANYVAR_AUTH_ISSUER_URL": "https://issuer.example.com",
        "ANYVAR_AUTH_AUDIENCES": "https://api.example.com,api://my-api",
        "ANYVAR_AUTH_APPIDS": "app-id-123,app-id-456",
        "ANYVAR_AUTH_SCOPES": "read,write",
        "ANYVAR_AUTH_EMAILS": "User@Example.Com,admin@example.com",
        "ANYVAR_AUTH_SUBJECTS": "sub123,sub456",
        "ANYVAR_AUTH_JWKS_URI": "https://issuer.example.com/.well-known/jwks.json",
    },
)
def test_config_from_env_with_values():
    """Test from_env with environment variables set."""
    config = BearerTokenAuthConfig.from_env()
    assert config.token_list == ["token1", "token2", "token3"]
    assert config.issuer_url == "https://issuer.example.com"
    assert config.audiences == ["https://api.example.com", "api://my-api"]
    assert config.appids == ["app-id-123", "app-id-456"]
    assert config.scopes == ["read", "write"]
    assert config.emails == ["user@example.com", "admin@example.com"]
    assert config.subjects == ["sub123", "sub456"]
    assert config.jwks_uri == "https://issuer.example.com/.well-known/jwks.json"


@patch.dict(
    os.environ,
    {"ANYVAR_AUTH_TOKEN_LIST": " token1 , token2 , , token3 "},
)
def test_config_from_env_strips_whitespace():
    """Test that from_env strips whitespace and empty values."""
    config = BearerTokenAuthConfig.from_env()
    assert config.token_list == ["token1", "token2", "token3"]


def test_config_get_signing_key_from_jwt_no_jwks_uri():
    """Test get_signing_key_from_jwt raises error when JWKS URI not configured."""
    config = BearerTokenAuthConfig()
    with pytest.raises(ValueError, match="JWKS URI is not configured"):
        config.get_signing_key_from_jwt("fake_token")


@patch("anyvar.restapi.auth.PyJWKClient")
def test_config_get_signing_key_from_jwt(mock_jwk_client_class):
    """Test get_signing_key_from_jwt successfully retrieves signing key."""
    mock_client = MagicMock()
    mock_signing_key = Mock()
    mock_client.get_signing_key_from_jwt.return_value = mock_signing_key
    mock_jwk_client_class.return_value = mock_client

    config = BearerTokenAuthConfig(jwks_uri="https://example.com/jwks")
    result = config.get_signing_key_from_jwt("fake_token")

    assert result == mock_signing_key
    mock_jwk_client_class.assert_called_once_with(
        "https://example.com/jwks", cache_keys=True, lifespan=3600
    )
    mock_client.get_signing_key_from_jwt.assert_called_once_with("fake_token")


@patch("anyvar.restapi.auth.PyJWKClient")
def test_config_get_signing_key_from_jwt_caches_client(mock_jwk_client_class):
    """Test that PyJWKClient is cached after first call."""
    mock_client = MagicMock()
    mock_jwk_client_class.return_value = mock_client

    config = BearerTokenAuthConfig(jwks_uri="https://example.com/jwks")
    config.get_signing_key_from_jwt("token1")
    config.get_signing_key_from_jwt("token2")

    # Should only create client once
    assert mock_jwk_client_class.call_count == 1


def test_valid_token_cache_initialization():
    """Test ValidTokenCache initialization."""
    cache = ValidTokenCache()
    assert cache.cache == {}
    assert isinstance(cache.last_purge, float)


def test_valid_token_cache_is_token_valid_not_in_cache():
    """Test is_token_valid returns False when token not in cache."""
    cache = ValidTokenCache()
    assert cache.is_token_valid("nonexistent_token") is False


def test_valid_token_cache_is_token_valid_expired():
    """Test is_token_valid returns False and removes expired token."""
    cache = ValidTokenCache()
    expired_time = 1000.0
    cache.cache["expired_token"] = expired_time

    with patch("time.time", return_value=2000.0):
        assert cache.is_token_valid("expired_token") is False

    # Token should be removed from cache
    assert "expired_token" not in cache.cache


def test_valid_token_cache_is_token_valid_not_expired():
    """Test is_token_valid returns True for valid token."""
    cache = ValidTokenCache()
    future_time = 9999999999.0
    cache.cache["valid_token"] = future_time

    with patch("time.time", return_value=1000.0):
        assert cache.is_token_valid("valid_token") is True

    # Token should remain in cache
    assert "valid_token" in cache.cache


def test_valid_token_cache_add_token():
    """Test add_token adds token with expiry to cache."""
    cache = ValidTokenCache()
    cache.add_token("new_token", 5000)

    assert cache.cache["new_token"] == 5000


def test_valid_token_cache_purge_no_purge_before_hour():
    """Test purge does not run if called before 1 hour."""
    cache = ValidTokenCache()
    cache.last_purge = 1000.0
    cache.cache["token1"] = 500.0  # Expired
    cache.cache["token2"] = 9999.0  # Valid

    with patch("time.time", return_value=2000.0):  # Less than 3600 seconds later
        cache.purge()

    # No purging should happen
    assert "token1" in cache.cache
    assert cache.last_purge == 1000.0


def test_valid_token_cache_purge_removes_expired():
    """Test purge removes expired tokens after 1 hour."""
    cache = ValidTokenCache()
    cache.last_purge = 1000.0
    cache.cache["expired_token"] = 3000.0
    cache.cache["valid_token"] = 9999.0

    with patch("time.time", return_value=5000.0):  # More than 3600 seconds later
        cache.purge()

    assert "expired_token" not in cache.cache
    assert "valid_token" in cache.cache
    assert cache.last_purge == 5000.0


def test_valid_token_cache_purge_updates_last_purge_time():
    """Test purge updates last_purge timestamp."""
    cache = ValidTokenCache()
    cache.last_purge = 1000.0

    with patch("time.time", return_value=5000.0):
        cache.purge()

    assert cache.last_purge == 5000.0


# Tests for is_jwt_token_valid function


def test_is_jwt_token_valid_no_jwks_uri():
    """Test is_jwt_token_valid returns False when JWKS URI not configured."""
    config = BearerTokenAuthConfig(issuer_url="https://issuer.example.com")
    cache = ValidTokenCache()

    result = is_jwt_token_valid(config, "fake_token", cache)

    assert result is False


def test_is_jwt_token_valid_no_issuer_url():
    """Test is_jwt_token_valid returns False when issuer URL not configured."""
    config = BearerTokenAuthConfig(jwks_uri="https://example.com/jwks")
    cache = ValidTokenCache()

    result = is_jwt_token_valid(config, "fake_token", cache)

    assert result is False


def test_is_jwt_token_valid_cached_token():
    """Test is_jwt_token_valid returns True for cached valid token."""
    config = BearerTokenAuthConfig(
        issuer_url="https://issuer.example.com", jwks_uri="https://example.com/jwks"
    )
    cache = ValidTokenCache()
    cache.add_token("cached_token", 9999999999.0)

    result = is_jwt_token_valid(config, "cached_token", cache)

    assert result is True


@patch("anyvar.restapi.auth.jwt.decode")
def test_is_jwt_token_valid_successful_validation(mock_jwt_decode):
    """Test is_jwt_token_valid with successful JWT validation."""
    config = BearerTokenAuthConfig(
        issuer_url="https://issuer.example.com", jwks_uri="https://example.com/jwks"
    )
    cache = ValidTokenCache()

    # Mock the JWT decode to return valid claims
    mock_jwt_decode.return_value = {
        "iss": "https://issuer.example.com",
        "exp": 9999999999,
        "iat": 1000000000,
        "sub": "user123",
    }

    # Mock get_signing_key_from_jwt
    with patch.object(config, "get_signing_key_from_jwt") as mock_get_key:
        mock_signing_key = Mock()
        mock_signing_key.key = "fake_key"
        mock_get_key.return_value = mock_signing_key

        result = is_jwt_token_valid(config, "valid_token", cache)

    assert result is True
    mock_jwt_decode.assert_called_once()


@patch("anyvar.restapi.auth.jwt.decode")
def test_is_jwt_token_valid_wrong_issuer(mock_jwt_decode):
    """Test is_jwt_token_valid returns False when issuer doesn't match."""
    config = BearerTokenAuthConfig(
        issuer_url="https://issuer.example.com", jwks_uri="https://example.com/jwks"
    )
    cache = ValidTokenCache()

    mock_jwt_decode.return_value = {
        "iss": "https://wrong-issuer.example.com",
        "exp": 9999999999,
        "iat": 1000000000,
        "sub": "user123",
    }

    with patch.object(config, "get_signing_key_from_jwt") as mock_get_key:
        mock_signing_key = Mock()
        mock_signing_key.key = "fake_key"
        mock_get_key.return_value = mock_signing_key

        result = is_jwt_token_valid(config, "token", cache)

    assert result is False


@patch("anyvar.restapi.auth.jwt.decode")
def test_is_jwt_token_valid_with_valid_audience_string(mock_jwt_decode):
    """Test is_jwt_token_valid with valid audience as string."""
    config = BearerTokenAuthConfig(
        issuer_url="https://issuer.example.com",
        jwks_uri="https://example.com/jwks",
        audiences=["https://api.example.com"],
    )
    cache = ValidTokenCache()

    mock_jwt_decode.return_value = {
        "iss": "https://issuer.example.com",
        "aud": "https://api.example.com",
        "exp": 9999999999,
        "iat": 1000000000,
        "sub": "user123",
    }

    with patch.object(config, "get_signing_key_from_jwt") as mock_get_key:
        mock_signing_key = Mock()
        mock_signing_key.key = "fake_key"
        mock_get_key.return_value = mock_signing_key

        result = is_jwt_token_valid(config, "token", cache)

    assert result is True


@patch("anyvar.restapi.auth.jwt.decode")
def test_is_jwt_token_valid_with_valid_audience_list(mock_jwt_decode):
    """Test is_jwt_token_valid with valid audience as list."""
    config = BearerTokenAuthConfig(
        issuer_url="https://issuer.example.com",
        jwks_uri="https://example.com/jwks",
        audiences=["https://api.example.com", "api://my-api"],
    )
    cache = ValidTokenCache()

    mock_jwt_decode.return_value = {
        "iss": "https://issuer.example.com",
        "aud": ["https://api.example.com", "https://other-api.example.com"],
        "exp": 9999999999,
        "iat": 1000000000,
        "sub": "user123",
    }

    with patch.object(config, "get_signing_key_from_jwt") as mock_get_key:
        mock_signing_key = Mock()
        mock_signing_key.key = "fake_key"
        mock_get_key.return_value = mock_signing_key

        result = is_jwt_token_valid(config, "token", cache)

    assert result is True


@patch("anyvar.restapi.auth.jwt.decode")
def test_is_jwt_token_valid_with_invalid_audience(mock_jwt_decode):
    """Test is_jwt_token_valid returns False when audience doesn't match."""
    config = BearerTokenAuthConfig(
        issuer_url="https://issuer.example.com",
        jwks_uri="https://example.com/jwks",
        audiences=["https://api.example.com"],
    )
    cache = ValidTokenCache()

    mock_jwt_decode.return_value = {
        "iss": "https://issuer.example.com",
        "aud": "https://wrong-api.example.com",
        "exp": 9999999999,
        "iat": 1000000000,
        "sub": "user123",
    }

    with patch.object(config, "get_signing_key_from_jwt") as mock_get_key:
        mock_signing_key = Mock()
        mock_signing_key.key = "fake_key"
        mock_get_key.return_value = mock_signing_key

        result = is_jwt_token_valid(config, "token", cache)

    assert result is False


@patch("anyvar.restapi.auth.jwt.decode")
def test_is_jwt_token_valid_with_valid_appid(mock_jwt_decode):
    """Test is_jwt_token_valid with valid appid claim."""
    config = BearerTokenAuthConfig(
        issuer_url="https://issuer.example.com",
        jwks_uri="https://example.com/jwks",
        appids=["app-id-123", "app-id-456"],
    )
    cache = ValidTokenCache()

    mock_jwt_decode.return_value = {
        "iss": "https://issuer.example.com",
        "appid": "app-id-123",
        "exp": 9999999999,
        "iat": 1000000000,
        "sub": "user123",
    }

    with patch.object(config, "get_signing_key_from_jwt") as mock_get_key:
        mock_signing_key = Mock()
        mock_signing_key.key = "fake_key"
        mock_get_key.return_value = mock_signing_key

        result = is_jwt_token_valid(config, "token", cache)

    assert result is True


@patch("anyvar.restapi.auth.jwt.decode")
def test_is_jwt_token_valid_with_valid_azp(mock_jwt_decode):
    """Test is_jwt_token_valid with valid azp claim (fallback for appid)."""
    config = BearerTokenAuthConfig(
        issuer_url="https://issuer.example.com",
        jwks_uri="https://example.com/jwks",
        appids=["app-id-123"],
    )
    cache = ValidTokenCache()

    mock_jwt_decode.return_value = {
        "iss": "https://issuer.example.com",
        "appid": "app-id-123",
        "exp": 9999999999,
        "iat": 1000000000,
        "sub": "user123",
    }

    with patch.object(config, "get_signing_key_from_jwt") as mock_get_key:
        mock_signing_key = Mock()
        mock_signing_key.key = "fake_key"
        mock_get_key.return_value = mock_signing_key

        result = is_jwt_token_valid(config, "token", cache)

    assert result is True


@patch("anyvar.restapi.auth.jwt.decode")
def test_is_jwt_token_valid_with_invalid_appid(mock_jwt_decode):
    """Test is_jwt_token_valid returns False when appid doesn't match."""
    config = BearerTokenAuthConfig(
        issuer_url="https://issuer.example.com",
        jwks_uri="https://example.com/jwks",
        appids=["app-id-123"],
    )
    cache = ValidTokenCache()

    mock_jwt_decode.return_value = {
        "iss": "https://issuer.example.com",
        "appid": "wrong-app-id",
        "exp": 9999999999,
        "iat": 1000000000,
        "sub": "user123",
    }

    with patch.object(config, "get_signing_key_from_jwt") as mock_get_key:
        mock_signing_key = Mock()
        mock_signing_key.key = "fake_key"
        mock_get_key.return_value = mock_signing_key

        result = is_jwt_token_valid(config, "token", cache)

    assert result is False


@patch("anyvar.restapi.auth.jwt.decode")
def test_is_jwt_token_valid_with_valid_scopes(mock_jwt_decode):
    """Test is_jwt_token_valid with valid scopes."""
    config = BearerTokenAuthConfig(
        issuer_url="https://issuer.example.com",
        jwks_uri="https://example.com/jwks",
        scopes=["read", "write"],
    )
    cache = ValidTokenCache()

    mock_jwt_decode.return_value = {
        "iss": "https://issuer.example.com",
        "exp": 9999999999,
        "iat": 1000000000,
        "sub": "user123",
        "scope": "read write execute",
    }

    with patch.object(config, "get_signing_key_from_jwt") as mock_get_key:
        mock_signing_key = Mock()
        mock_signing_key.key = "fake_key"
        mock_get_key.return_value = mock_signing_key

        result = is_jwt_token_valid(config, "token", cache)

    assert result is True


@patch("anyvar.restapi.auth.jwt.decode")
def test_is_jwt_token_valid_with_scope_as_list(mock_jwt_decode):
    """Test is_jwt_token_valid with scope as list."""
    config = BearerTokenAuthConfig(
        issuer_url="https://issuer.example.com",
        jwks_uri="https://example.com/jwks",
        scopes=["read"],
    )
    cache = ValidTokenCache()

    mock_jwt_decode.return_value = {
        "iss": "https://issuer.example.com",
        "exp": 9999999999,
        "iat": 1000000000,
        "sub": "user123",
        "scope": ["read", "write"],
    }

    with patch.object(config, "get_signing_key_from_jwt") as mock_get_key:
        mock_signing_key = Mock()
        mock_signing_key.key = "fake_key"
        mock_get_key.return_value = mock_signing_key

        result = is_jwt_token_valid(config, "token", cache)

    assert result is True


@patch("anyvar.restapi.auth.jwt.decode")
def test_is_jwt_token_valid_with_invalid_scopes(mock_jwt_decode):
    """Test is_jwt_token_valid returns False when required scopes not present."""
    config = BearerTokenAuthConfig(
        issuer_url="https://issuer.example.com",
        jwks_uri="https://example.com/jwks",
        scopes=["admin"],
    )
    cache = ValidTokenCache()

    mock_jwt_decode.return_value = {
        "iss": "https://issuer.example.com",
        "exp": 9999999999,
        "iat": 1000000000,
        "sub": "user123",
        "scope": "read write",
    }

    with patch.object(config, "get_signing_key_from_jwt") as mock_get_key:
        mock_signing_key = Mock()
        mock_signing_key.key = "fake_key"
        mock_get_key.return_value = mock_signing_key

        result = is_jwt_token_valid(config, "token", cache)

    assert result is False


@patch("anyvar.restapi.auth.jwt.decode")
def test_is_jwt_token_valid_with_valid_email(mock_jwt_decode):
    """Test is_jwt_token_valid with valid email."""
    config = BearerTokenAuthConfig(
        issuer_url="https://issuer.example.com",
        jwks_uri="https://example.com/jwks",
        emails=["user@example.com"],
    )
    cache = ValidTokenCache()

    mock_jwt_decode.return_value = {
        "iss": "https://issuer.example.com",
        "exp": 9999999999,
        "iat": 1000000000,
        "sub": "user123",
        "email": "user@example.com",
    }

    with patch.object(config, "get_signing_key_from_jwt") as mock_get_key:
        mock_signing_key = Mock()
        mock_signing_key.key = "fake_key"
        mock_get_key.return_value = mock_signing_key

        result = is_jwt_token_valid(config, "token", cache)

    assert result is True


@patch("anyvar.restapi.auth.jwt.decode")
def test_is_jwt_token_valid_with_case_insensitive_email(mock_jwt_decode):
    """Test is_jwt_token_valid handles email case insensitivity."""
    config = BearerTokenAuthConfig(
        issuer_url="https://issuer.example.com",
        jwks_uri="https://example.com/jwks",
        emails=["user@example.com"],
    )
    cache = ValidTokenCache()

    mock_jwt_decode.return_value = {
        "iss": "https://issuer.example.com",
        "exp": 9999999999,
        "iat": 1000000000,
        "sub": "user123",
        "email": "User@Example.Com",
    }

    with patch.object(config, "get_signing_key_from_jwt") as mock_get_key:
        mock_signing_key = Mock()
        mock_signing_key.key = "fake_key"
        mock_get_key.return_value = mock_signing_key

        result = is_jwt_token_valid(config, "token", cache)

    assert result is True


@patch("anyvar.restapi.auth.jwt.decode")
def test_is_jwt_token_valid_with_invalid_email(mock_jwt_decode):
    """Test is_jwt_token_valid returns False when email not in allowed list."""
    config = BearerTokenAuthConfig(
        issuer_url="https://issuer.example.com",
        jwks_uri="https://example.com/jwks",
        emails=["allowed@example.com"],
    )
    cache = ValidTokenCache()

    mock_jwt_decode.return_value = {
        "iss": "https://issuer.example.com",
        "exp": 9999999999,
        "iat": 1000000000,
        "sub": "user123",
        "email": "notallowed@example.com",
    }

    with patch.object(config, "get_signing_key_from_jwt") as mock_get_key:
        mock_signing_key = Mock()
        mock_signing_key.key = "fake_key"
        mock_get_key.return_value = mock_signing_key

        result = is_jwt_token_valid(config, "token", cache)

    assert result is False


@patch("anyvar.restapi.auth.jwt.decode")
def test_is_jwt_token_valid_with_valid_subject(mock_jwt_decode):
    """Test is_jwt_token_valid with valid subject."""
    config = BearerTokenAuthConfig(
        issuer_url="https://issuer.example.com",
        jwks_uri="https://example.com/jwks",
        subjects=["sub123", "sub456"],
    )
    cache = ValidTokenCache()

    mock_jwt_decode.return_value = {
        "iss": "https://issuer.example.com",
        "exp": 9999999999,
        "iat": 1000000000,
        "sub": "sub123",
    }

    with patch.object(config, "get_signing_key_from_jwt") as mock_get_key:
        mock_signing_key = Mock()
        mock_signing_key.key = "fake_key"
        mock_get_key.return_value = mock_signing_key

        result = is_jwt_token_valid(config, "token", cache)

    assert result is True


@patch("anyvar.restapi.auth.jwt.decode")
def test_is_jwt_token_valid_with_invalid_subject(mock_jwt_decode):
    """Test is_jwt_token_valid returns False when subject not in allowed list."""
    config = BearerTokenAuthConfig(
        issuer_url="https://issuer.example.com",
        jwks_uri="https://example.com/jwks",
        subjects=["sub123"],
    )
    cache = ValidTokenCache()

    mock_jwt_decode.return_value = {
        "iss": "https://issuer.example.com",
        "exp": 9999999999,
        "iat": 1000000000,
        "sub": "sub999",
    }

    with patch.object(config, "get_signing_key_from_jwt") as mock_get_key:
        mock_signing_key = Mock()
        mock_signing_key.key = "fake_key"
        mock_get_key.return_value = mock_signing_key

        result = is_jwt_token_valid(config, "token", cache)

    assert result is False


@patch("anyvar.restapi.auth.jwt.decode")
def test_is_jwt_token_valid_with_all_validations(mock_jwt_decode):
    """Test is_jwt_token_valid with all validation criteria."""
    config = BearerTokenAuthConfig(
        issuer_url="https://issuer.example.com",
        jwks_uri="https://example.com/jwks",
        scopes=["read"],
        emails=["user@example.com"],
        subjects=["sub123"],
    )
    cache = ValidTokenCache()

    mock_jwt_decode.return_value = {
        "iss": "https://issuer.example.com",
        "exp": 9999999999,
        "iat": 1000000000,
        "scope": "read write",
        "email": "user@example.com",
        "sub": "sub123",
    }

    with patch.object(config, "get_signing_key_from_jwt") as mock_get_key:
        mock_signing_key = Mock()
        mock_signing_key.key = "fake_key"
        mock_get_key.return_value = mock_signing_key

        result = is_jwt_token_valid(config, "token", cache)

    assert result is True


@patch("anyvar.restapi.auth.jwt.decode")
def test_is_jwt_token_valid_jwt_decode_exception(mock_jwt_decode):
    """Test is_jwt_token_valid returns False when JWT decode raises exception."""
    config = BearerTokenAuthConfig(
        issuer_url="https://issuer.example.com", jwks_uri="https://example.com/jwks"
    )
    cache = ValidTokenCache()

    mock_jwt_decode.side_effect = jwt.DecodeError("Invalid token")

    with patch.object(config, "get_signing_key_from_jwt") as mock_get_key:
        mock_signing_key = Mock()
        mock_signing_key.key = "fake_key"
        mock_get_key.return_value = mock_signing_key

        result = is_jwt_token_valid(config, "invalid_token", cache)

    assert result is False


@patch("anyvar.restapi.auth.jwt.decode")
def test_is_jwt_token_valid_expired_token(mock_jwt_decode):
    """Test is_jwt_token_valid returns False when token is expired."""
    config = BearerTokenAuthConfig(
        issuer_url="https://issuer.example.com", jwks_uri="https://example.com/jwks"
    )
    cache = ValidTokenCache()

    mock_jwt_decode.side_effect = jwt.ExpiredSignatureError("Token expired")

    with patch.object(config, "get_signing_key_from_jwt") as mock_get_key:
        mock_signing_key = Mock()
        mock_signing_key.key = "fake_key"
        mock_get_key.return_value = mock_signing_key

        result = is_jwt_token_valid(config, "expired_token", cache)

    assert result is False


def test_is_jwt_token_valid_get_signing_key_exception():
    """Test is_jwt_token_valid returns False when get_signing_key raises exception."""
    config = BearerTokenAuthConfig(
        issuer_url="https://issuer.example.com", jwks_uri="https://example.com/jwks"
    )
    cache = ValidTokenCache()

    with patch.object(
        config, "get_signing_key_from_jwt", side_effect=Exception("Key error")
    ):
        result = is_jwt_token_valid(config, "token", cache)

    assert result is False


# Tests for check_bearer_token function (via get_token_auth_dependency)


@pytest.mark.asyncio
@patch.dict(
    os.environ,
    {"ANYVAR_AUTH_TOKEN_LIST": "valid_token_1,valid_token_2"},
)
async def test_check_bearer_token_with_valid_literal_token():
    """Test check_bearer_token accepts valid literal token."""
    dependency = get_token_auth_dependency()

    # Create a mock HTTPBearer credentials object
    mock_auth = Mock()
    mock_auth.credentials = "valid_token_1"

    # Should not raise exception
    result = await dependency(mock_auth)
    assert result is None


@pytest.mark.asyncio
@patch.dict(
    os.environ,
    {"ANYVAR_AUTH_TOKEN_LIST": "valid_token_1,valid_token_2"},
)
async def test_check_bearer_token_with_invalid_literal_token():
    """Test check_bearer_token rejects invalid literal token."""
    dependency = get_token_auth_dependency()

    mock_auth = Mock()
    mock_auth.credentials = "invalid_token"

    with pytest.raises(HTTPException) as exc_info:
        await dependency(mock_auth)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token"


@pytest.mark.asyncio
@patch.dict(
    os.environ,
    {
        "ANYVAR_AUTH_ISSUER_URL": "https://issuer.example.com",
        "ANYVAR_AUTH_JWKS_URI": "https://example.com/jwks",
    },
)
@patch("anyvar.restapi.auth.is_jwt_token_valid")
async def test_check_bearer_token_with_valid_jwt(mock_is_jwt_valid):
    """Test check_bearer_token accepts valid JWT token."""
    mock_is_jwt_valid.return_value = True

    dependency = get_token_auth_dependency()

    mock_auth = Mock()
    mock_auth.credentials = "valid.jwt.token"

    result = await dependency(mock_auth)
    assert result is None
    mock_is_jwt_valid.assert_called_once()


@pytest.mark.asyncio
@patch.dict(
    os.environ,
    {
        "ANYVAR_AUTH_ISSUER_URL": "https://issuer.example.com",
        "ANYVAR_AUTH_JWKS_URI": "https://example.com/jwks",
    },
)
@patch("anyvar.restapi.auth.is_jwt_token_valid")
async def test_check_bearer_token_with_invalid_jwt(mock_is_jwt_valid):
    """Test check_bearer_token rejects invalid JWT token."""
    mock_is_jwt_valid.return_value = False

    dependency = get_token_auth_dependency()

    mock_auth = Mock()
    mock_auth.credentials = "invalid.jwt.token"

    with pytest.raises(HTTPException) as exc_info:
        await dependency(mock_auth)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token"


@pytest.mark.asyncio
@patch.dict(
    os.environ,
    {
        "ANYVAR_AUTH_TOKEN_LIST": "literal_token",
        "ANYVAR_AUTH_ISSUER_URL": "https://issuer.example.com",
        "ANYVAR_AUTH_JWKS_URI": "https://example.com/jwks",
    },
)
async def test_check_bearer_token_literal_token_takes_precedence():
    """Test check_bearer_token checks literal tokens first."""
    dependency = get_token_auth_dependency()

    mock_auth = Mock()
    mock_auth.credentials = "literal_token"

    # Should succeed without calling JWT validation
    with patch("anyvar.restapi.auth.is_jwt_token_valid") as mock_is_jwt_valid:
        result = await dependency(mock_auth)
        assert result is None
        # JWT validation should not be called since literal token matched
        mock_is_jwt_valid.assert_not_called()


@pytest.mark.asyncio
@patch.dict(
    os.environ,
    {
        "ANYVAR_AUTH_TOKEN_LIST": "literal_token",
        "ANYVAR_AUTH_ISSUER_URL": "https://issuer.example.com",
        "ANYVAR_AUTH_JWKS_URI": "https://example.com/jwks",
    },
)
@patch("anyvar.restapi.auth.is_jwt_token_valid")
async def test_check_bearer_token_falls_back_to_jwt_validation(mock_is_jwt_valid):
    """Test check_bearer_token falls back to JWT when literal token doesn't match."""
    mock_is_jwt_valid.return_value = True

    dependency = get_token_auth_dependency()

    mock_auth = Mock()
    mock_auth.credentials = "not.literal.token"

    result = await dependency(mock_auth)
    assert result is None
    # JWT validation should be called
    mock_is_jwt_valid.assert_called_once()


@pytest.mark.asyncio
@patch.dict(
    os.environ,
    {
        "ANYVAR_AUTH_ISSUER_URL": "https://issuer.example.com",
        "ANYVAR_AUTH_JWKS_URI": "https://example.com/jwks",
    },
)
@patch("anyvar.restapi.auth.is_jwt_token_valid")
async def test_check_bearer_token_exception_handling(mock_is_jwt_valid):
    """Test check_bearer_token converts exceptions to HTTPException."""
    mock_is_jwt_valid.side_effect = Exception("Unexpected error")

    dependency = get_token_auth_dependency()

    mock_auth = Mock()
    mock_auth.credentials = "some.token"

    with pytest.raises(HTTPException) as exc_info:
        await dependency(mock_auth)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token"


@pytest.mark.asyncio
@patch.dict(
    os.environ,
    {
        "ANYVAR_AUTH_TOKEN_LIST": "valid_token",
    },
)
async def test_check_bearer_token_with_literal_tokens_only():
    """Test check_bearer_token with only literal tokens configured."""
    dependency = get_token_auth_dependency()

    mock_auth = Mock()
    mock_auth.credentials = "valid_token"

    with patch("anyvar.restapi.auth.is_jwt_token_valid") as mock_is_jwt_valid:
        result = await dependency(mock_auth)
        assert result is None
        # JWT validation should not be called
        mock_is_jwt_valid.assert_not_called()


@pytest.mark.asyncio
@patch.dict(
    os.environ,
    {
        "ANYVAR_AUTH_ISSUER_URL": "https://issuer.example.com",
        "ANYVAR_AUTH_JWKS_URI": "https://example.com/jwks",
    },
)
@patch("anyvar.restapi.auth.is_jwt_token_valid")
async def test_check_bearer_token_with_jwt_only(mock_is_jwt_valid):
    """Test check_bearer_token with only JWT configuration."""
    mock_is_jwt_valid.return_value = True

    dependency = get_token_auth_dependency()

    mock_auth = Mock()
    mock_auth.credentials = "valid.jwt.token"

    result = await dependency(mock_auth)
    assert result is None
    mock_is_jwt_valid.assert_called_once()


@pytest.mark.asyncio
@patch.dict(
    os.environ,
    {
        "ANYVAR_AUTH_TOKEN_LIST": "token1",
        "ANYVAR_AUTH_ISSUER_URL": "https://issuer.example.com",
        "ANYVAR_AUTH_JWKS_URI": "https://example.com/jwks",
    },
)
@patch("anyvar.restapi.auth.is_jwt_token_valid")
async def test_check_bearer_token_both_validations_fail(mock_is_jwt_valid):
    """Test check_bearer_token rejects when both literal and JWT validation fail."""
    mock_is_jwt_valid.return_value = False

    dependency = get_token_auth_dependency()

    mock_auth = Mock()
    mock_auth.credentials = "invalid_token"

    with pytest.raises(HTTPException) as exc_info:
        await dependency(mock_auth)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token"
