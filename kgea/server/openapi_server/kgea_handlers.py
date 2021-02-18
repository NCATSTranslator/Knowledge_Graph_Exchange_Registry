from pathlib import Path
from uuid import uuid4

import connexion

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

from flask import abort, render_template, redirect

from string import Template
import re

from werkzeug import Response

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
    object_location,
    with_timestamp
)

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

from .kgea_session import (
    create_session,
    valid_session,
    get_session,
    delete_session
)

#############################################################
# Site Controller Handlers
#
# Insert imports and return calls into site_controller.py:
#
# from ..kge_handlers import (
#     kge_client_authentication,
#     get_kge_home,
#     kge_login,
#     kge_logout
# )
#############################################################

# This is the home page path,
# should match the API path spec
LANDING = '/'
HOME = '/home'


def kge_landing_page(session_id=None):  # noqa: E501
    """Display landing page.

     # noqa: E501

    :param session_id:
    :type session_id: str

    :rtype: str
    """
    # validate the session key
    if valid_session(session_id):
        # then redirect to an authenticated home page
        authenticated_url = HOME + '?session=' + session_id
        return redirect(authenticated_url, code=302, Response=None)
    else:
        # If session is not active, then render login page
        return render_template('login.html')


def get_kge_home(session_id: str = None) -> Response:  # noqa: E501
    """Get default landing page

     # noqa: E501
    :param session_id:
    :type session_id: str

    :rtype: Response
    """

    # validate the session key
    if valid_session(session_id):
        return render_template('home.html', session=session_id)
    else:
        # If session is not active, then just
        # redirect back to unauthenticated landing page
        return redirect(LANDING, code=302, Response=None)


# hack: short term dictionary
_state_cache = []


def kge_client_authentication(code: str, state: str) -> Response:  # noqa: E501
    """Process client authentication

     # noqa: E501

    :param code:
    :type code: str

    :param state:
    :type state: str

    :rtype: Response
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
                return redirect(authenticated_url, code=302, Response=None)

    # If authentication conditions are not met, then
    # simply redirect back to public landing page
    redirect(LANDING, code=302, Response=None)


def kge_login() -> Response:  # noqa: E501
    """Process client user login

     # noqa: E501

    :rtype: Response
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

    return redirect(login_url, code=302, Response=None)


def kge_logout(session_id: str = None) -> Response:  # noqa: E501
    """Process client user logout

     # noqa: E501
     
    :param session_id:
    :type session_id: str
    
    :rtype: Response
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

        return redirect(logout_url, code=302, Response=None)
    else:
        # redirect to unauthenticated landing page for login
        return redirect(LANDING, code=302, Response=None)


#############################################################
# Provider Controller Handler
#
# Insert import and return call into provider_controller.py:
#
# from ..kge_handlers import kge_access
#############################################################

# TODO: get file out from timestamped folders 
def kge_access(kg_name: str, session_id: str) -> Response:  # noqa: E501
    """Get KGE File Sets

     # noqa: E501

    :param kg_name: Name label of KGE File Set whose files are being accessed
    :type kg_name: str
    :param session_id:
    :type session_id: str
    
    :rtype: Response( Dict[str, Attribute] )
    """

    if not valid_session(session_id):
        # If session is not active, then just
        # redirect back to public landing page
        return redirect(LANDING, code=302, Response=None)

    files_location = object_location(kg_name)
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

    return Response(kg_urls)


#############################################################
# Content Controller Handler
#
# Insert import and return call into content_controller.py:
#
# from ..kge_handlers import kge_knowledge_map
#############################################################

# TODO: get file out of root folder
def kge_knowledge_map(kg_name: str, session_id: str) -> Response:  # noqa: E501
    """Get supported relationships by source and target

     # noqa: E501

    :param kg_name: Name label of KGE File Set whose knowledge graph content metadata is being reported
    :type kg_name: str
    :param session_id:
    :type session_id: str
    
    :rtype: Response( Dict[str, Dict[str, List[str]]] )
    """

    if not valid_session(session_id):
        # If session is not active, then just
        # redirect back to public landing page
        return redirect(LANDING, code=302, Response=None)

    files_location = object_location(kg_name)

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
        map(lambda kg_file: [Path(kg_file).stem, create_presigned_url(resources['bucket'], kg_file)], kg_listing))
    # logger.info('knowledge_map urls: %s', kg_urls)
    # import requests, json
    # metadata_key = kg_listing[0]
    # url = create_presigned_url(resources['bucket'], metadata_key)
    # metadata = json.loads(requests.get(url).text)
    return Response(kg_urls)


#############################################################
# Upload Controller Handlers
#
# Insert imports and return calls into upload_controller.py:
#
# from ..kge_handlers import (
#     get_kge_file_upload_form,
#     get_kge_registration_form,
#     register_kge_file_set,
#     upload_kge_file,
# )
#
# rewrite 'register_file_set' and 'upload_files' arguments to a
# single 'body' argument (dissected inside the respective handlers)
#############################################################

def _kge_metadata(
        session_id: str,
        kg_name: str = None,
        submitter: str = None
):
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


def get_kge_registration_form(session_id: str) -> Response:  # noqa: E501
    """Get web form for specifying KGE File Set name and submitter

     # noqa: E501
     
    :param session_id:
    :type session_id: str

    :rtype: Response
    """

    if not valid_session(session_id):
        # If session is not active, then just
        # redirect back to public landing page
        return redirect(LANDING, code=302, Response=None)

    #  TODO: if user is authenticated, why do we need to ask them for a submitter  name?

    return render_template(
        'register.html',
        session=session_id
    )


def get_kge_file_upload_form(
        session_id: str,
        submitter: str,
        kg_name: str
) -> Response:  # noqa: E501
    """Get web form for specifying KGE File Set upload

     # noqa: E501

    :param session_id:
    :type session_id: str
    :param submitter:
    :type submitter: str
    :param kg_name:
    :type kg_name: str
    
    :rtype: Response
    """

    if not valid_session(session_id):
        # If session is not active, then just
        # redirect back to public landing page
        return redirect(LANDING, code=302, Response=None)

    # TODO guard against absent kg_name
    # TODO guard against invalid kg_name (check availability in bucket)
    # TODO redirect to register_form with given optional param as the entered kg_name

    return render_template('upload.html', kg_name=kg_name, submitter=submitter, session=session_id)


def register_kge_file_set(body) -> Response:  # noqa: E501
    """Register core parameters for the KGE File Set upload

     # noqa: E501

    :param body:
    :type body: dict

    :rtype: Response
    """
    # logger.critical("register_kge_file_set(locals: " + str(locals()) + ")")

    session_id = body['session']

    if not valid_session(session_id):
        # If session is not active, then just
        # redirect back to public landing page
        return redirect(LANDING, code=302, Response=None)

    submitter = body['submitter']
    kg_name = body['kg_name']

    session = _kge_metadata(session_id, kg_name, submitter)

    kg_name = session['kg_name']
    submitter = session['submitter']

    register_location = object_location(kg_name)

    if True:  # location_available(bucket_name, object_key):
        if True:  # api_specification and url:
            # TODO: repair return
            #  1. Store url and api_specification (if needed) in the session
            #  2. replace with /upload form returned
            #
            return redirect(
                Template('/upload?session=$session&submitter=$submitter&kg_name=$kg_name').
                    substitute(session=session_id, kg_name=kg_name, submitter=submitter)
            )
    #     else:
    #         # TODO: more graceful front end failure signal
    #         redirect(HOME, code=400, Response=None)
    # else:
    #     # TODO: more graceful front end failure signal
    #     return abort(201)


def upload_kge_file(body) -> Response:  # noqa: E501

    """KGE File Set upload process

     # noqa: E501

    :param body:
    :type body: dict

    :rtype: Response
    """

    saved_args = locals()
    logger.info("entering upload_kge_file(): locals(" + str(saved_args) + ")")

    session_id = body['session']

    if not valid_session(session_id):
        # If session is not active, then just
        # redirect back to public landing page
        return redirect(LANDING, code=302, Response=None)

    upload_mode = body['upload_mode']
    if upload_mode not in ['metadata', 'content_from_local_file', 'content_from_url']:
        # Invalid upload mode
        return abort(400, description="upload_kge_file(): unknown upload_mode: '" + upload_mode + "'?")

    session = get_session(session_id)
    kg_name = session['kg_name']
    submitter = session['submitter']

    if upload_mode == 'content_from_url':

        # TODO: implement file from URL
        url = upload_mode = body['content_url']
        logger.info("upload_kge_file(): content_url == '" + url + "')")
        return abort(503, description="upload_kge_file(): content-from-url is not yet implemented?")

    else:  # process direct metadata or content file upload

        # Retrieve the POSTed metadata or content file from connexion
        # See https://github.com/zalando/connexion/issues/535 for resolution
        uploaded_file = connexion.request.files['uploaded_file']

        content_location, _ = with_timestamp(object_location)(kg_name)
        metadata_location = object_location(kg_name)

        maybe_upload_content = None
        maybe_upload_meta_data = None

        # if api_registered(kg_name) and not location_available(bucket_name, object_location) or override:
        if upload_mode == 'content_from_local_file':

            maybe_upload_content = upload_file(
                uploaded_file,
                file_name=uploaded_file.filename,
                bucket_name=resources['bucket'],
                object_location=content_location
            )

            if maybe_upload_content:

                response = {"content": dict({})}

                content_url = create_presigned_url(
                    bucket=resources['bucket'],
                    object_key=maybe_upload_content
                )

                if maybe_upload_content in response["content"]:
                    return abort(400, description="upload_kge_file(): Duplication in content?")
                else:
                    response["content"][maybe_upload_content] = content_url

                # If we get this far, time to register the dataset in SmartAPI
                api_specification = create_smartapi(submitter, kg_name)
                translator_registry_url = add_to_github(api_specification)

                return Response(response)

            else:
                return abort(400, description="upload_kge_file(): content upload failed?")

        elif upload_mode == 'metadata':

            response = {"metadata": dict({})}

            maybe_upload_meta_data = \
                None or uploaded_file and \
                upload_file(uploaded_file,
                            file_name=uploaded_file.filename,
                            bucket_name=resources['bucket'],
                            object_location=metadata_location
                            )

            if maybe_upload_meta_data:

                metadata_url = create_presigned_url(
                    bucket=resources['bucket'],
                    object_key=maybe_upload_meta_data
                )

                if maybe_upload_meta_data not in response["metadata"]:
                    response["metadata"][maybe_upload_meta_data] = metadata_url
                # don't care if not there since optional

                return Response(response)

            else:
                return abort(400, description="upload_kge_file(): metadata upload failed?")

        else:
            return abort(400, description="upload_kge_file(): unknown upload_mode: '" + upload_mode + "'?")
