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

from .kgea_config import resources

from .kgea_file_ops import (
    upload_file,
    create_presigned_url,
    location_available,
    kg_files_in_location,
    add_to_github,
    create_smartapi,
    get_object_location,
    with_timestamp, translator_registration
)

from .kgea_stream import transfer_file_from_url

from .kgea_session import (
    create_session,
    valid_session,
    get_session,
    delete_session
)

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

#############################################################
# Site Controller Handlers
#
# Insert imports and return calls into site_controller.py:
#
# from ..kge_handlers import (
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


@aiohttp_jinja2.template('login.html')
async def kge_landing_page(request: web.Request, session_id=None):  # noqa: E501
    """Display landing page.

     # noqa: E501

    :param request:
    :type request: web.Request
    :param session_id:
    :type session_id: str

    :rtype: str
    """
    # validate the session key
    if valid_session(session_id):
        # then redirect to an authenticated home page
        authenticated_url = HOME + '?session=' + session_id
        raise web.HTTPFound(authenticated_url)
    else:
        # If session is not active, then render login page  (no Jinja parameterization)
        return {}


@aiohttp_jinja2.template('home.html')
async def get_kge_home(request: web.Request, session_id: str = None):  # noqa: E501
    """Get default landing page

     # noqa: E501

    :param request:
    :type request: web.Request
    :param session_id:
    :type session_id: str

    :rtype: web.Response
    """

    # validate the session key
    if valid_session(session_id):
        return {"session":  session_id}
    else:
        # If session is not active, then just
        # redirect back to unauthenticated landing page
        raise web.HTTPFound(LANDING)


# hack: short term dictionary
_state_cache = []


async def kge_client_authentication(request: web.Request, code: str, state: str):  # noqa: E501
    """Process client authentication

     # noqa: E501

    :param request:
    :type request: web.Request
    :param code:
    :type code: str
    :param state:
    :type state: str
    """

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


async def kge_logout(request: web.Request, session_id: str = None):  # noqa: E501
    """Process client user logout

     # noqa: E501

    :param request:
    :type request: web.Request
    :param session_id:
    :type session_id: str
    """

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
# Provider Controller Handler
#
# Insert import and return call into provider_controller.py:
#
# from ..kge_handlers import kge_access
#############################################################

# TODO: get file out from timestamped folders 
async def kge_access(request: web.Request, kg_name: str, session_id: str) -> web.Response:  # noqa: E501
    """Get KGE File Sets

     # noqa: E501

    :param request:
    :type request: web.Request
    :param kg_name: Name label of KGE File Set whose files are being accessed
    :type kg_name: str
    :param session_id:
    :type session_id: str
    
    :rtype: web.Response( Dict[str, Attribute] )
    """

    if not valid_session(session_id):
        # If session is not active, then just
        # redirect back to public landing page
        raise web.HTTPFound(LANDING)

    files_location = get_object_location(kg_name)
    # Listings Approach
    # - Introspect on Bucket
    # - Create URL per Item Listing
    # - Send Back URL with Dictionary
    # OK in case with multiple files (alternative would be, archives?). A bit redundant with just one file.
    # TODO: convert into redirect approach with cross-origin scripting?
    kg_files = kg_files_in_location(
        bucket_name=resources['bucket'],
        object_location=files_location
    )
    pattern = Template('($FILES_LOCATION[0-9]+\/)').substitute(FILES_LOCATION=files_location)
    kg_listing = [content_location for content_location in kg_files if re.match(pattern, content_location)]
    kg_urls = dict(
        map(lambda kg_file: [Path(kg_file).stem, create_presigned_url(resources['bucket'], kg_file)], kg_listing))
    # logger.info('access urls %s, KGs: %s', kg_urls, kg_listing)

    # return Response(kg_urls)
    return web.Response(text=str(kg_urls), status=200)


#############################################################
# Content Controller Handler
#
# Insert import and return call into content_controller.py:
#
# from ..kge_handlers import kge_knowledge_map
#############################################################

# TODO: get file out of root folder
async def kge_knowledge_map(request: web.Request, kg_name: str, session_id: str) -> web.Response:  # noqa: E501
    """Get supported relationships by source and target

     # noqa: E501

    :param request:
    :type request: web.Request
    :param kg_name: Name label of KGE File Set whose knowledge graph content metadata is being reported
    :type kg_name: str
    :param session_id:
    :type session_id: str
    
    :rtype: web.Response( Dict[str, Dict[str, List[str]]] )
    """

    if not valid_session(session_id):
        # If session is not active, then just
        # redirect back to public landing page
        raise web.HTTPFound(LANDING)

    files_location = get_object_location(kg_name)

    # Listings Approach
    # - Introspect on Bucket
    # - Create URL per Item Listing
    # - Send Back URL with Dictionary
    # OK in case with multiple files (alternative would be, archives?). A bit redundant with just one file.
    # TODO: convert into redirect approach with cross-origin scripting?
    kg_files = kg_files_in_location(
        bucket_name=resources['bucket'],
        object_location=files_location
    )
    pattern = Template('$FILES_LOCATION([^\/]+\..+)').substitute(
        FILES_LOCATION=files_location
    )
    kg_listing = [content_location for content_location in kg_files if re.match(pattern, content_location)]
    kg_urls = dict(
        map(lambda kg_file: [Path(kg_file).stem, create_presigned_url(resources['bucket'], kg_file)], kg_listing)
    )

    # logger.info('knowledge_map urls: %s', kg_urls)
    # import requests, json
    # metadata_key = kg_listing[0]
    # url = create_presigned_url(resources['bucket'], metadata_key)
    # metadata = json.loads(requests.get(url).text)

    # return Response(kg_urls)
    return web.Response(text=str(kg_urls), status=200)


#############################################################
# Upload Controller Handlers
#
# Insert imports and return calls into upload_controller.py:
#
# from ..kge_handlers import (
#     get_kge_file_upload_form,
#     get_kge_registration_form,
#     register_kge_file_set,
#     upload_kge_file
# )
#
# Remove all parameters  other than 'request'  from
# 'register_file_set' and 'upload_files' arguments.
# (rather retrieved from request.post inside the respective handlers)
#############################################################

def _kge_metadata(
        session_id: str,
        kg_name: str = None,
        submitter: str = None
) -> Dict:
    session = get_session(session_id)

    if kg_name is not None:
        session['kg_name'] = kg_name
    else:
        session['kg_name'] = ''
    if submitter is not None:
        session['submitter'] = submitter
    else:
        session['submitter'] = ''

    return session


@aiohttp_jinja2.template('register.html')
async def get_kge_registration_form(request: web.Request, session_id: str):  # noqa: E501
    """Get web form for specifying KGE File Set name and submitter

     # noqa: E501

    :param request:
    :type request: web.Request
    :param session_id:
    :type session_id: str

    :rtype: web.Response
    """

    if not valid_session(session_id):
        # If session is not active, then just
        # redirect back to public landing page
        raise web.HTTPFound(LANDING)

    #  TODO: if user is authenticated, why do we need to ask them for a submitter name?

    return {"session": session_id}


@aiohttp_jinja2.template('upload.html')
async def get_kge_file_upload_form(
        request: web.Request,
        session_id: str,
        submitter: str,
        kg_name: str
):  # noqa: E501
    """Get web form for specifying KGE File Set upload

     # noqa: E501

    :param request:
    :type request: web.Request
    :param session_id:
    :type session_id: str
    :param submitter:
    :type submitter: str
    :param kg_name:
    :type kg_name: str
    
    :rtype: web.Response
    """

    if not valid_session(session_id):
        # If session is not active, then just
        # redirect back to public landing page
        raise web.HTTPFound(LANDING)

    # TODO guard against absent kg_name
    # TODO guard against invalid kg_name (check availability in bucket)
    # TODO redirect to register_form with given optional param as the entered kg_name

    # return render_template('upload.html', kg_name=kg_name, submitter=submitter, session=session_id)
    return {
        "kg_name": kg_name,
        "submitter": submitter,
        "session": session_id
    }


async def register_kge_file_set(request: web.Request):  # noqa: E501
    """Register core parameters for the KGE File Set upload

     # noqa: E501

    :param request:
    :type request: web.Request

    """
    # logger.critical("register_kge_file_set(locals: " + str(locals()) + ")")

    data = await request.post()

    session_id = data['session']

    if not valid_session(session_id):
        # If session is not active, then just
        # redirect back to public landing page
        raise web.HTTPFound(LANDING)

    submitter = data['submitter']
    kg_name = data['kg_name']

    session = _kge_metadata(session_id, kg_name, submitter)

    kg_name = session['kg_name']
    submitter = session['submitter']

    if not (kg_name and submitter):
        raise web.HTTPBadRequest(reason="register_kge_file_set(): either kg_name or submitter are empty?")

    register_location = get_object_location(kg_name)

    if True:  # location_available(bucket_name, object_key):
        if True:  # api_specification and url:
            # TODO: repair return
            #  1. Store url and api_specification (if needed) in the session
            #  2. replace with /upload form returned
            #
            raise web.HTTPFound(
                Template('/upload?session=$session&submitter=$submitter&kg_name=$kg_name').
                    substitute(session=session_id, kg_name=kg_name, submitter=submitter)
            )
    #     else:
    #         # TODO: more graceful front end failure signal
    #         raise web.HTTPFound(HOME)
    # else:
    #     # TODO: more graceful front end failure signal
    #     raise web.HTTPBadRequest()


async def upload_kge_file(request: web.Request) -> web.Response:  # noqa: E501

    """KGE File Set upload process

     # noqa: E501

    :param request:
    :type request: web.Request

    :rtype: web.Response
    """

    # saved_args = locals()
    # logger.info("entering upload_kge_file(): locals(" + str(saved_args) + ")")

    data = await request.post()

    session_id = data['session']

    if not valid_session(session_id):
        # If session is not active, then just
        # redirect back to public landing page
        raise web.HTTPFound(LANDING)

    upload_mode = data['upload_mode']
    if upload_mode not in ['metadata', 'content_from_local_file', 'content_from_url']:
        # Invalid upload mode
        raise web.HTTPBadRequest(reason="upload_kge_file(): unknown upload_mode: '" + upload_mode + "'?")

    session = get_session(session_id)
    kg_name = session['kg_name']
    submitter = session['submitter']

    content_location, _ = with_timestamp(get_object_location)(kg_name)

    uploaded_file_object_key = None
    file_type = "Unknown"
    response = dict()

    if upload_mode == 'content_from_url':
        url = upload_mode = data['content_url']
        logger.info("upload_kge_file(): content_url == '" + url + "')")
        uploaded_file_object_key = transfer_file_from_url(
            url,  # file_name derived from the URL
            bucket=resources['bucket'],
            object_location=content_location
        )

        file_type = "content"

    else:  # process direct metadata or content file upload

        # Retrieve the POSTed metadata or content file from connexion
        # See https://github.com/zalando/connexion/issues/535 for resolution
        uploaded_file = data['uploaded_file']

        if upload_mode == 'content_from_local_file':

            # KGE Content File for upload?

            uploaded_file_object_key = upload_file(
                uploaded_file.file,
                file_name=uploaded_file.filename,
                bucket=resources['bucket'],
                object_location=content_location
            )

            file_type = "content"

        elif upload_mode == 'metadata':

            # KGE Metadata File for upload?

            metadata_location = get_object_location(kg_name)

            uploaded_file_object_key = upload_file(
                uploaded_file.file,
                file_name=uploaded_file.filename,
                bucket=resources['bucket'],
                object_location=metadata_location
            )

            file_type = "metadata"

        else:
            raise web.HTTPBadRequest(reason="upload_kge_file(): unknown upload_mode: '" + upload_mode + "'?")

    if uploaded_file_object_key:

        # If we get this far, time to register the KGE dataset in SmartAPI
        translator_registration(submitter, kg_name)

        response = {file_type: dict({})}

        s3_file_url = create_presigned_url(
            bucket=resources['bucket'],
            object_key=uploaded_file_object_key
        )

        response[file_type][uploaded_file_object_key] = s3_file_url

        return web.Response(text=str(response), status=200)

    else:
        raise web.HTTPBadRequest(reason="upload_kge_file(): "+file_type+" upload failed?")
