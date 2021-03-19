from os import getenv
from uuid import uuid4

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

from aiohttp import web
import aiohttp_jinja2

from aiohttp_session import get_session

from kgea.server.web_services.kgea_session import (
    initialize_user_session, redirect, with_session
)

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
kgea_app_config = get_app_config()

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
else:
    # Production NGINX resolves the relative path otherwise?
    ARCHIVE_REGISTRATION_FORM_ACTION = ARCHIVE_PATH+"register"
    UPLOAD_FORM_ACTION = ARCHIVE_PATH+"upload"


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
    # Can't seem to get the session cookie via any
    # redirection so use a URL query string workaround?
    # uid = request.query.get('uid')
    # if uid:
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


# hack: short term state dictionary
_state_cache = []


async def kge_client_authentication(request: web.Request):
    """Process client authentication

    :param request:
    :type request: web.Request
    """
    code = request.query['code']
    state = request.query['state']

    # Establish session here if there
    # is a valid access code & state variable?
    if state in _state_cache:

        # state 'secrets' are only got for one request
        _state_cache.remove(state)

        # now, check the returned code for authorization
        if code:

            # Let everything through for the initial iteration
            # Need to tie into AWS Cognito validation
            # TODO: check AWS authorization token
            authenticated = True  # stub implementation of validation

            if authenticated:
    
                await initialize_user_session(request)
                
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
        kgea_app_config['oauth2']['host'] + \
        '/login?response_type=code' + \
        '&state=' + state + \
        '&client_id=' + \
        kgea_app_config['oauth2']['client_id'] + \
        '&redirect_uri=' + \
        kgea_app_config['oauth2']['site_uri'] + \
        kgea_app_config['oauth2']['login_callback']

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
                kgea_app_config['oauth2']['host'] + \
                '/logout?client_id=' + \
                kgea_app_config['oauth2']['client_id'] + \
                '&logout_uri=' + \
                kgea_app_config['oauth2']['site_uri']
    
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
            "registration_action": ARCHIVE_REGISTRATION_FORM_ACTION
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

        submitter = request.query.get('submitter', default='')
        kg_name = request.query.get('kg_name', default='')

        # TODO guard against absent kg_name
        # TODO guard against invalid kg_name (check availability in bucket)
        # TODO redirect to register_form with given optional param as the entered kg_name

        context = {
            "upload_action": UPLOAD_FORM_ACTION,
            "kg_name": kg_name,
            "submitter": submitter
        }
        response = aiohttp_jinja2.render_template('upload.html', request=request, context=context)
        return await with_session(request, response)

    else:
        # If session is not active, then just a redirect
        # directly back to unauthenticated landing page
        await redirect(request, LANDING)
