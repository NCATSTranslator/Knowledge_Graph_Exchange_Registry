from os import getenv
from pathlib import Path

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

from string import Template
import re

from aiohttp import web
from aiohttp_session import get_session

#############################################################
# Application Configuration
#############################################################

from kgea.server.config import get_app_config

from .kgea_session import redirect, with_session, report_error

from .kgea_file_ops import (
    upload_file,
    upload_file_multipart,
    create_presigned_url,
    # location_available,
    kg_files_in_location,
    # add_to_github,
    # create_smartapi,
    get_object_location,
    with_timestamp
)

from .kgea_stream import transfer_file_from_url

from ..registry.Registry import (
    KgeFileType,
    KgeaRegistry
)

import logging

# Master flag for local development runs bypassing authentication and other production processes
DEV_MODE = getenv('DEV_MODE', default=False)

logger = logging.getLogger(__name__)

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
# Upload Controller Handlers
#
# Insert imports and return calls into upload_controller.py:
#
# from ..kge_handlers import (
#     register_kge_file_set,
#     upload_kge_file
# )
#############################################################

_known_licenses = {
    "Creative-Commons-4.0": 'https://creativecommons.org/licenses/by/4.0/legalcode',
    "MIT": 'https://opensource.org/licenses/MIT',
    "Apache-2.0": 'https://www.apache.org/licenses/LICENSE-2.0.txt'
}


async def register_kge_file_set(request: web.Request):  # noqa: E501
    """Register core parameters for the KGE File Set upload

     # noqa: E501

    :param request:
    :type request: web.Request - contains register.html form parameters

    """
    logger.debug("Entering register_kge_file_set()")
    
    session = await get_session(request)
    if not session.empty:
        
        data = await request.post()
        
        # KGE File Set Translator SmartAPI parameters set
        # now includes the following string keyword arguments:
        
        # kg_name: human readable name of the knowledge graph
        kg_name = data['kg_name']
        
        # kg_description: detailed description of knowledge graph (may be multi-lined with '\n')
        kg_description = data['kg_description']

        # translator_component: Translator component associated with the knowledge graph (e.g. KP, ARA or SRI)
        translator_component = data['translator_component']

        # translator_team: specific Translator team (affiliation)
        # contributing the file set, e.g. Clinical Data Provider
        translator_team = data['translator_team']

        # submitter: name of submitter of the KGE file set
        submitter = data['submitter']

        # submitter_email: contact email of the submitter
        submitter_email = data['submitter_email']

        # license_name Open Source license name, e.g. MIT, Apache 2.0, etc.
        license_name = data['license_name']

        # license_url: web site link to project license
        license_url = ''
        
        if 'license_url' in data:
            license_url = data['license_url'].strip()
            
        # url may be empty or unavailable - try to take default license?
        if not license_url:
            if license_name in _known_licenses:
                license_url = _known_licenses[license_name]
            elif license_name != "Other":
                await report_error(request, "register_kge_file_set(): unknown licence_name: '"+license_name+"'?")

        # terms_of_service: specifically relating to the project, beyond the licensing
        terms_of_service = data['terms_of_service']
        
        logger.debug(
            "register_kge_file_set() form parameters:\n\t" +
            "\n\tkg_name: " + kg_name +
            "\n\tkg_description: " + kg_description +
            "\n\ttranslator_component: " + translator_component +
            "\n\ttranslator_team: " + translator_team +
            "\n\tsubmitter: " + submitter +
            "\n\tsubmitter_email: " + submitter_email +
            "\n\tlicense_name: " + license_name +
            "\n\tlicense_url: " + license_url +
            "\n\tterms_of_service: " + terms_of_service
        )
        
        if not kg_name or not submitter:
            await report_error(request, "register_kge_file_set(): either kg_name or submitter are empty?")

        # Use a normalized version of the knowledge
        # graph name as the KGE File Set identifier.
        kg_id = KgeaRegistry.normalize_name(kg_name)

        file_set_location = get_object_location(kg_id)
        
        logger.debug("register_kge_file_set(file_set_location: " + file_set_location + ")")
        
        if True:  # location_available(bucket_name, object_key):
            if True:  # api_specification and url:
                # TODO: repair return
                #  1. Store url and api_specification (if needed) in the session
                #  2. replace with /upload form returned
                #
                
                # Here we start to inject local KGE Archive tracking
                # of the file set of a specific knowledge graph submission
                KgeaRegistry.registry().add_kge_file_set(
                    kg_id,
                    file_set_location=file_set_location,
                    kg_name=kg_name,
                    kg_description=kg_description,
                    translator_component=translator_component,
                    translator_team=translator_team,
                    submitter=submitter,
                    submitter_email=submitter_email,
                    license_name=license_name,
                    license_url=license_url,
                    terms_of_service=terms_of_service
                )
                
                await redirect(request,
                               Template(UPLOAD_FORM_PATH + '?submitter=$submitter&kg_name=$kg_name').substitute(
                                   kg_name=kg_name, submitter=submitter),
                               active_session=True
                               )
        #     else:
        #         # TODO: more graceful front end failure signal
        #         await redirect(request, HOME)
        # else:
        #     # TODO: more graceful front end failure signal
        #     await report_error(request, "Unknown failure")
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
) -> web.Response:
    """KGE File Set upload process

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
            await report_error(request, "upload_kge_file(): empty Knowledge Graph Name?")
        
        if not submitter:
            # must not be empty string
            await report_error(request, "upload_kge_file(): empty Submitter?")
        
        if not content_name:
            # must not be empty string
            await report_error(request, "upload_kge_file(): empty Content Name?")
        
        if upload_mode not in ['metadata', 'content_from_local_file', 'content_from_url']:
            # Invalid upload mode
            await report_error(request, "upload_kge_file(): unknown upload_mode: '" + upload_mode + "'?")
        
        # Use a normalized version of the knowledge
        # graph name as the KGE File Set identifier.
        kg_id = KgeaRegistry.normalize_name(kg_name)
        
        content_location, _ = with_timestamp(get_object_location)(kg_id)
        
        uploaded_file_object_key = None
        file_type: KgeFileType = KgeFileType.KGX_UNKNOWN
        
        if upload_mode == 'content_from_url':
            
            logger.debug("upload_kge_file(): content_url == '" + content_url + "')")
            
            uploaded_file_object_key = transfer_file_from_url(
                url=content_url,
                file_name=content_name,
                bucket=kgea_app_config['bucket'],
                object_location=content_location
            )
            
            file_type = KgeFileType.KGX_DATA_FILE
        
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
                
                file_type = KgeFileType.KGX_DATA_FILE
            
            elif upload_mode == 'metadata':

                # KGE Metadata File for upload?
                
                metadata_location = get_object_location(kg_id)
                
                uploaded_file_object_key = upload_file(
                    # TODO: does uploaded_file need to be a 'MultipartReader' or a 'BodyPartReader' here?
                    data_file=uploaded_file.file,
                    file_name=content_name,
                    bucket=kgea_app_config['bucket'],
                    object_location=metadata_location
                )
                
                file_type = KgeFileType.KGX_METADATA_FILE
            
            else:
                await report_error(request, "upload_kge_file(): unknown upload_mode: '" + upload_mode + "'?")
        
        if uploaded_file_object_key:

            try:
                s3_file_url = create_presigned_url(
                    bucket=kgea_app_config['bucket'],
                    object_key=uploaded_file_object_key
                )

                # This action adds a file to a knowledge graph initiating
                # or continuing a KGE file set registration process.
                # May raise an Exception if something goes wrong.
                KgeaRegistry.registry().add_to_kge_file_set(
                    kg_id=kg_id,
                    file_type=file_type,
                    file_name=content_name,
                    object_key=uploaded_file_object_key,
                    s3_file_url=s3_file_url
                )

                response = web.Response(text=str(kg_id), status=200)

                return await with_session(request, response)

            except Exception as exc:
                error_msg: str = "upload_kge_file(object_key: " + \
                                 str(uploaded_file_object_key)+") - "+str(exc)
                logger.error(error_msg)
                await report_error(request, error_msg)
        else:
            await report_error(request, "upload_kge_file(): " + str(file_type) + "file upload failed?")
    
    else:
        # If session is not active, then just a redirect
        # directly back to unauthenticated landing page
        await redirect(request, LANDING)


#############################################################
# Content Metadata Controller Handler
#
# Insert import and return call into content_controller.py:
#
# from ..kge_handlers import kge_meta_knowledge_graph
#############################################################


# TODO: get file out of root folder
async def kge_meta_knowledge_graph(request: web.Request, kg_id: str) -> web.Response:
    """Get supported relationships by source and target

    :param request:
    :type request: web.Request
    :param kg_id: Name label of KGE File Set whose knowledge graph content metadata is being reported
    :type kg_id: str

    :rtype: web.Response( Dict[str, Dict[str, List[str]]] )
    """
    logger.debug("Entering kge_meta_knowledge_graph(kg_id: " + kg_id + ")")

    session = await get_session(request)
    if not session.empty:

        files_location = get_object_location(kg_id)

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
            map(lambda kg_file: [Path(kg_file).stem, create_presigned_url(kgea_app_config['bucket'], kg_file)],
                kg_listing)
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
# Provider Metadata Controller Handler
#
# Insert import and return call into provider_controller.py:
#
# from ..kge_handlers import kge_access
#############################################################
# TODO: get file out from timestamped folders
async def kge_access(request: web.Request, kg_id: str) -> web.Response:
    """Get KGE File Sets

    :param request:
    :type request: web.Request
    :param kg_id: Name label of KGE File Set whose files are being accessed
    :type kg_id: str

    :rtype: web.Response( Dict[str, Attribute] )
    """
    logger.debug("Entering kge_access(kg_id: " + kg_id + ")")

    session = await get_session(request)
    if not session.empty:

        files_location = get_object_location(kg_id)
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
            map(lambda kg_file: [Path(kg_file).stem, create_presigned_url(kgea_app_config['bucket'], kg_file)],
                kg_listing))
        # logger.debug('access urls %s, KGs: %s', kg_urls, kg_listing)

        response = web.Response(text=str(kg_urls), status=200)
        return await with_session(request, response)

    else:
        # If session is not active, then just
        # redirect back to unauthenticated landing page
        await redirect(request, LANDING)
