from pathlib import Path
from uuid import uuid4

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
    withTimestamp
)

import logging

logger = logging.getLogger(__name__)

from .kgea_session import (
    create_session,
    valid_session,
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
HOME = '/home'


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
        return render_template('login.html')


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
                authenticated_url = HOME+'?session='+session_id
                return redirect(authenticated_url, code=302, Response=None)
    
    # If authentication conditions are not met
    # just redirect back to unauthenticated home page
    redirect(HOME, code=302, Response=None)


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
        # redirect to unauthenticated home page, for login
        redirect(HOME, code=302, Response=None)


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
        # redirect to unauthenticated home page
        return redirect(HOME, code=302, Response=None)
    
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
    kg_listing = [ content_location for content_location in kg_files if re.match(pattern, content_location) ]
    kg_urls = dict(map(lambda kg_file: [Path(kg_file).stem, create_presigned_url(resources['bucket'], kg_file)], kg_listing))
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
        # redirect to unauthenticated home page
        return redirect(HOME, code=302, Response=None)

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
    kg_urls = dict(map(lambda kg_file: [Path(kg_file).stem, create_presigned_url(resources['bucket'], kg_file)], kg_listing))
    # logger.info('knowledge_map urls: %s', kg_urls)
    
    return Response(kg_urls)


#############################################################
# Upload Controller Handlers
#
# Insert imports and return calls into upload_controller.py:
#
# from ..kge_handlers import (
#     get_kge_registration_form,
#     get_kge_upload_form,
#     register_kge_file_set,
#     upload_kge_file_set,
# )
#
# rewrite 'register_kge_file_set' arguments 'submitter' and 'kg_name' => 'body'
#############################################################


def get_kge_registration_form(
        session_id: str,
        kg_name: str = None,
        submitter: str = None
) -> Response:  # noqa: E501
    """Get web form for specifying KGE File Set upload

     # noqa: E501
     
    :param session_id:
    :type session_id: str
    :param kg_name:
    :type kg_name: str
    :param submitter:
    :type submitter: str

    :rtype: Response
    """

    if not valid_session(session_id):
        # redirect to unauthenticated home page
        return redirect(HOME, code=302, Response=None)

    kg_name_text = kg_name
    submitter_text = submitter
    if kg_name is None:
        kg_name_text = ''
    if submitter is None:
        submitter_text = ''

    return render_template('register.html', session=session_id)


def get_kge_upload_form(kg_name: str, session_id: str) -> Response:  # noqa: E501
    """Get web form for specifying KGE File Set upload

     # noqa: E501

    :param kg_name:
    :type kg_name: str
    :param session_id:
    :type session_id: str
    
    :rtype: Response
    """

    if not valid_session(session_id):
        # redirect to unauthenticated home page
        return redirect(HOME, code=302, Response=None)

    # TODO guard against absent kg_name
    # TODO guard against invalid kg_name (check availability in bucket)
    # TODO redirect to register_form with given optional param as the entered kg_name
    
    return render_template('upload.html', kg_name=kg_name, submitter='unknown', session=session_id)


def register_kge_file_set(session_id, submitter, kg_name) -> Response:  # noqa: E501
    """Register core parameters for the KGE File Set upload

     # noqa: E501

    :param body:
    :type body: dict

    :rtype: Response
    """
    
    # session_id = body['session']
    # submitter = body['submitter']
    # kg_name = body['kg_name']
    
    print("register_kge_file_set(session_id: "+session_id+")")

    if not valid_session(session_id):
        # redirect to unauthenticated home page
        return redirect(HOME, code=302, Response=None)

    register_location = object_location(kg_name)
    
    api_specification = create_smartapi(submitter, kg_name)
    url = add_to_github(api_specification)
    
    if location_available:
        if api_specification and url:
            # TODO: repair return
            #  1. Store url and api_specification (if needed) in the session
            #  2. replace with /upload form returned
            #
            return redirect(Template('/upload/$KG_NAME/?session={{session}}').substitute(session=session_id, kg_name=kg_name), kg_name=kg_name, submitter=submitter)
        else:
            # TODO: more graceful front end failure signal
            redirect(HOME, code=400, Response=None)
    else:
        # TODO: more graceful front end failure signal
        abort(201)


def upload_kge_file_set(
        kg_name: str,
        session_id: str,
        data_file_content,
        data_file_metadata=None
) -> Response:  # noqa: E501
    """Upload web form details specifying a KGE File Set upload process

     # noqa: E501

    :param kg_name:
    :type kg_name: str
    :param session_id:
    :type session_id: str
    :param data_file_content:
    :type data_file_content: FileStorage
    :param data_file_metadata:
    :type data_file_metadata: FileStorage

    :rtype: Response
    """
    saved_args = locals()
    print("upload_kge_file_set", saved_args)

    if not valid_session(session_id):
        # redirect to unauthenticated home page
        return redirect(HOME, code=302, Response=None)

    contentLocation, _ = withTimestamp(object_location)(kg_name)
    metadataLocation = object_location(kg_name)

    # if api_registered(kg_name) and not location_available(bucket_name, object_location) or override:
    maybeUploadContent = upload_file(data_file_content, file_name=data_file_content.filename, bucket_name=resources['bucket'], object_location=contentLocation)
    maybeUploadMetaData = None or data_file_metadata and upload_file(data_file_metadata, file_name=data_file_metadata.filename, bucket_name=resources['bucket'], object_location=metadataLocation)
    
    if maybeUploadContent or maybeUploadMetaData:
        response = {"content": dict({}), "metadata": dict({})}
        
        content_url = create_presigned_url(bucket=resources['bucket'], object_key=maybeUploadContent)

        if maybeUploadContent in response["content"]:
            abort(400)
        else:
            response["content"][maybeUploadContent] = content_url
        
        if maybeUploadMetaData:
            metadata_url = create_presigned_url(bucket=resources['bucket'], object_key=maybeUploadMetaData)
            if maybeUploadMetaData not in response["metadata"]:
                response["metadata"][maybeUploadMetaData] = metadata_url
            # don't care if not there since optional
        
        return Response(response)
    else:
        abort(400)
