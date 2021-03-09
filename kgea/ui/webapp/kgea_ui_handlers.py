from uuid import uuid4

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

from aiohttp import web
import aiohttp_jinja2

#############################################################
# Application Configuration
#############################################################

from .kgea_ui_config import resources

from .kgea_session import (
    create_session,
    valid_session,
    delete_session
)

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

FAKE_LOGIN=True

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

ARCHIVE_HOST = 'http://localhost:8080'
ARCHIVE_PATH = '/archive/'
ARCHIVE_REGISTRATION_FORM_ACTION = ARCHIVE_HOST+ARCHIVE_PATH+"register"


async def kge_landing_page(request: web.Request) -> web.Response:  # noqa: E501
    """Display landing page.

     # noqa: E501

    :param request:
    :type request: web.Request

    :rtype: str
    """
    session_id = request.query.get('session', default='')

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


async def get_kge_home(request: web.Request) -> web.Response:  # noqa: E501
    """Get default landing page

     # noqa: E501

    :param request:
    :type request: web.Request

    :rtype: web.Response
    """
    session_id = request.query.get('session', default='')

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
    code = request.query['code']
    state = request.query['state']

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

    if FAKE_LOGIN:
        # This fake logging process bypasses AWS Cognito, for development testing purposes
        session_id = create_session()

        # then redirect to an authenticated home page
        authenticated_url = HOME + '?session=' + session_id
        raise web.HTTPFound(authenticated_url)
        
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
    """
    session_id = request.query.get('session', default='')

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


#############################################################
# Upload Controller Handlers
#
# Insert imports and return calls into into ui/__init__.py:
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
    :param session_id:
    :type session_id: str

    :rtype: web.Response
    """
    session_id = request.query.get('session', default='')

    if not valid_session(session_id):
        # If session is not active, then just
        # redirect back to public landing page
        raise web.HTTPFound(LANDING)

    #  TODO: if user is authenticated, why do we need to ask them for a submitter name?
    context = {
        "session": session_id,
        "registration_action": ARCHIVE_REGISTRATION_FORM_ACTION
    }
    response = aiohttp_jinja2.render_template('register.html',
                                              request,
                                              context)
    return response


async def get_kge_file_upload_form(request: web.Request) -> web.Response:  # noqa: E501
    """Get web form for specifying KGE File Set upload

     # noqa: E501

    :param request:
    :type request: web.Request

    :rtype: web.Response
    """
    session_id = request.query.get('session', default='')
    submitter = request.query.get('submitter', default='')
    kg_name = request.query.get('kg_name', default='')

    if not valid_session(session_id):
        # If session is not active, then just
        # redirect back to public landing page
        raise web.HTTPFound(LANDING)

    # TODO guard against absent kg_name
    # TODO guard against invalid kg_name (check availability in bucket)
    # TODO redirect to register_form with given optional param as the entered kg_name

    # return render_template('upload.html', kg_name=kg_name, submitter=submitter, session=session_id)
    context = {
        "kg_name": kg_name,
        "submitter": submitter,
        "session": session_id
    }
    response = aiohttp_jinja2.render_template('upload.html',
                                              request,
                                              context)
    return response
