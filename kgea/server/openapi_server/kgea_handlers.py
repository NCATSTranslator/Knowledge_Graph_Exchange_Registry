from pathlib import Path
from uuid import uuid4

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

from flask import abort, render_template, redirect

import jinja2


#############################################################
# Application Configuration
#############################################################

from .kgea_config import s3_client, resources
from .kgea_file_ops import (
    upload_file, 
    download_file, 
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
#     get_kge_home
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
    if session:
        return render_template('home.html')
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
        resources.oauth2.host + \
        '/login?response_type=code' + \
        '&state=' + state + \
        '&client_id=' + \
        resources.oauth2.client_id + \
        '&redirect_uri=' + \
        resources.oauth2.site_uri + \
        resources.oauth2.login_callback
    
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
            resources.oauth2.host + \
            '/logout?client_id=' + \
            resources.oauth2.client_id + \
            '&logout_uri=' + \
            resources.oauth2.site_uri
    
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
def kge_access(kg_name):  # noqa: E501
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
    kg_files = kg_files_in_location(bucket_name=resources['bucket'], object_location=object_location)
    kg_listing = dict(map(lambda kg_file: [Path(kg_file).stem, create_presigned_url(resources['bucket'], kg_file)], kg_files))
    return kg_listing


#############################################################
# Content Controller Handler
#
# Insert import and return call into content_controller.py:
#
# from ..kge_handlers import kge_knowledge_map
#############################################################

# TODO: get file out of root folder
def kge_knowledge_map(kg_name):  # noqa: E501
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
    kg_files = kg_files_in_location(bucket_name=resources['bucket'], object_location=object_location)
    kg_listing = dict(
        map(lambda kg_file: [Path(kg_file).stem, create_presigned_url(resources['bucket'], kg_file)], kg_files))
    return kg_listing


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


def get_kge_registration_form(kg_name=None, submitter=None):  # noqa: E501
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
    
    page = """
    <!DOCTYPE html>
    <html>

    <head>
        <title>Register Files for Knowledge Graph</title>
    </head>

    <body>
        <h1>Register Files for Knowledge Graph</h1>

        <form action="/register" method="post" enctype="application/x-www-form-urlencoded">
            KnowledgeGraph Name: <input type="text" name="kg_name" value="{{kg_name}}"><br>
            Submitter: <input type="text" name="submitter" value="{{submitter}}"><br>
            <input type="submit" value="Register">
        </form>

    </body>

    </html>
    """
    return jinja2.Template(page).render(kg_name=kg_name_text, submitter=submitter_text)


def get_kge_upload_form(kg_name):  # noqa: E501
    """Get web form for specifying KGE File Set upload

     # noqa: E501

    :param kg_name:
    :type kg_name: str

    :rtype: str
    """
    # TODO guard against absent kg_name
    # TODO guard against invalid kg_name (check availability in bucket)
    # TODO redirect to register_form with given optional param as the entered kg_name
    
    page = """
    <!DOCTYPE html>
    <html>

    <head>
        <title>Upload New File</title>
    </head>

    <body>
        <h1>Upload Files</h1>

        <form action="/upload/{{kg_name}}" method="post" enctype="multipart/form-data">
            API Files: <input type="file" name="data_file_content"><br>
            API Metadata: <input type="file" name="data_file_metadata"><br>
            <input type="submit" value="Upload">
        </form>

    </body>

    </html>
    """
    return jinja2.Template(page).render(kg_name=kg_name)


def register_kge_file_set(body):  # noqa: E501
    submitter = body['submitter']
    kg_name = body['kg_name']
    
    register_location = object_location(kg_name)
    
    api_specification = create_smartapi(submitter, kg_name)
    url = add_to_github(api_specification)
    
    if location_available:
        if api_specification and url:
            return dict({
                "url": url,
                "api": api_specification
            })
        else:
            abort(400)
    else:
        abort(201)


def upload_kge_file_set(kg_name, data_file_content, data_file_metadata=None):  # noqa: E501
    """Upload web form details specifying a KGE File Set upload process

     # noqa: E501

    :param kg_name:
    :type kg_name: str
    :param data_file_content:
    :type data_file_content: str
    :param data_file_metadata:
    :type data_file_metadata: str

    :rtype: str
    """

    contentLocation, _ = withTimestamp(object_location)(kg_name)
    metadataLocation = object_location(kg_name)

    # if api_registered(kg_name) and not location_available(bucket_name, object_location) or override:
    maybeUploadContent = upload_file(data_file_content, file_name=data_file_content.filename, bucket_name=resources['bucket'], object_location=contentLocation)
    maybeUploadMetaData = None or data_file_metadata and upload_file(data_file_metadata, file_name=data_file_metadata.filename, bucket_name=resources['bucket'], object_location=metadataLocation)
    
    if maybeUploadContent or maybeUploadMetaData:
        response = {"content": dict({}), "metadata": dict({})}
        
        content_name = maybeUploadContent
        content_url = create_presigned_url(bucket=resources['bucket'], object_key=maybeUploadContent)

        if content_name in response["content"]:
            abort(400)
        else:
            response["content"][content_name] = content_url
        
        if maybeUploadMetaData:
            metadata_name = Path(maybeUploadMetaData).stem
            metadata_url = create_presigned_url(bucket=resources['bucket'], object_key=maybeUploadMetaData)
            if metadata_name not in response["metadata"]:
                response["metadata"][metadata_name] = metadata_url
            # don't care if not there since optional
        
        return response
    else:
        abort(400)
