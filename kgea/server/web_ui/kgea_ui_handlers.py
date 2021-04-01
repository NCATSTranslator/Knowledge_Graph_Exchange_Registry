from os import getenv
from typing import List, Dict
from uuid import uuid4
from datetime import datetime

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

from aiohttp import web
import aiohttp_jinja2

from aiohttp_session import get_session

from kgea.server.web_services.kgea_session import (
    initialize_user_session,
    redirect,
    with_session,
    report_error
)

from ..registry.Registry import KgeaRegistry

#############################################################
# Application Configuration
#############################################################

from kgea.server.config import get_app_config

import logging

# Master flag for local development runs bypassing authentication and other production processes
DEV_MODE = getenv('DEV_MODE', default=False)

logger = logging.getLogger(__name__)
if DEV_MODE:
    logger.setLevel(logging.DEBUG)

# Opaquely access the configuration dictionary
KGEA_APP_CONFIG = get_app_config()

#############################################################
# Site Controller Handlers
#
# Insert imports and return calls into web_ui/__init__.py:
#
# from ..kge_ui_handlers import (
#     kge_landing_page,
#     kge_login,
#     kge_client_authentication,
#     get_kge_home,
#     kge_logout
# )
#############################################################

# This is the home page path,
# should match the API path spec
LANDING = '/'
HOME = '/home'

ARCHIVE_PATH = '/archive/'

if DEV_MODE:
    # Point to http://localhost:8080 for Archive process host for local testing
    ARCHIVE_REGISTRATION_FORM_ACTION = 'http://localhost:8080'+ARCHIVE_PATH+"register"
    UPLOAD_FORM_ACTION = 'http://localhost:8080'+ARCHIVE_PATH+"upload"
    PUBLISH_FILE_SET_ACTION = 'http://localhost:8080'+ARCHIVE_PATH+"publish"
else:
    # Production NGINX resolves the relative path otherwise?
    ARCHIVE_REGISTRATION_FORM_ACTION = ARCHIVE_PATH+"register"
    UPLOAD_FORM_ACTION = ARCHIVE_PATH+"upload"
    PUBLISH_FILE_SET_ACTION = ARCHIVE_PATH+"publish"


async def kge_landing_page(request: web.Request) -> web.Response:  # noqa: E501
    """Display landing page.

     # noqa: E501

    :param request:
    :type request: web.Request

    :rtype: str
    """

    session = await get_session(request)
    if not session.empty:
        # if active session and no exception raised, then
        # redirect to the home page, with a session cookie
        await redirect(request, HOME, active_session=True)
    else:
        # Session is not active, then render the login page
        response = aiohttp_jinja2.render_template('login.html', request=request, context={})
        return response


async def get_kge_home(request: web.Request, uid: str = None) -> web.Response:  # noqa: E501
    """Get default landing page

     # noqa: E501

    :param request:
    :type request: web.Request
    :param uid:
    :type uid: str

    :rtype: web.Response
    """
    session = await get_session(request)
    if not session.empty:
        
        # TODO: verify that all local session data is reloaded?
        # reconstituting the session
        # await initialize_user_session(request, uid)
        
        response = aiohttp_jinja2.render_template('home.html', request=request, context={})
        return await with_session(request, response)
    else:
        # If session is not active, then just a await redirect
        # directly back to unauthenticated landing page
        await redirect(request, LANDING)


async def get_authorization(code: str) -> Dict:
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


# hack: short term state dictionary
_state_cache = []


async def kge_client_authentication(request: web.Request):
    """Process client authentication

    :param request:
    :type request: web.Request
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

            user_attributes = await get_authorization(code)

            if user_attributes:
    
                await initialize_user_session(request, user_attributes=user_attributes)
                
                # if active session and no exception raised, then
                # redirect to the home page, with a session cookie
                await redirect(request, HOME, active_session=True)

    # If authentication conditions are not met, then
    # simply redirect back to public landing page
    await redirect(request, LANDING)


async def kge_login(request: web.Request):  # noqa: E501
    """Process client user login

     # noqa: E501

    :param request:
    :type request: web.Request
    """

    if DEV_MODE:
        
        await initialize_user_session(request)

        # then redirect to an authenticated home page
        await redirect(request, HOME, active_session=True)
      
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


async def kge_logout(request: web.Request):
    """Process client user logout

    :param request:
    :type request: web.Request
    """
    session = await get_session(request)
    if not session.empty:

        session.invalidate()
        
        if DEV_MODE:
            # Just bypass the AWS Cognito and directly redirect to
            # the unauthenticated landing page after session deletion
            await redirect(request, LANDING)
        
        else:

            # ...then redirect to signal logout at the Oauth2 host
            logout_url = \
                KGEA_APP_CONFIG['oauth2']['host'] + \
                '/logout?client_id=' + \
                KGEA_APP_CONFIG['oauth2']['client_id'] + \
                '&logout_uri=' + \
                KGEA_APP_CONFIG['oauth2']['site_uri']
    
            await redirect(request, logout_url)
    else:
        # If session is not active, then just a await redirect
        # directly back to unauthenticated landing page
        await redirect(request, LANDING)


#############################################################
# Upload Controller Handlers
#
# Insert imports and return calls into into web_ui/__init__.py:
#
# from ..kge_handlers import (
#     get_kge_registration_form,
#     get_kge_file_upload_form
# )
#############################################################


async def get_kge_registration_form(request: web.Request) -> web.Response:  # noqa: E501
    """Get web form for specifying KGE File Set name and submitter

     # noqa: E501

    :param request:
    :type request: web.Request

    :rtype: web.Response
    """
    session = await get_session(request)
    if not session.empty:
        #  TODO: if user is authenticated, why do we need to ask them for a submitter name?
        context = {
            "registration_action": ARCHIVE_REGISTRATION_FORM_ACTION,
            "kg_version": datetime.now().strftime('%Y-%m-%d')  # defaults to today's date "timestamp"
        }
        response = aiohttp_jinja2.render_template('register.html', request=request, context=context)
        return await with_session(request, response)
    else:
        # If session is not active, then just a redirect
        # directly back to unauthenticated landing page
        await redirect(request, LANDING)


async def get_kge_file_upload_form(request: web.Request) -> web.Response:
    """Get web form for specifying KGE File Set upload

    :param request:
    :type request: web.Request
    """
    session = await get_session(request)
    if not session.empty:

        kg_id = request.query.get('kg_id', default='')
        kg_name = request.query.get('kg_name', default='')
        kg_version = request.query.get('kg_version', default='')
        submitter = request.query.get('submitter', default='')
        
        missing: List[str] = []
        if not kg_id:
            missing.append("kg_id")
        if not kg_name:
            missing.append("kg_name")
        if not kg_version:
            missing.append("kg_version")
        if not submitter:
            missing.append("submitter")

        if missing:
            await report_error( request, "get_kge_file_upload_form() - missing parameter(s): " + ", ".join(missing))

        context = {
            "kg_id": kg_id,
            "kg_name": kg_name,
            "kg_version": kg_version,
            "submitter": submitter,
            "upload_action": UPLOAD_FORM_ACTION,
            "publish_file_set_action": PUBLISH_FILE_SET_ACTION
        }
        response = aiohttp_jinja2.render_template('upload.html', request=request, context=context)
        return await with_session(request, response)

    else:
        # If session is not active, then just a redirect
        # directly back to unauthenticated landing page
        await redirect(request, LANDING)
