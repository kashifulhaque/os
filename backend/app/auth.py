"""Identity verified by the trusted reverse proxy's Authelia headers."""

import hmac

from fastapi import Depends, HTTPException, Request, status

from .config import Settings, get_settings


def current_user(
    request: Request, settings: Settings = Depends(get_settings)
) -> str:
    """Return the Authelia username vouched for by the trusted Caddy proxy."""
    secret = settings.sso_proxy_secret
    sent = request.headers.get("x-sso-proxy", "")
    name = request.headers.get("remote-user", "").strip()
    if not secret or not hmac.compare_digest(sent.encode(), secret.encode()) or not name:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not signed in"
        )
    return settings.sso_names.get(name.lower(), name)
