from os import getenv
from pathlib import Path
from typing import Dict, List

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

from .kgea_session import (
    redirect,
    with_session,
    report_error,
    report_not_found
)

from .kgea_file_ops import (
    upload_file,
    download_file,
    compress_download,
    create_presigned_url,
    infix_string,
    # location_available,
    kg_files_in_location,
    # add_to_github,
    # generate_translator_registry_entry,
    get_object_location,
    get_kg_versions_available,

    with_version,
    with_subfolder
)

from .kgea_stream import transfer_file_from_url

from kgea.server.web_services.catalog.Catalog import (
    KgeFileType,
    KgeaCatalog
)

import logging

# Master flag for local development runs bypassing authentication and other production processes
DEV_MODE = getenv('DEV_MODE', default=False)

logger = logging.getLogger(__name__)

logger.setLevel(logging.DEBUG)

# Opaquely access the configuration dictionary
_KGEA_APP_CONFIG = get_app_config()

# This is likely invariant almost forever unless new types of
# KGX data files will eventually be added, i.e. 'attributes'(?)
KGX_FILE_CONTENT_TYPES = ['metadata', 'nodes', 'edges', 'archive']

if DEV_MODE:
    # Point to http://localhost:8090 for UI
    UPLOAD_FORM_PATH = "http://localhost:8090/upload"
    LANDING = "http://localhost:8090/"
    HOME = "http://localhost:8090/home"
else:
    # Production NGINX resolves the relative path otherwise?
    UPLOAD_FORM_PATH = "/upload"
    LANDING = '/'
    HOME = '/home'


#############################################################
# Catalog Metadata Controller Handler
#
# Insert import and return call into provider_controller.py:
#
# from ..kge_handlers import (
#     get_kge_file_set_catalog,
#     register_kge_file_set,
#     publish_kge_file_set
# )
#############################################################


async def get_kge_file_set_catalog(request: web.Request) -> web.Response:
    """Returns the catalog of available KGE File Sets

    :param request:
    :type request: web.json_response
    """
    catalog: Dict = dict()

    # Paranoia: can't see the catalog without being logged in a user session
    session = await get_session(request)
    if not session.empty:
        catalog = KgeaCatalog.catalog().get_entries()

    # but don't need to propagate the user session to the output
    response = web.json_response(catalog, status=200)
    return response


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

        # kg_version: release version of knowledge graph
        kg_version = data['kg_version']

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
                await report_error(request, "register_kge_file_set(): unknown licence_name: '" + license_name + "'?")

        # terms_of_service: specifically relating to the project, beyond the licensing
        terms_of_service = data['terms_of_service']

        logger.debug(
            "register_kge_file_set() form parameters:\n\t" +
            "\n\tkg_name: " + kg_name +
            "\n\tkg_description: " + kg_description +
            "\n\tkg_version: " + kg_version +
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
        kg_id = KgeaCatalog.normalize_name(kg_name)

        file_set_location, assigned_version = with_version(func=get_object_location, version=kg_version)(kg_id)

        logger.debug("register_kge_file_set(file_set_location: " + file_set_location + ")")

        if True:  # location_available(bucket_name, object_key):
            if True:  # api_specification and url:
                # TODO: repair return
                #  1. Store url and api_specification (if needed) in the session
                #  2. replace with /upload form returned
                #

                # Here we start to inject local KGE Archive tracking
                # of the file set of a specific knowledge graph submission
                KgeaCatalog.catalog().register_kge_file_set(
                    kg_id,
                    file_set_location=file_set_location,
                    kg_name=kg_name,
                    kg_description=kg_description,
                    kg_version=assigned_version,
                    translator_component=translator_component,
                    translator_team=translator_team,
                    submitter=submitter,
                    submitter_email=submitter_email,
                    license_name=license_name,
                    license_url=license_url,
                    terms_of_service=terms_of_service
                )

                await redirect(request,
                               Template(
                                   UPLOAD_FORM_PATH +
                                   '?kg_id=$kg_id&kg_name=$kg_name&kg_version=$kg_version&submitter=$submitter'
                               ).substitute(kg_id=kg_id, kg_name=kg_name, kg_version=kg_version, submitter=submitter),
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


async def publish_kge_file_set(request: web.Request, kg_id):
    """Publish a registered File Set

    :param request:
    :type request: web.Request
    :param kg_id: KGE File Set identifier for the knowledge graph for which data files are being accessed.
    :type kg_id: str

    """

    if not kg_id:
        await report_not_found(request, "publish_kge_file_set(): unknown KGE File Set '" + kg_id + "'?")

    errors: List = await KgeaCatalog.catalog().publish_file_set(kg_id)

    if DEV_MODE and errors:
        raise report_error(
            request,
            "publish_kge_file_set() errors:\n\t" + "\n\t".join([str(e) for e in errors])
        )

    await redirect(request, HOME)


#############################################################
# Upload Controller Handler
#
# Insert imports and return calls into upload_controller.py:
#
# from ..kge_handlers import upload_kge_file
#############################################################


async def get_file_set_location(kg_id: str, kg_version: str = None):
    
    kge_file_set = KgeaCatalog.catalog().get_kge_file_set(kg_id)

    if not kg_version:
        kg_version = kge_file_set.get_version()
        
    file_set_location, assigned_version = with_version(func=get_object_location, version=kg_version)(kg_id)
    
    return file_set_location, assigned_version


async def upload_kge_file(
        request: web.Request,
        kg_id: str,
        kgx_file_content: str,
        upload_mode: str,
        content_name: str,
        content_url: str = None,
        uploaded_file=None
) -> web.Response:
    """KGE File Set upload process

    :param request:
    :type request: web.Request
    :param kg_id:
    :type kg_id: str
    :param kgx_file_content:
    :type kgx_file_content: str
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

        """
        BEGIN Error Handling: checking if parameters passed are sufficient for a well-formed request
        """
        if not kg_id:
            # must not be empty string
            await report_error(request, "upload_kge_file(): empty Knowledge Graph Identifier?")

        if kgx_file_content not in KGX_FILE_CONTENT_TYPES:
            # must not be empty string
            await report_error(
                request,
                "upload_kge_file(): empty or invalid KGX file content type: '" + str(kgx_file_content) + "'?"
            )

        if upload_mode not in ['content_from_local_file', 'content_from_url']:
            # Invalid upload mode
            await report_error(
                request,
                "upload_kge_file(): empty or invalid upload_mode: '" + str(upload_mode) + "'?"
            )

        if not content_name:
            # must not be empty string
            await report_error(request, "upload_kge_file(): empty Content Name?")

        """
        END Error Handling
        """

        """BEGIN Register upload-specific metadata"""

        # The final key for the object is dependent on its type
            # edges -> <file_set_location>/edges/
            # nodes -> <file_set_location>/nodes/
            # archive -> <file_set_location>/archive/

        file_set_location, assigned_version = await get_file_set_location(kg_id)
        if not file_set_location:
            await report_not_found(request, "upload_kge_file(): unknown KGE File Set '" + kg_id + "'?")

        file_type: KgeFileType = KgeFileType.KGX_UNKNOWN

        if kgx_file_content in ['nodes', 'edges']:
            file_set_location = with_subfolder(location=file_set_location, subfolder=kgx_file_content)
            file_type = KgeFileType.KGX_DATA_FILE

        elif kgx_file_content == "metadata":
            # metadata stays in the kg_id 'root' version folder
            file_type = KgeFileType.KGX_METADATA_FILE

        elif kgx_file_content == "archive":
            # TODO this is tricky.. not yet sure how to handle an archive with
            #      respect to properly persisting it in the S3 bucket...
            #      Leave it in the kg_id 'root' version folder for now?
            #      The archive may has metadata too, but the data's the main thing.
            file_type = KgeFileType.KGX_ARCHIVE

        """END Register upload-specific metadata"""


        """BEGIN File Upload Protocol"""

        # keep track of the final key for testing purposes?
        uploaded_file_object_key = None

        # we modify the filename so that they can be validated by KGX natively by tar.gz
        content_name = infix_string(content_name, f"_{kgx_file_content}") if kgx_file_content in ['nodes', 'edges'] else content_name

        if upload_mode == 'content_from_url':

            logger.debug("upload_kge_file(): content_url == '" + content_url + "')")

            uploaded_file_object_key = transfer_file_from_url(
                url=content_url,
                file_name=content_name,
                bucket=_KGEA_APP_CONFIG['bucket'],
                object_location=file_set_location
            )

        elif upload_mode == 'content_from_local_file':

            """
            Although earlier on I experimented with approaches that streamed directly into an archive,
            it failed for what should have been obvious reasons: gzip is non-commutative, so without unpacking
            then zipping up consecutively uploaded files I can't add new gzip files to the package after compression.
            
            So for now we're just streaming into the bucket, only archiving when required - on download.
            """

            uploaded_file_object_key = upload_file(
                data_file=uploaded_file.file,      # The raw file object (e.g. as a byte stream)
                file_name=content_name,            # The new name for the file
                bucket=_KGEA_APP_CONFIG['bucket'],
                object_location=file_set_location
            )

        else:
            await report_error(request, "upload_kge_file(): unknown upload_mode: '" + upload_mode + "'?")

        """END File Upload Protocol"""


        if uploaded_file_object_key:

            try:
                s3_file_url = create_presigned_url(
                    bucket=_KGEA_APP_CONFIG['bucket'],
                    object_key=uploaded_file_object_key
                )

                # This action adds a file to a knowledge graph initiating
                # or continuing a KGE file set registration process.
                # May raise an Exception if something goes wrong.
                KgeaCatalog.catalog().add_to_kge_file_set(
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
                                 str(uploaded_file_object_key) + ") - " + str(exc)
                logger.error(error_msg)
                await report_error(request, error_msg)
        else:
            await report_error(request, "upload_kge_file(): " + str(file_type) + "file upload failed?")

    # else:
    #     # If session is not active, then just a redirect
    #     # directly back to unauthenticated landing page
    #     await redirect(request, LANDING)


#############################################################
# Content Metadata Controller Handler
#
# Insert import and return call into content_controller.py:
#
# from ..kgea_handlers import (
#     get_kge_file_set_contents,
#     kge_meta_knowledge_graph,
#     download_kge_file_set
# )
#############################################################


async def get_kge_file_set_contents(request: web.Request, kg_id: str, kg_version: str) -> web.Response:
    """Get KGE File Set provider metadata.

    :param request:
    :type request: web.Request
    :param kg_id: KGE File Set identifier for the knowledge graph for which data files are being accessed
    :type kg_id: str
    :param kg_version: Specific version of KGE File Set for the knowledge graph for which data file metadata are being accessed
    :type kg_version: str

    """

    if not (kg_id and kg_version):
        await report_not_found(
            request,
            "get_kge_file_set_contents(): KGE File Set identifier or version must not be null?"
        )

    logger.debug("Entering get_kge_file_set_contents(kg_id: " + kg_id + ", kg_version: " + kg_version + ")")

    session = await get_session(request)
    if not session.empty:

        # TODO: need to retrieve metadata by kg_version
        file_set_location, assigned_version = await get_file_set_location(kg_id)
        if not file_set_location:
            await report_not_found(request, "get_kge_file_set_contents(): unknown KGE File Set '" + kg_id + "'?")
        
        # Listings Approach
        # - Introspect on Bucket
        # - Create URL per Item Listing
        # - Send Back URL with Dictionary
        # OK in case with multiple files (alternative would be, archives?). A bit redundant with just one file.
        # TODO: convert into redirect approach with cross-origin scripting?
        kg_files = kg_files_in_location(
            bucket_name=_KGEA_APP_CONFIG['bucket'],
            object_location=file_set_location
        )
        pattern = Template('($FILES_LOCATION[0-9]+\/)').substitute(FILES_LOCATION=file_set_location)
        kg_listing = [content_location for content_location in kg_files if re.match(pattern, content_location)]
        kg_urls = dict(
            map(lambda kg_file: [Path(kg_file).stem, create_presigned_url(_KGEA_APP_CONFIG['bucket'], kg_file)],
                kg_listing))
        # logger.debug('access urls %s, KGs: %s', kg_urls, kg_listing)

        response = web.Response(text=str(kg_urls), status=200)

        return await with_session(request, response)

    else:
        # If session is not active, then just
        # redirect back to unauthenticated landing page
        await redirect(request, LANDING)


async def kge_meta_knowledge_graph(request: web.Request, kg_id: str, kg_version: str) -> web.Response:
    """Get supported relationships by source and target

    :param request:
    :type request: web.Request
    :param kg_id: KGE File Set identifier for the knowledge graph for which graph metadata is being accessed.
    :type kg_id: str
    :param kg_version: Version of KGE File Set for a given knowledge graph.
    :type kg_version: str

    :rtype: web.Response( Dict[str, Dict[str, List[str]]] )
    """
    if not (kg_id and kg_version):
        await report_not_found(
            request,
            "kge_meta_knowledge_graph(): KGE File Set 'kg_id' has value " + str(kg_id) +
            " and 'kg_version' has value " + str(kg_version) + "... both must be non-null."
        )

    logger.debug("Entering kge_meta_knowledge_graph(kg_id: " + kg_id + ", kg_version: " + kg_version + ")")

    session = await get_session(request)
    if not session.empty:

        file_set_location, assigned_version = await get_file_set_location(kg_id, version=kg_version)
        if not file_set_location:
            await report_not_found(request, "kge_meta_knowledge_graph(): unknown KGE File Set '" + kg_id + "'?")

        # Listings Approach
        # - Introspect on Bucket
        # - Create URL per Item Listing
        # - Send Back URL with Dictionary
        # OK in case with multiple files (alternative would be, archives?). A bit redundant with just one file.
        # TODO: convert into redirect approach with cross-origin scripting?
        kg_files = kg_files_in_location(
            bucket_name=_KGEA_APP_CONFIG['bucket'],
            object_location=file_set_location
        )

        #
        # RMB - probably legacy code to be deleted but I keep it visible, just in case
        #
        # pattern = Template('$FILES_LOCATION([^\/]+\..+)').substitute(
        #     FILES_LOCATION=file_set_location
        # )
        # kg_listing = [content_location for content_location in kg_files if re.match(pattern, content_location)]
        # kg_urls = dict(
        #     map(lambda kg_file: [Path(kg_file).stem, create_presigned_url(_KGEA_APP_CONFIG['bucket'], kg_file)],
        #         kg_listing)
        # )

        kg_names = [kg_name.split('/')[1] for kg_name in kg_files]

        logger.debug('knowledge_map names: %s', kg_names)

        response = web.Response(text=str(kg_names), status=200)
        return await with_session(response)
    else:
        # If session is not active, then just a redirect
        # directly back to unauthenticated landing page
        await redirect(request, LANDING)


async def download_kge_file_set(request: web.Request, kg_id, kg_version, archive=False) -> web.Response:
    """Returns specified KGE File Set as a gzip compressed tar archive


    :param request:
    :type request: web.Request
    :param kg_id: KGE File Set identifier for the knowledge graph being accessed.
    :type kg_id: str
    :param kg_version: Version of KGE File Set of the knowledge graph being accessed.
    :type kg_version: str

    """
    if not (kg_id and kg_version):
        await report_not_found(
            request,
            "download_kge_file_set(): KGE File Set 'kg_id' has value " + str(kg_id) +
            " and 'kg_version' has value " + str(kg_version) + "... both must be non-null."
        )

    logger.debug("Entering download_kge_file_set(kg_id: " + kg_id + ", kg_version: " + kg_version + ")")

    session = await get_session(request)
    if not session.empty:
        kg_filepath, _ = with_version(get_object_location, kg_version)(kg_id)
        kg_files_for_version = kg_files_in_location(
            _KGEA_APP_CONFIG['bucket'],
            kg_filepath,
        )

        maybe_archive = [
            kg_path for kg_path in kg_files_for_version
                if ".tar.gz" in kg_path
        ]

        if len(maybe_archive) == 1:
            archive_key = maybe_archive[0]
            download_url = download_file(_KGEA_APP_CONFIG['bucket'], archive_key, open_file=True)
            await redirect(request, download_url)
        else:
            download_url = await compress_download(_KGEA_APP_CONFIG['bucket'], kg_filepath, open_file=True)
            await redirect(request, download_url)
    else:
        # If session is not active, then just a redirect
        # directly back to unauthenticated landing page
        await redirect(request, LANDING)
