import logging

logger = logging.getLogger("auth")


def log_auth_event(action: str, request, user=None, status: str = "success", extra: dict | None = None):
    """Emit a structured auth event with action, user, ip, and status."""
    ip = request.META.get("REMOTE_ADDR")
    payload = {
        "action": action,
        "ip": ip,
        "status": status,
    }
    if user is not None:
        payload["user_id"] = getattr(user, "id", None)
        payload["username"] = getattr(user, "username", None)
        payload["email"] = getattr(user, "email", None)
    if extra:
        payload.update(extra)
    logger.info(payload)
