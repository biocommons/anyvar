Authentication Configuration
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

.. raw:: html

   <style>
   .wy-table-responsive table td, .wy-table-responsive table th {
       white-space: normal;
   }
   </style>

AnyVar supports optional bearer token authentication for REST API endpoints. When enabled, all API requests must include a valid bearer token in the ``Authorization`` header. Authentication can be disabled by leaving all authentication environment variables unset.

Authentication Modes
====================

AnyVar supports two modes of authentication that can be used independently or in combination:

1. **Literal Token Validation**: Validate against a predefined list of static tokens
2. **JWT Token Validation**: Validate JSON Web Tokens (JWT) using OpenID Connect (OIDC) workflow

If neither mode is configured (all authentication environment variables are unset), authentication is disabled and no bearer token is required.

Authentication Behavior
=======================

When authentication is enabled, AnyVar validates bearer tokens as follows:

- If ``ANYVAR_AUTH_TOKEN_LIST`` is configured, the token is checked against the list of allowed literal tokens
- If JWT validation is configured (``ANYVAR_AUTH_ISSUER_URL`` and ``ANYVAR_AUTH_JWKS_URI`` are set), the token is validated as a JWT
- If the token matches either validation method, the request is authorized
- If the token fails both validation methods (or if no validation methods are configured but a token is provided), a 401 Unauthorized response is returned

JWT tokens are cached after successful validation to improve performance and reduce repeated validation overhead. The cache automatically purges expired tokens every hour.

Configuration Parameters
========================

Literal Token Authentication
-----------------------------

Use this mode to validate against a static list of pre-shared tokens.

.. list-table::
   :header-rows: 1

   * - Environment Variable
     - Description
   * - ``ANYVAR_AUTH_TOKEN_LIST``
     - Comma-separated list of literal bearer tokens that are accepted for authentication. Example: ``"token1,token2,token3"``

JWT Token Authentication
------------------------

Use this mode to validate JWT tokens issued by an OpenID Connect provider. Both ``ANYVAR_AUTH_ISSUER_URL`` and ``ANYVAR_AUTH_JWKS_URI`` must be set for JWT validation to be enabled.

Required Parameters
^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1

   * - Environment Variable
     - Description
   * - ``ANYVAR_AUTH_ISSUER_URL``
     - JWT issuer URL (``iss`` claim). The token's ``iss`` claim must match this value exactly.
   * - ``ANYVAR_AUTH_JWKS_URI``
     - JWKS (JSON Web Key Set) URI used to retrieve public keys for JWT signature validation. Example: ``"https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys"``

Optional Claim Validation
^^^^^^^^^^^^^^^^^^^^^^^^^^

These optional parameters enable validation of specific JWT claims. If set, tokens must satisfy the configured constraints:

.. list-table::
   :header-rows: 1

   * - Environment Variable
     - Description
   * - ``ANYVAR_AUTH_AUDIENCES``
     - Comma-separated list of allowed audience values (``aud`` claim). At least one audience in the token must match one of the configured audiences.
   * - ``ANYVAR_AUTH_APPIDS``
     - Comma-separated list of allowed application IDs (``appid`` claim). The token's ``appid`` claim must match one of the configured values.
   * - ``ANYVAR_AUTH_SCOPES``
     - Comma-separated list of required scopes (``scope`` claim). The token must contain at least one of the configured scopes.
   * - ``ANYVAR_AUTH_EMAILS``
     - Comma-separated list of allowed email addresses (``email`` claim). The token's ``email`` claim must match one of the configured values (case-insensitive).
   * - ``ANYVAR_AUTH_SUBJECTS``
     - Comma-separated list of allowed subject values (``sub`` claim). The token's ``sub`` claim must match one of the configured values.

JWT Token Requirements
^^^^^^^^^^^^^^^^^^^^^^

All JWT tokens must include the following claims:

- ``iat`` (issued at time)
- ``exp`` (expiration time)
- ``iss`` (issuer)
- ``sub`` (subject)

Tokens are validated for signature authenticity, expiration, and issuer. The signature is verified using RS256 algorithm with public keys retrieved from the JWKS URI.

Example Configuration
=====================

Literal Token Authentication
-----------------------------

.. code-block:: bash

   # Enable authentication with literal tokens
   ANYVAR_AUTH_TOKEN_LIST="my-secret-token-1,my-secret-token-2"

JWT Token Authentication with Azure AD
---------------------------------------

.. code-block:: bash

   # Enable JWT authentication with Azure AD
   ANYVAR_AUTH_ISSUER_URL="https://login.microsoftonline.com/{tenant-id}/v2.0"
   ANYVAR_AUTH_JWKS_URI="https://login.microsoftonline.com/{tenant-id}/discovery/v2.0/keys"
   ANYVAR_AUTH_AUDIENCES="api://{client-id}"
   ANYVAR_AUTH_SCOPES="access_as_user"

Combined Authentication
-----------------------

.. code-block:: bash

   # Accept both literal tokens and JWT tokens
   ANYVAR_AUTH_TOKEN_LIST="admin-token-123"
   ANYVAR_AUTH_ISSUER_URL="https://login.microsoftonline.com/{tenant-id}/v2.0"
   ANYVAR_AUTH_JWKS_URI="https://login.microsoftonline.com/{tenant-id}/discovery/v2.0/keys"
   ANYVAR_AUTH_AUDIENCES="api://{client-id}"

Using Bearer Tokens
===================

When authentication is enabled, include the bearer token in the ``Authorization`` header of all API requests:

.. code-block:: bash

   curl -H "Authorization: Bearer YOUR_TOKEN_HERE" \
        https://your-anyvar-instance.com/variation

Without a valid token, requests will receive a 401 Unauthorized response.

Security Considerations
=======================

- **Keep tokens secure**: Never commit literal tokens to version control. Use environment variables or secret management systems.
- **Use HTTPS**: Always deploy AnyVar with HTTPS in production to protect tokens in transit.
- **Token rotation**: Regularly rotate literal tokens and use short-lived JWT tokens when possible.
- **Principle of least privilege**: Configure claim validation (audiences, scopes, emails, subjects) to restrict access to only authorized users and applications.
- **Monitor authentication logs**: Review authentication logs for unauthorized access attempts.
