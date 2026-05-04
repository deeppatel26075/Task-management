"""
routes/jwt_routes.py
JWT Authentication endpoints for Project PA REST API.

Provides stateless token-based auth so external clients (Postman, mobile apps,
third-party integrations) can authenticate without a browser session.

Endpoints:
    POST /api/v1/auth/login    → obtain access + refresh tokens
    POST /api/v1/auth/refresh  → exchange refresh token for new access token
    GET  /api/v1/auth/me       → return current user profile (JWT-protected)
    POST /api/v1/auth/logout   → revoke current token (client-side; documented)
"""
import logging

from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
)
from werkzeug.security import check_password_hash

from models.user import User

logger = logging.getLogger(__name__)

jwt_bp = Blueprint("jwt_auth", __name__, url_prefix="/api/v1/auth")


def _error(message: str, code: int = 400):
    return jsonify({"success": False, "error": message}), code


def _ok(data, code: int = 200):
    return jsonify({"success": True, "data": data}), code


# ---------------------------------------------------------------------------
# POST /api/v1/auth/login
# ---------------------------------------------------------------------------
@jwt_bp.route("/login", methods=["POST"])
def jwt_login():
    """
    Obtain JWT access and refresh tokens.

    Body (JSON):
        email     (required) string
        password  (required) string

    Returns:
        access_token   — short-lived (15 min), use in Authorization: Bearer header
        refresh_token  — long-lived (30 days), use to get new access_token
        user           — basic user info
    """
    body = request.get_json(silent=True) or {}
    email    = (body.get("email") or "").strip()
    password = body.get("password", "")

    if not email or not password:
        return _error("'email' and 'password' are required")

    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, password):
        logger.warning("JWT login failed for: %s", email)
        return _error("Invalid email or password", 401)

    access_token  = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    logger.info("JWT login success: user=%s", user.id)
    return _ok({
        "access_token":  access_token,
        "refresh_token": refresh_token,
        "token_type":    "Bearer",
        "user":          user.to_dict(),
    })


# ---------------------------------------------------------------------------
# POST /api/v1/auth/refresh
# ---------------------------------------------------------------------------
@jwt_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def jwt_refresh():
    """
    Exchange a refresh token for a new access token.

    Header:
        Authorization: Bearer <refresh_token>
    """
    user_id      = get_jwt_identity()
    access_token = create_access_token(identity=user_id)
    logger.info("JWT refresh: user=%s", user_id)
    return _ok({"access_token": access_token, "token_type": "Bearer"})


# ---------------------------------------------------------------------------
# GET /api/v1/auth/me
# ---------------------------------------------------------------------------
@jwt_bp.route("/me", methods=["GET"])
@jwt_required()
def jwt_me():
    """
    Return the authenticated user's profile.

    Header:
        Authorization: Bearer <access_token>
    """
    user_id = int(get_jwt_identity())
    user    = User.query.get(user_id)
    if not user:
        return _error("User not found", 404)
    return _ok(user.to_dict())


# ---------------------------------------------------------------------------
# POST /api/v1/auth/logout  (client-side — documented pattern)
# ---------------------------------------------------------------------------
@jwt_bp.route("/logout", methods=["POST"])
@jwt_required()
def jwt_logout():
    """
    Logout endpoint.
    JWT is stateless — the client should discard the token.
    For full server-side revocation, a token blocklist (Redis) would be added.
    This endpoint exists for API completeness and documentation purposes.
    """
    return _ok({"message": "Logged out. Discard your token client-side."})
