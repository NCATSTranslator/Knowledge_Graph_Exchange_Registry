from os import getenv
from pathlib import Path

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

from string import Template
import re

from aiohttp import web
from aiohttp_session import get_session, Session

#############################################################
# Application Configuration
#############################################################

from kgea.server.config import get_app_config

from .kgea_session import redirect, with_session, report_error

from .kgea_file_ops import (
    upload_file,
    create_presigned_url,
    # location_available,
    kg_files_in_location,
    # add_to_github,
    # create_smartapi,
    get_object_location,
    with_timestamp, translator_registration
)

from .kgea_stream import transfer_file_from_url

import logging

# Master flag for local development runs bypassing authentication and other production processes
DEV_MODE = getenv('DEV_MODE', default=False)

logger = logging.getLogger(__name__)
if DEV_MODE:
    logger.setLevel(logging.DEBUG)

# Opaquely access the configuration dictionary
kgea_app_config = get_app_config()

# This is the home page path,
# should match the API path spec
LANDING = '/'
HOME = '/home'

if DEV_MODE:
    # Point to http://localhost:8090 for UI
    UPLOAD_FORM_PATH = "http://localhost:8090/upload"
else:
    # Production NGINX resolves the relative path otherwise?
    UPLOAD_FORM_PATH = "/upload"


#############################################################
# Provider Controller Handler
#
# Insert import and return call into provider_controller.py:
#
# from ..kge_handlers import kge_access
#############################################################


# TODO: get file out from timestamped folders 
async def kge_access(request: web.Request, kg_name: str) -> web.Response:
    """Get KGE File Sets

    :param request:
    :type request: web.Request
    :param kg_name: Name label of KGE File Set whose files are being accessed
    :type kg_name: str

    :rtype: web.Response( Dict[str, Attribute] )
    """
    logger.debug("Entering kge_access(kg_name: " + kg_name + ")")
    
    session = await get_session(request)
    if not session.empty:

        files_location = get_object_location(kg_name)
        # Listings Approach
        # - Introspect on Bucket
        # - Create URL per Item Listing
        # - Send Back URL with Dictionary
        # OK in case with multiple files (alternative would be, archives?). A bit redundant with just one file.
        # TODO: convert into redirect approach with cross-origin scripting?
        kg_files = kg_files_in_location(
            bucket_name=kgea_app_config['bucket'],
            object_location=files_location
        )
        pattern = Template('($FILES_LOCATION[0-9]+\/)').substitute(FILES_LOCATION=files_location)
        kg_listing = [content_location for content_location in kg_files if re.match(pattern, content_location)]
        kg_urls = dict(
            map(lambda kg_file: [Path(kg_file).stem, create_presigned_url(kgea_app_config['bucket'], kg_file)], kg_listing))
        # logger.debug('access urls %s, KGs: %s', kg_urls, kg_listing)
        
        response = web.Response(text=str(kg_urls), status=200)
        return await with_session(request, response)
    
    else:
        # If session is not active, then just
        # redirect back to unauthenticated landing page
        await redirect(request, LANDING)


#############################################################
# Content Controller Handler
#
# Insert import and return call into content_controller.py:
#
# from ..kge_handlers import kge_knowledge_map
#############################################################


# TODO: get file out of root folder
async def kge_knowledge_map(request: web.Request, kg_name: str) -> web.Response:
    """Get supported relationships by source and target

    :param request:
    :type request: web.Request
    :param kg_name: Name label of KGE File Set whose knowledge graph content metadata is being reported
    :type kg_name: str

    :rtype: web.Response( Dict[str, Dict[str, List[str]]] )
    """
    logger.debug("Entering kge_knowledge_map(kg_name: " + kg_name + ")")
    
    session = await get_session(request)
    if not session.empty:
        
        files_location = get_object_location(kg_name)
        
        # Listings Approach
        # - Introspect on Bucket
        # - Create URL per Item Listing
        # - Send Back URL with Dictionary
        # OK in case with multiple files (alternative would be, archives?). A bit redundant with just one file.
        # TODO: convert into redirect approach with cross-origin scripting?
        kg_files = kg_files_in_location(
            bucket_name=kgea_app_config['bucket'],
            object_location=files_location
        )
        pattern = Template('$FILES_LOCATION([^\/]+\..+)').substitute(
            FILES_LOCATION=files_location
        )
        kg_listing = [content_location for content_location in kg_files if re.match(pattern, content_location)]
        kg_urls = dict(
            map(lambda kg_file: [Path(kg_file).stem, create_presigned_url(kgea_app_config['bucket'], kg_file)], kg_listing)
        )
        
        # logger.debug('knowledge_map urls: %s', kg_urls)
        # import requests, json
        # metadata_key = kg_listing[0]
        # url = create_presigned_url(kgea_app_config['bucket'], metadata_key)
        # metadata = json.loads(requests.get(url).text)
        
        response = web.Response(text=str(kg_urls), status=200)
        return await with_session(request, response)

    else:
        # If session is not active, then just a redirect
        # directly back to unauthenticated landing page
        await redirect(request, LANDING)


#############################################################
# Upload Controller Handlers
#
# Insert imports and return calls into upload_controller.py:
#
# from ..kge_handlers import (
#     register_kge_file_set,
#     upload_kge_file
# )
#############################################################

def _kge_metadata(
        session: Session,
        kg_name: str = None,
        submitter: str = None
) -> Session:
    if kg_name is not None:
        session['kg_name'] = kg_name
    else:
        session['kg_name'] = ''
    if submitter is not None:
        session['submitter'] = submitter
    else:
        session['submitter'] = ''
    
    return session


async def register_kge_file_set(request: web.Request):  # noqa: E501
    """Register core parameters for the KGE File Set upload

     # noqa: E501

    :param request:
    :type request: web.Request

    """
    logger.debug("Entering register_kge_file_set()")

    session = await get_session(request)
    if not session.empty:
 
        data = await request.post()
        
        submitter = data['submitter']
        kg_name = data['kg_name']
        
        logger.debug("register_kge_file_set(original submitter: " + submitter +
                     "original kg_name: " + kg_name + ")")
        
        session = _kge_metadata(session, kg_name, submitter)
        
        kg_name = session['kg_name']
        submitter = session['submitter']
        
        logger.debug("register_kge_file_set(cached submitter: " + submitter +
                     "cached kg_name: " + kg_name + ")")
        
        if not (kg_name and submitter):
            report_error("register_kge_file_set(): either kg_name or submitter are empty?")
        
        register_location = get_object_location(kg_name)
        
        logger.debug("register_kge_file_set(register_location: " + register_location + ")")
        
        if True:  # location_available(bucket_name, object_key):
            if True:  # api_specification and url:
                # TODO: repair return
                #  1. Store url and api_specification (if needed) in the session
                #  2. replace with /upload form returned
                #
                await redirect(request,
                         Template(UPLOAD_FORM_PATH + '?submitter=$submitter&kg_name=$kg_name').substitute(
                             kg_name=kg_name, submitter=submitter)
                         )
        #     else:
        #         # TODO: more graceful front end failure signal
        #         await redirect(request, HOME)
        # else:
        #     # TODO: more graceful front end failure signal
        #     report_error("Unknown failure")
    else:
        # If session is not active, then just a redirect
        # directly back to unauthenticated landing page
        await redirect(request, LANDING)


async def upload_kge_file(
        request: web.Request,
        kg_name: str,
        submitter: str,
        upload_mode: str,
        content_name: str,
        content_url: str = None,
        uploaded_file=None
) -> web.Response:  # noqa: E501
    """KGE File Set upload process

     # noqa: E501

    :param request:
    :type request: web.Request
    :param kg_name:
    :type kg_name: str
    :param submitter:
    :type submitter: str
    :param upload_mode:
    :type upload_mode: str
    :param content_name:
    :type content_name: str
    :param content_url:
    :type content_url: str
    :param uploaded_file:
    :type uploaded_file: FileField

    :rtype: web.Response
    """
    logger.debug("Entering upload_kge_file()")
    
    session = await get_session(request)
    if not session.empty:
        
        if not kg_name:
            # must not be empty string
            report_error("upload_kge_file(): empty Knowledge Graph Name?")
        
        if not submitter:
            # must not be empty string
            report_error("upload_kge_file(): empty Submitter?")
        
        if not content_name:
            # must not be empty string
            report_error("upload_kge_file(): empty Content Name?")
        
        if upload_mode not in ['metadata', 'content_from_local_file', 'content_from_url']:
            # Invalid upload mode
            report_error("upload_kge_file(): unknown upload_mode: '" + upload_mode + "'?")
        
        content_location, _ = with_timestamp(get_object_location)(kg_name)
        
        uploaded_file_object_key = None
        file_type = "Unknown"
        
        if upload_mode == 'content_from_url':
            
            logger.debug("upload_kge_file(): content_url == '" + content_url + "')")
            
            uploaded_file_object_key = transfer_file_from_url(
                url=content_url,
                file_name=content_name,
                bucket=kgea_app_config['bucket'],
                object_location=content_location
            )
            
            file_type = "content"
        
        else:  # process direct metadata or content file upload
            
            # upload_file is a FileField with a file attribute
            # pointing to the actual data file as a temporary file
            # Initial approach here will be to user the uploaded_file.file
            # TODO: check if uploaded_file.file scales to large files
            
            if upload_mode == 'content_from_local_file':
                
                # KGE Content File for upload?
                
                uploaded_file_object_key = upload_file(
                    # TODO: does uploaded_file need to be a 'MultipartReader' or a 'BodyPartReader' here?
                    data_file=uploaded_file.file,
                    file_name=content_name,
                    bucket=kgea_app_config['bucket'],
                    object_location=content_location
                )
                
                file_type = "content"
            
            elif upload_mode == 'metadata':
                
                # KGE Metadata File for upload?
                
                metadata_location = get_object_location(kg_name)
                
                uploaded_file_object_key = upload_file(
                    # TODO: does uploaded_file need to be a 'MultipartReader' or a 'BodyPartReader' here?
                    data_file=uploaded_file.file,
                    file_name=content_name,
                    bucket=kgea_app_config['bucket'],
                    object_location=metadata_location
                )
                
                file_type = "metadata"
            
            else:
                report_error("upload_kge_file(): unknown upload_mode: '" + upload_mode + "'?")
        
        if uploaded_file_object_key:
            
            # If we get this far, time to register the KGE dataset in SmartAPI
            translator_registration(submitter, kg_name)
            
            s3_metadata = {file_type: dict({})}
            
            s3_file_url = create_presigned_url(
                bucket=kgea_app_config['bucket'],
                object_key=uploaded_file_object_key
            )
            
            s3_metadata[file_type][uploaded_file_object_key] = s3_file_url
            
            response = web.Response(text=str(s3_metadata), status=200)
            return await with_session(request, response)
        
        else:
            report_error("upload_kge_file(): " + file_type + " upload failed?")

    else:
        # If session is not active, then just a redirect
        # directly back to unauthenticated landing page
        await redirect(request, LANDING)
