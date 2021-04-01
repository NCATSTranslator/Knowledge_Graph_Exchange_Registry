from os import getenv
from typing import List

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

from kgea.server.config import get_app_config
from .kgea_users import (
    authenticate,
    authenticate_user,
    logout
)

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


async def kge_landing_page(request: web.Request) -> web.Response:
    """Display landing page.

    :param request:
    :type request: web.Request

    :rtype: login web.Response login page or redirect to authenticated /home page
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


async def get_kge_home(request: web.Request) -> web.Response:
    """Get default landing page

    :param request:
    :type request: web.Request

    :rtype: web.Response
    """
    session = await get_session(request)
    if not session.empty:
        response = aiohttp_jinja2.render_template('home.html', request=request, context={})
        return await with_session(request, response)
    else:
        # If session is not active, then just a await redirect
        # directly back to unauthenticated landing page
        await redirect(request, LANDING)


async def kge_client_authentication(request: web.Request):
    """Process client authentication
    :param request:
    :type request: web.Request
    """
    user_attributes = await authenticate_user(request)
    if user_attributes:

        await initialize_user_session(request, user_attributes=user_attributes)
        
        # if active session and no exception raised, then
        # redirect to the home page, with a session cookie
        await redirect(request, HOME, active_session=True)
    else:
        # If authentication conditions are not met, then
        # simply redirect back to public landing page
        await redirect(request, LANDING)


async def kge_login(request: web.Request):
    """Process client user login
    :param request:
    :type request: web.Request
    """
    if DEV_MODE:
        # DEV_MODE workaround by-passes full external authentication
        await initialize_user_session(request)

        # then redirect to an authenticated home page
        await redirect(request, HOME, active_session=True)

    await authenticate(request)


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
            await logout(request)
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
