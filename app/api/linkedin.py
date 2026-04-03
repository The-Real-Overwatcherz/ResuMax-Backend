"""
ResuMax Backend — LinkedIn OAuth Routes
Handles LinkedIn Sign In with OpenID Connect to fetch user profile data.
"""

import httpx
import structlog
from urllib.parse import urlencode
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from app.config import get_settings

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/auth/linkedin", tags=["linkedin"])

LINKEDIN_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_USERINFO_URL = "https://api.linkedin.com/v2/userinfo"


@router.get("/login")
async def linkedin_login():
    """
    Redirect the user to LinkedIn's OAuth consent screen.
    """
    settings = get_settings()

    params = {
        "response_type": "code",
        "client_id": settings.linkedin_client_id,
        "redirect_uri": settings.linkedin_redirect_uri,
        "scope": "openid profile email",
        "state": "resumax_linkedin",
    }

    auth_url = f"{LINKEDIN_AUTH_URL}?{urlencode(params)}"
    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def linkedin_callback(code: str = "", error: str = "", state: str = ""):
    """
    LinkedIn redirects here after user consents.
    Exchanges the auth code for an access token, fetches profile, and
    redirects to the frontend with the profile data as query params.
    """
    settings = get_settings()

    if error:
        logger.warning("linkedin_oauth_error", error=error)
        return RedirectResponse(
            url=f"{settings.frontend_url}/create?linkedin_error={error}"
        )

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            LINKEDIN_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.linkedin_redirect_uri,
                "client_id": settings.linkedin_client_id,
                "client_secret": settings.linkedin_client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if token_resp.status_code != 200:
            logger.error("linkedin_token_exchange_failed", status=token_resp.status_code, body=token_resp.text)
            return RedirectResponse(
                url=f"{settings.frontend_url}/create?linkedin_error=token_exchange_failed"
            )

        token_data = token_resp.json()
        access_token = token_data.get("access_token")

        if not access_token:
            return RedirectResponse(
                url=f"{settings.frontend_url}/create?linkedin_error=no_access_token"
            )

        # Fetch user profile via OpenID Connect userinfo
        userinfo_resp = await client.get(
            LINKEDIN_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )

        if userinfo_resp.status_code != 200:
            logger.error("linkedin_userinfo_failed", status=userinfo_resp.status_code)
            return RedirectResponse(
                url=f"{settings.frontend_url}/create?linkedin_error=userinfo_failed"
            )

        profile = userinfo_resp.json()

    # Extract profile fields
    full_name = profile.get("name", "")
    email = profile.get("email", "")
    picture = profile.get("picture", "")
    given_name = profile.get("given_name", "")
    family_name = profile.get("family_name", "")

    logger.info("linkedin_profile_fetched", name=full_name, email=email)

    # Redirect to frontend with profile data as query params
    params = urlencode({
        "linkedin_name": full_name,
        "linkedin_email": email,
        "linkedin_picture": picture,
        "linkedin_given_name": given_name,
        "linkedin_family_name": family_name,
        "linkedin_success": "true",
    })

    return RedirectResponse(url=f"{settings.frontend_url}/create?{params}")
