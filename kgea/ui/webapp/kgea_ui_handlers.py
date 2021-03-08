from pathlib import Path
from typing import Dict
from uuid import uuid4

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

from string import Template
import re

from aiohttp import web
import aiohttp_jinja2

#############################################################
# Application Configuration
#############################################################

from .kgea_ui_config import resources

from .kgea_session import (
    create_session,
    valid_session,
    get_session,
    delete_session
)

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# @aiohttp_jinja2.template("home.html")
# class HomeHandler(web.View):
#
#     async def get(self):
#         return {}
#
#     async def post(self):
#         form = await self.request.post()
#         return {"name": form['name']}

#############################################################
# Site Controller Handlers
#
# Insert imports and return calls into ui/__init__.py:
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


def kge_landing_page(request: web.Request) -> web.Response:  # noqa: E501
    """Display landing page.

     # noqa: E501

    :param request:
    :type request: web.Request

    :rtype: str
    """
    param = await request.get()
    session_id = param['session']

    # validate the session key
    if valid_session(session_id):
        # then redirect to an authenticated home page
        authenticated_url = HOME + '?session=' + session_id
        raise web.HTTPFound(authenticated_url)
    else:
        # If session is not active, then
        # render login page (no Jinja parameterization)
        # return {}

        context = {}
        response = aiohttp_jinja2.render_template('login.html',
                                                  request,
                                                  context)
        return response


async def get_kge_home(request: web.Request):  # noqa: E501
    """Get default landing page

     # noqa: E501

    :param request:
    :type request: web.Request

    :rtype: web.Response
    """
    param = await request.get()
    session_id = param['session']

    # validate the session key
    if valid_session(session_id):
        context = {"session":  session_id}
        response = aiohttp_jinja2.render_template('home.html',
                                                  request,
                                                  context)
        return response
    else:
        # If session is not active, then just
        # redirect back to unauthenticated landing page
        raise web.HTTPFound(LANDING)

# hack: short term dictionary
_state_cache = []


async def kge_client_authentication(request: web.Request):  # noqa: E501
    """Process client authentication

     # noqa: E501

    :param request:
    :type request: web.Request
    :param code:
    :type code: str
    :param state:
    :type state: str
    """
    param = await request.get()
    code = param['code']
    state = param['state']

    # Establish session here if there
    # is a valid access code & state variable?
    if state in _state_cache:

        # state 'secrets' are only got for one request
        _state_cache.remove(state)

        # now, check the returned code for authorization
        if code:

            # TODO: check AWS authorization token

            # Let everything through for the initial iteration
            # Need to tie into AWS Cognito validation
            authenticated = True

            if authenticated:
                # create and persist Session here
                session_id = create_session()

                # then redirect to an authenticated home page
                authenticated_url = HOME + '?session=' + session_id
                raise web.HTTPFound(authenticated_url)

    # If authentication conditions are not met, then
    # simply redirect back to public landing page
    raise web.HTTPFound(LANDING)


async def kge_login(request: web.Request):  # noqa: E501
    """Process client user login

     # noqa: E501

    :param request:
    :type request: web.Request
    """

    state = str(uuid4())
    _state_cache.append(state)

    login_url = \
        resources['oauth2']['host'] + \
        '/login?response_type=code' + \
        '&state=' + state + \
        '&client_id=' + \
        resources['oauth2']['client_id'] + \
        '&redirect_uri=' + \
        resources['oauth2']['site_uri'] + \
        resources['oauth2']['login_callback']

    raise web.HTTPFound(login_url)


async def kge_logout(request: web.Request):  # noqa: E501
    """Process client user logout

     # noqa: E501

    :param request:
    :type request: web.Request
    :param session_id:
    :type session_id: str
    """
    param = await request.get()
    session_id = param['session']

    # invalidate session here?
    if valid_session(session_id):

        delete_session(session_id)

        # ...then redirect to signal logout at the Oauth2 host
        logout_url = \
            resources['oauth2']['host'] + \
            '/logout?client_id=' + \
            resources['oauth2']['client_id'] + \
            '&logout_uri=' + \
            resources['oauth2']['site_uri']

        raise web.HTTPFound(logout_url)
    else:
        # redirect to unauthenticated landing page for login
        raise web.HTTPFound(LANDING)
