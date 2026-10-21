import hmac

from fastapi import Header, HTTPException, status

from app.config import get_settings

settings = get_settings()


def telegram_allowed(telegram_id: int) -> bool:
    return telegram_id in settings.allowed_telegram_ids


def require_api_identity(
    x_api_key: str = Header(default=""),
    x_owner_telegram_id: int | None = Header(default=None),
) -> int:
    if not hmac.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    if x_owner_telegram_id is None or not telegram_allowed(x_owner_telegram_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner not allowed")
    return x_owner_telegram_id
