"""
KGE Archive OAuth2 User Authentication/Authorization Workflow (based on AWS Cognito)
"""
from typing import Dict
from uuid import uuid4

import logging

from aiohttp import web

from kgea.server.config import get_app_config
from kgea.server.web_services.kgea_session import (
    redirect,
    report_error
)

logger = logging.getLogger(__name__)

KGEA_APP_CONFIG = get_app_config()

# hack: short term state token cache
_state_cache = []


async def authenticate(request: web.Request):
    """
    Sends an authentication request to specified
    OAuth2 login service (i.e. AWS Cognito)
    
    :param request:
    :param state: string state secret (to avoid CORS)
    :return: redirection to OAuth2 login service
    """
    state = str(uuid4())
    _state_cache.append(state)
    
    login_url = \
        KGEA_APP_CONFIG['oauth2']['host'] + \
        '/login?response_type=code' + \
        '&state=' + state + \
        '&client_id=' + \
        KGEA_APP_CONFIG['oauth2']['client_id'] + \
        '&redirect_uri=' + \
        KGEA_APP_CONFIG['oauth2']['site_uri'] + \
        KGEA_APP_CONFIG['oauth2']['login_callback']
    
    await redirect(request, login_url)


async def _get_authenticated_user_token(code: str) -> Dict:
    logger.debug("Entering _get_authorization(code: "+code+")")
    user_attributes: Dict = dict()
    #
    # See https://aws.amazon.com/blogs/mobile/how-to-use-cognito-pre-token-generators-to-customize-claims-in-id-tokens/
    #
    # got the authorization code Query parameter, the next step is to exchange it
    # for user pool tokens. The exchange occurs by submitting a POST request with
    # code Query parameter, client Id and Authorization Header like below.
    #
    # # HTTP Request (including valid token with "email" scope)
    # $ curl -X POST \
    #   'https://<Cognito User Pool Domain>/oauth2/token?
    #   grant_type=authorization_code&
    #   code=8a24d2df-07b9-41e1-bb5c-c269e87838df&
    #   redirect_uri=http://localhost&
    #   client_id=55pb79dl8gm0i1ho9hdrXXXXXX&scope=openid%20email' \
    #   -H 'Accept-Encoding: gzip, deflate' \
    #   -H 'Authorization: Basic NTVwYj......HNXXXXXXX' \
    #   -H 'Content-Type: application/x-www-form-urlencoded'
    #
    # Ssh
    #
    # We would need to set the Authorization header for this request as
    # Basic BASE64(CLIENT_ID:CLIENT_SECRET), where BASE64(CLIENT_ID:CLIENT_SECRET)
    # is the base64 representation of the app client ID and app client secret, concatenated with a colon.
    #
    # Once the POST Request is successful we should get a response with id_token, access_token and refresh_token.
    #
    # {
    #     "id_token":"XXXXXXx.....XXXXXXX",
    #     "access_token":"XXXXXXx.....XXXXXXX",
    #     "refresh_token":"XXXXXXx.....XXXXXXX",
    #     "expires_in": 3600,
    #     "token_type": "Bearer"
    # }
    #
    # JSON
    #
    # Decoding the JWT ID Token will yield the following results with custom claim pet_preference added to the Id Token.
    #
    # {
    #     "at_hash": "4FNVgmQsm5m_h9VC_OFFuQ",
    #     "sub": "472ff4cd-9b09-46b5-8680-e8c5d6025d38",
    #     "aud": "55pb79dl8gm0i1ho9hdre91r3k",
    #     "token_use": "id",
    #     "auth_time": 1576816174,
    #     "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_qyS1sSLiQ",
    #     "pet_preference": "dogs",
    #     "cognito:username": "test-user",
    #     "exp": 1576819774,
    #     "iat": 1576816174,
    #     "email": "test-user@amazon.com“
    # }
    #
    return user_attributes


async def authenticate_user(request: web.Request):
    """
    :param request: from Oauth2 callback request endpoint handler
    :return: dictionary of identity token attributes obtained for an authenticate user; None if unsuccessful
    """
    
    error = request.query.get('error', default='')
    if error:
        error_description = request.query.get('error_description', default='')
        await report_error(request, "User not authenticated. Reason: " + str(error_description))
    
    code = request.query.get('code', default='')
    state = request.query.get('state', default='')
    
    if not (code and state):
        await report_error(request, "User not authenticated. Reason: no authorization code returned?")
    
    # Establish session here if there is a valid access code & state variable?
    if state in _state_cache:
        
        # state 'secrets' are only got for one request
        _state_cache.remove(state)
        
        # now, check the returned code for authorization
        if code:
            user_attributes = await _get_authenticated_user_token(code)
            return user_attributes
            
    return None


async def logout(request: web.Request):
    """
    Redirection to signal logout at the Oauth2 host
    :param request:
    :return: redirection exception to OAuth2 service
    """
    logout_url = \
        KGEA_APP_CONFIG['oauth2']['host'] + \
        '/logout?client_id=' + \
        KGEA_APP_CONFIG['oauth2']['client_id'] + \
        '&logout_uri=' + \
        KGEA_APP_CONFIG['oauth2']['site_uri']
    
    await redirect(request, logout_url)
