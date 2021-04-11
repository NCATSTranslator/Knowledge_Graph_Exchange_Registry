"""
KGE Archive OAuth2 User Authentication/Authorization Workflow (based on AWS Cognito)
"""
from os import getenv
from typing import Dict
from base64  import b64encode
from uuid import uuid4

import logging

from aiohttp import web

from kgea.server.config import get_app_config
from kgea.server.web_services.kgea_session import KgeaSession


logger = logging.getLogger(__name__)

# Master flag for simplified local development
DEV_MODE = getenv('DEV_MODE', default=False)

KGEA_APP_CONFIG = get_app_config()

# hack: short term state token cache
_state_cache = []


async def login_url(request: web.Request) -> str:
    """
    Sends an authentication request to specified
    OAuth2 login service (i.e. AWS Cognito)
    
    :param request:
    :param state: string state secret (to avoid CORS)
    :return: redirection to OAuth2 login service
    """
    state = str(uuid4())
    _state_cache.append(state)

    host = KGEA_APP_CONFIG['oauth2']['host']
    client_id = KGEA_APP_CONFIG['oauth2']['client_id']
    redirect_uri = KGEA_APP_CONFIG['oauth2']['site_uri'] + KGEA_APP_CONFIG['oauth2']['login_callback']

    return host + '/login?response_type=code&state=' + state + \
        '&client_id=' + client_id + '&redirect_uri=' + redirect_uri


def mock_user_attributes() -> Dict:
    # Stub implementation in DEV_MODE
    user_attributes: Dict = dict()
    user_attributes["user_id"] = 'translator'  # cognito:username?
    user_attributes["user_name"] = 'Mr. Trans L. Tor'  # not sure how to get this value(?)
    user_attributes["user_email"] = 'translator@ncats.nih.gov'
    return user_attributes


async def _get_user_attributes(request: web.Request, code: str) -> Dict:
    # Return user attributes from
    # AWS Cognito via retrieval
    # of the OAuth2 ID Token

    logger.debug("Entering _get_authorization(code: "+str(code)+")")

    user_attributes: Dict = dict()

    # short term override of the Work-In-Progress code
    if DEV_MODE:
        user_attributes = mock_user_attributes()
    else:
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
        #

        host = KGEA_APP_CONFIG['oauth2']['host']
        redirect_uri = KGEA_APP_CONFIG['oauth2']['site_uri'] + KGEA_APP_CONFIG['oauth2']['login_callback']
        client_id = KGEA_APP_CONFIG['oauth2']['client_id']
        client_secret = KGEA_APP_CONFIG['oauth2']['client_secret']

        token_url = host + '/oauth2/token?' + \
            'grant_type=authorization_code&code=' + code + \
            '&redirect_uri=' + redirect_uri + \
            '&client_id=' + client_id

        # See https://docs.aws.amazon.com/cognito/latest/developerguide/token-endpoint.html
        #
        #   -H 'Accept-Encoding: gzip, deflate' \
        #   -H 'Authorization: Basic ' + Base64Encode(client_id:client_secret)
        #   -H 'Content-Type: application/x-www-form-urlencoded'
        #
        # One needs to set the Authorization header for this request as
        # Basic BASE64(CLIENT_ID:CLIENT_SECRET), where BASE64(CLIENT_ID:CLIENT_SECRET)
        # is the base64 representation of the app client ID and app client secret, concatenated with a colon.
        #
        credentials = client_id+':'+client_secret
        authorization = b64encode(credentials.encode('utf-8')).decode('utf-8')
        headers = {
            'Accept-Encoding': 'gzip, deflate',
            'Authorization': 'Basic ' + authorization,
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        async with KgeaSession.get_global_session().post(token_url, headers=headers) as resp:
            data = await resp.json()

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


async def authenticate_user(code: str, state: str):
    """
    :param code: value from Oauth2 authenticated callback request endpoint handler
    :param state: value from Oauth2 authenticated callback request endpoint handler
    :return: dictionary of AWS Cognito OAuth2 ID token attributes obtained for an login_url user; None if unsuccessful
    """

    # Establish session here if there is a valid access code & state variable?
    if state in _state_cache:
        
        # state 'secrets' are only got for one request
        _state_cache.remove(state)
        
        # now, check the returned code for authorization
        if code:
            user_attributes = await _get_user_attributes(code)
            return user_attributes
            
    return None


async def logout_url(request: web.Request) -> str:
    """
    Redirection to signal logout_url at the Oauth2 host
    :param request:
    :return: redirection exception to OAuth2 service
    """
    return \
        KGEA_APP_CONFIG['oauth2']['host'] + \
        '/logout_url?client_id=' + \
        KGEA_APP_CONFIG['oauth2']['client_id'] + \
        '&logout_uri=' + \
        KGEA_APP_CONFIG['oauth2']['site_uri']
