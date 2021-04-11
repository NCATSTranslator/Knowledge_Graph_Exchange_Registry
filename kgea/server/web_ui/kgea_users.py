"""
KGE Archive OAuth2 User Authentication/Authorization Workflow (based on AWS Cognito)
"""
from os import getenv
from typing import Dict
import json

from base64  import b64encode, b64decode
from uuid import uuid4

import logging

from aiohttp import web

from kgea.server.config import get_app_config
from kgea.server.web_services.kgea_session import KgeaSession

logger = logging.getLogger(__name__)

logger.setLevel(logging.DEBUG)

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
    user_attributes["preferred_username"] = 'translator'
    user_attributes["name"] = 'Mr. Trans L. Tor'
    user_attributes["email"] = 'translator@ncats.nih.gov'
    return user_attributes


async def _get_user_attributes(request: web.Request, code: str) -> Dict:
    # Return user attributes from
    # AWS Cognito via retrieval
    # of the OAuth2 ID Token

    logger.debug("Entering _get_user_attributes(code: "+str(code)+")")

    user_attributes: Dict = dict()

    # short term override of the Work-In-Progress code
    if DEV_MODE:
        user_attributes = mock_user_attributes()

    else:
        # See the AWS Cognito documentation about ID tokens:
        # https://aws.amazon.com/blogs/mobile/how-to-use-cognito-pre-token-generators-to-customize-claims-in-id-tokens/
        #
        # Given the authorization code Query parameter, the next step is to exchange it
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

        logger.debug("_get_user_attributes(): token_url: "+token_url)

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
        token_headers = {
            'Accept-Encoding': 'gzip, deflate',
            'Authorization': 'Basic ' + authorization,
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        logger.debug("_get_user_attributes(): Authorization: " + authorization)

        logger.debug("_get_user_attributes(): POSTing to /oauth2/token ...")

        async with KgeaSession.get_global_session().post(token_url, headers=token_headers) as resp:
            # Once the POST Request is successful we should get a
            # response with id_token, access_token and refresh_token.
            #
            # {
            #     "id_token":"XXXXXXx.....XXXXXXX",
            #     "access_token":"XXXXXXx.....XXXXXXX",
            #     "refresh_token":"XXXXXXx.....XXXXXXX",
            #     "expires_in": 3600,
            #     "token_type": "Bearer"
            # }
            #
            encoded_data = await resp.json()

            logger.debug("\t... returned:\n\n"+str(encoded_data))

            # The access and refresh tokens with metadata are
            # directly returned among the user attributes
            user_attributes["access_token"] = encoded_data['access_token']

            # TODO: how do I need to handle access_token refresh after expiration?
            user_attributes["refresh_token"] = encoded_data['refresh_token']
            user_attributes["expires_in"] = encoded_data['expires_in']
            user_attributes["token_type"] = encoded_data['token_type']

            #
            # Hmm... perhaps I don't care about the ID token per say, but
            # actually need to access the /oauth2/userInfo endpoint
            # to get the actual user attributes of interest
            #
            # Then by decoding the JWT ID Token, we will get at the actual
            # user attributes and associated metadata, like the following:
            #
            # {
            #     "at_hash": "4FNVgmQsm5m_h9VC_OFFuQ",
            #     "sub": "472ff4cd-9b09-46b5-8680-e8c5d6025d38",
            #     "aud": "55pb79dl8gm0i1ho9hdre91r3k",
            #     "token_use": "id",
            #     "auth_time": 1576816174,
            #     "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_qyS1sSLiQ",
            #     "cognito:username": "test-user",
            #     "exp": 1576819774,
            #     "iat": 1576816174,
            #     "email": "test-user@amazon.com“
            # }
            #
            # jwt_id_token = encoded_data['id_token']
            # decoded_jwt_id_token: str = b64decode(jwt_id_token).decode('utf-8')
            # user_data: Dict = json.loads(decoded_jwt_id_token)
            #
            # logger.debug("\twith decoded user data:\n\n"+str(user_data))

        #  GET https://<your-user-pool-domain>/oauth2/userInfo
        # Authorization: Bearer <access_token>
        user_info_url = host + '/oauth2/token'
        user_info_headers = {
            "Authorization": 'Bearer ' + user_attributes["access_token"]
        }

        async with KgeaSession.get_global_session().get(user_info_url, headers=user_info_headers) as resp:
            # Should GET something ike the following response:
            #
            # HTTP/1.1 200 OK
            # Content-Type: application/json;charset=UTF-8
            # {
            #    "sub": "248289761001",
            #    "name": "Jane Doe",
            #    "given_name": "Jane",
            #    "family_name": "Doe",
            #    "preferred_username": "j.doe",
            #    "email": "janedoe@example.com"
            # }
            #
            user_data = await resp.json()

            logger.debug("_get_user_attributes(): GETing oauth2/userInfo ...")
            logger.debug("\t... returned:\n\n" + str(user_data))

            for key, value in user_data:
                user_attributes[key] = value

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
