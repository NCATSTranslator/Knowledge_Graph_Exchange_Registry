from pathlib import Path
from uuid import uuid4

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

from flask import abort, render_template, redirect

import jinja2
from string import Template
import re

# from werkzeug import FileStorage

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


def get_kge_home(session=None):  # noqa: E501
    """Get default landing page

     # noqa: E501

    :rtype: str
    """
    # validate the session key
    
    if session:
        return render_template('home.html', session=session)
    else:
        return render_template('login.html')


def kge_client_authentication(code, state):  # noqa: E501
    """Process client authentication

     # noqa: E501

    :param code:
    :type code: str

    :param state:
    :type state: str

    :rtype: str
    """
    if code:
        # Establish session here if there is a valid access code & state variable?
        # TODO: maybe delete the 'state' from the temporary global dictionary mentioned in /login?
        
        # Fake it for the first iteration
        session_id = uuid4()
        
        # Store the session here
        
        # then redirect to an authenticated home page
        authenticated_url = HOME+'?session='+str(session_id)
        return redirect(authenticated_url, code=302, Response=None)
    
    else:
        # redirect to home page for login
        redirect(HOME, code=302, Response=None)


def kge_login():  # noqa: E501
    """Process client user login

     # noqa: E501

    :rtype: None
    """
    
    # Have to figure out how best to use
    # this anonymous Oauth2 'state' variable
    state = str(uuid4())
    
    # TODO: maybe store 'state' in a temporary global dictionary for awhile?
    
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


def kge_logout(session=None):  # noqa: E501
    """Process client user logout

     # noqa: E501

    :rtype: None
    """
    
    # invalidate session here?
    if session:
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
def kge_access(kg_name, session):  # noqa: E501
    """Get KGE File Sets

     # noqa: E501

    :param kg_name: Name label of KGE File Set whose files are being accessed
    :type kg_name: str

    :rtype: Dict[str, Attribute]
    """
    
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
    # print('access urls', kg_urls, kg_listing)
    return kg_urls


#############################################################
# Content Controller Handler
#
# Insert import and return call into content_controller.py:
#
# from ..kge_handlers import kge_knowledge_map
#############################################################

# TODO: get file out of root folder
def kge_knowledge_map(kg_name, session):  # noqa: E501
    """Get supported relationships by source and target

     # noqa: E501

    :param kg_name: Name label of KGE File Set whose knowledge graph content metadata is being reported
    :type kg_name: str

    :rtype: Dict[str, Dict[str, List[str]]]
    """

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
    kg_listing = [ content_location for content_location in kg_files if re.match(pattern, content_location) ]
    kg_urls = dict(map(lambda kg_file: [Path(kg_file).stem, create_presigned_url(resources['bucket'], kg_file)], kg_listing))
    # print('knowledge_map urls', kg_urls)
    return kg_urls


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
#############################################################


def get_kge_registration_form(session, kg_name: str = None, submitter: str = None):  # noqa: E501
    """Get web form for specifying KGE File Set upload

     # noqa: E501

    :param kg_name:
    :type kg_name: str
    :param submitter:
    :type submitter: str

    :rtype: str
    """
    
    kg_name_text = kg_name
    submitter_text = submitter
    if kg_name is None:
        kg_name_text = ''
    if submitter is None:
        submitter_text = ''

    return render_template('register.html', session=session)


def get_kge_upload_form(kg_name, session):  # noqa: E501
    """Get web form for specifying KGE File Set upload

     # noqa: E501

    :param kg_name:
    :type kg_name: str

    :rtype: str
    """
    # TODO guard against absent kg_name
    # TODO guard against invalid kg_name (check availability in bucket)
    # TODO redirect to register_form with given optional param as the entered kg_name
    
    return render_template('upload.html', kg_name=kg_name, submitter='unknown', session=session)


def register_kge_file_set(session, body):  # noqa: E501
    """Register core parameters for the KGE File Set upload

     # noqa: E501

    :param session:
    :type session: str
    :param body:
    :type body: dict

    :rtype: str
    """
    submitter = body['submitter']
    kg_name = body['kg_name']
    
    register_location = object_location(kg_name)
    
    api_specification = create_smartapi(submitter, kg_name)
    url = add_to_github(api_specification)
    
    if location_available:
        if api_specification and url:
            # TODO: repair return
            #  1. Store url and api_specification (if needed) in the session
            #  2. replace with /upload form returned
            #
            return redirect(Template('/upload?session={{session}}').substitute(session=session), kg_name=kg_name, submitter=submitter)
        else:
            # TODO: more graceful front end failure signal
            redirect(HOME, code=400, Response=None)
    else:
        # TODO: more graceful front end failure signal
        abort(201)

def upload_kge_file_set(
        kg_name,
        session,
        data_file_content,#: FileStorage,
        data_file_metadata = None#: FileStorage
):  # noqa: E501
    """Upload web form details specifying a KGE File Set upload process

     # noqa: E501

    :param kg_name:
    :type kg_name: str
    :param session:
    :type session: str
    :param data_file_content:
    :type data_file_content: FileStorage
    :param data_file_metadata:
    :type data_file_metadata: FileStorage

    :rtype: str
    """
    saved_args = locals()
    print("upload_kge_file_set", saved_args)

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
        
        return response
    else:
        abort(400)
