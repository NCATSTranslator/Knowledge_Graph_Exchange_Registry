import sys
from os import getenv
from pathlib import Path
from typing import Dict, Optional

from .models import (
    KgeFileSetStatus,
    UploadTokenObject,
    UploadProgressToken
)

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

from string import Template

from aiohttp import web
from aiohttp_session import get_session

import threading

#############################################################
# Application Configuration
#############################################################

from kgea.server.config import (
    get_app_config,
    CONTENT_METADATA_FILE,

    LANDING_PAGE,
    HOME_PAGE,

    FILESET_REGISTRATION_FORM,
    DATA_UNAVAILABLE,

    UPLOAD_FORM
)

from .kgea_session import (
    redirect,
    download,
    with_session,
    report_error,
    report_not_found
)

from .kgea_file_ops import (
    upload_file,
    compress_download,
    create_presigned_url,
    kg_files_in_location,
    get_object_location,
    with_version,
    object_key_exists,
    get_default_date_stamp, with_subfolder, infix_string
)

from kgea.server.web_services.catalog.Catalog import (
    KgeArchiveCatalog,
    KgeKnowledgeGraph,
    KgeFileSet, KgeFileType
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

#############################################################
# Catalog Metadata Controller Handler
#
# Insert import and return call into provider_controller.py:
#
# from ..kge_handlers import (
#     get_kge_knowledge_graph_catalog,
#     register_kge_knowledge_graph,
#     register_kge_file_set,
#     publish_kge_file_set
# )
#############################################################

_upload_tracker = {}


async def get_kge_knowledge_graph_catalog(request: web.Request) -> web.Response:
    """Returns the catalog of available KGE File Sets

    :param request:
    :type request: web.json_response
    """
    catalog: Dict = dict()

    # Paranoia: can't see the catalog without being logged in a user session
    session = await get_session(request)
    if not session.empty:
        catalog = KgeArchiveCatalog.catalog().get_kg_entries()

    # but don't need to propagate the user session to the output
    response = web.json_response(catalog, status=200)
    return response


_known_licenses = {
    "Creative-Commons-4.0": 'https://creativecommons.org/licenses/by/4.0/legalcode',
    "MIT": 'https://opensource.org/licenses/MIT',
    "Apache-2.0": 'https://www.apache.org/licenses/LICENSE-2.0.txt'
}


async def register_kge_knowledge_graph(request: web.Request):
    """Register core metadata for a distinct KGE Knowledge Graph

    Register core metadata for a new KGE persisted Knowledge Graph.
    Since this endpoint assumes assumes a web session authenticated user,
    this user is automatically designated as the &#39;owner&#39; of the new KGE graph.

    :param request:
    :type request: web.Request
    """
    logger.debug("Entering register_kge_knowledge_graph()")

    session = await get_session(request)
    if not session.empty:

        # submitter: name & email of submitter of the KGE file set,
        # cached in session from user authentication
        submitter = session['name']
        submitter_email = session['email']

        data = await request.post()

        # kg_name: human readable name of the knowledge graph
        kg_name = data['kg_name']

        if not kg_name:
            await report_error(request, "register_kge_file_set(): knowledge graph name is unspecified?")

        # kg_description: detailed description of knowledge graph (may be multi-lined with '\n')
        kg_description = data['kg_description']

        # translator_component: Translator component associated with the knowledge graph (e.g. KP, ARA or SRI)
        translator_component = data['translator_component']

        # translator_team: specific Translator team (affiliation)
        # contributing the file set, e.g. Clinical Data Provider
        translator_team = data['translator_team']

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
            "register_kge_knowledge_graph() form parameters:\n\t" +
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

        # Use a normalized version of the knowledge
        # graph name as the KGE File Set identifier.
        kg_id = KgeArchiveCatalog.normalize_name(kg_name)

        if True:  # location_available(bucket_name, object_key):
            if True:  # api_specification and url:
                # TODO: repair return
                #  1. Store url and api_specification (if needed) in the session
                #  2. replace with /upload form returned

                # Here we start to start to track a specific
                # knowledge graph submission within KGE Archive
                knowledge_graph = KgeArchiveCatalog.catalog().add_knowledge_graph(
                    kg_id=kg_id,
                    kg_name=kg_name,
                    kg_description=kg_description,
                    translator_component=translator_component,
                    translator_team=translator_team,
                    submitter=submitter,
                    submitter_email=submitter_email,
                    license_name=license_name,
                    license_url=license_url,
                    terms_of_service=terms_of_service,
                )

                # Also publish a new 'provider.yaml' metadata file to the KGE Archive
                knowledge_graph.publish_provider_metadata()

                await redirect(
                    request,
                    Template(
                        FILESET_REGISTRATION_FORM +
                        '?kg_id=$kg_id&kg_name=$kg_name'
                    ).substitute(
                        kg_id=kg_id,
                        kg_name=knowledge_graph.get_name()
                    ),
                    active_session=True
                )

        #     else:
        #         # TODO: more graceful front end failure signal
        #         await redirect(request, HOME_PAGE)
        # else:
        #     # TODO: more graceful front end failure signal
        #     await report_error(request, "Unknown failure")

    else:
        # If session is not active, then just a redirect
        # directly back to unauthenticated landing page
        await redirect(request, LANDING_PAGE)


async def register_kge_file_set(request: web.Request):
    """Register core metadata for a distinctly versioned file set of a KGE Knowledge Graph

    Register core metadata for a newly persisted file set version of a
    KGE persisted Knowledge Graph. Since this endpoint assumes a web session
    authenticated session user, this user is automatically designated
    as the &#39;owner&#39; of the new versioned file set.

    :param request:
    :type request: web.Request
    """
    logger.debug("Entering register_kge_file_set()")

    session = await get_session(request)
    if not session.empty:

        # submitter: name & email of submitter of the KGE file set,
        # cached in session from user authentication
        submitter = session['name']
        submitter_email = session['email']

        data = await request.post()

        # Identifier of the knowledge graph to
        # which the new KGE File Set belongs
        kg_id = data['kg_id']
        if not kg_id:
            await report_not_found(
                request,
                "register_kge_file_set(): knowledge graph identifier parameter is empty?",
                active_session=True
            )

        # SemVer major versioning of the new KGE File Set
        major_version = data['major_version']
        if not major_version:
            await report_not_found(
                request,
                "register_kge_file_set(): file set major version parameter is empty?",
                active_session=True
            )

        # SemVer minor versioning of the new KGE File Set
        minor_version = data['minor_version']
        if not minor_version:
            await report_not_found(
                request,
                "register_kge_file_set(): file set minor version parameter is empty?",
                active_session=True
            )

        # Consolidated version of new KGE File Set
        # TODO: Should the kg_version include more than just the major and minor SemVer versioning?
        kg_version = str(major_version) + "." + str(minor_version)

        # TODO: do we need to check if this kg_version of
        #       file set already exists? If so, then what?

        # Date stamp of the new KGE File Set
        date_stamp = data['date_stamp'] if 'date_stamp' in data else get_default_date_stamp()

        logger.debug(
            "register_kge_file_set() form parameters:\n\t" +
            "\n\tsubmitter: " + submitter +
            "\n\tsubmitter_email: " + submitter_email +
            "\n\tkg_id: " + kg_id +
            "\n\tversion: " + kg_version +
            "\n\tdate_stamp: " + date_stamp
        )

        knowledge_graph: KgeKnowledgeGraph = \
            KgeArchiveCatalog.catalog().get_knowledge_graph(kg_id)

        if not knowledge_graph:
            await report_not_found(
                request,
                "publish_kge_file_set(): knowledge graph '" + kg_id + "' was not found in the catalog?",
                active_session=True
            )
        if True:  # location_available(bucket_name, object_key):
            if True:  # api_specification and url:
                # TODO: repair return
                #  1. Store url and api_specification (if needed) in the session
                #  2. replace with /upload form returned

                # Here we start to start to track a specific
                # knowledge graph submission within KGE Archive
                file_set: KgeFileSet = knowledge_graph.get_file_set(kg_version)

                if file_set:
                    # existing file set for specified version... hmm... what do I do here?
                    if DEV_MODE:
                        await report_error(
                            request,
                            "publish_kge_file_set(): encountered duplicate file set version '" +
                            kg_version + "' for knowledge graph '" + kg_id + "'?",
                            active_session=True
                        )
                else:
                    # expected new instance of KGE File Set to be created and initialized
                    file_set = KgeFileSet(
                        kg_id=kg_id,
                        kg_version=kg_version,
                        submitter=submitter,
                        submitter_email=submitter_email,
                        date_stamp=date_stamp
                    )

                # Add new versioned KGE File Set to the Catalog Knowledge Graph entry
                knowledge_graph.add_file_set(kg_version, file_set)

                await redirect(
                        request,
                        Template(
                           UPLOAD_FORM +
                           '?kg_id=$kg_id&kg_name=$kg_name&kg_version=$kg_version&submitter=$submitter'
                        ).substitute(
                           kg_id=kg_id,
                           kg_name=knowledge_graph.get_name(),
                           kg_version=kg_version,
                           submitter=submitter
                        ),
                        active_session=True
                    )
        #     else:
        #         # TODO: more graceful front end failure signal
        #         await redirect(request, HOME_PAGE)
        # else:
        #     # TODO: more graceful front end failure signal
        #     await report_error(request, "Unknown failure")

    else:
        # If session is not active, then just a redirect
        # directly back to unauthenticated landing page
        await redirect(request, LANDING_PAGE)


async def publish_kge_file_set(request: web.Request, kg_id: str, kg_version: str):
    """Publish a registered File Set

    :param request:
    :type request: web.Request
    :param kg_id: KGE Knowledge Graph Identifier for the knowledge graph from which data files are being accessed.
    :type kg_id: str
    :param kg_version: specific version of KGE File Set being published for the specified Knowledge Graph Identifier
    :type kg_version: str
    """
    logger.debug("Entering publish_kge_file_set()")

    session = await get_session(request)
    if not session.empty:

        if not (kg_id and kg_version):
            await report_not_found(
                request,
                "publish_kge_file_set(): knowledge graph id or file set version are null?"
            )

        knowledge_graph: KgeKnowledgeGraph = KgeArchiveCatalog.catalog().get_knowledge_graph(kg_id)

        file_set: KgeFileSet = knowledge_graph.get_file_set(kg_version)

        if not (file_set and file_set.publish()):
            await report_error(
                request,
                "publish_kge_file_set() errors: file set version '" +
                kg_version + "' for knowledge graph '" + kg_id + "'" +
                "could not be published?"
            )

    await redirect(request, HOME_PAGE)


#############################################################
# Upload Controller Handler
#
# Insert imports and return calls into upload_controller.py:
#
# from ..kgea_handlers import (
#     setup_kge_upload_context,
#     get_kge_upload_status,
#     upload_kge_file
# )
#############################################################


async def setup_kge_upload_context(
        request: web.Request,
        kg_id: str,
        kg_version: str,
        kgx_file_content: str,
        upload_mode: str,
        content_name: str,
        content_url: str = None
):
    logger.debug("Entering upload_kge_file()")

    session = await get_session(request)
    if not session.empty:

        # """
        # BEGIN Error Handling: checking if parameters
        # passed are sufficient for a well-formed request
        # """
        if not kg_id:
            # must not be empty string
            await report_error(request, "setup_kge_upload_context(): empty Knowledge Graph Identifier?")
        
        if kgx_file_content not in KGX_FILE_CONTENT_TYPES:
            # must not be empty string
            await report_error(
                request,
                "setup_kge_upload_context(): empty or invalid KGX file content type: '" + str(kgx_file_content) + "'?"
            )

        if upload_mode not in ['content_from_local_file', 'content_from_url']:
            # Invalid upload mode
            await report_error(
                request,
                "setup_kge_upload_context(): empty or invalid upload_mode: '" + str(upload_mode) + "'?"
            )

        if not content_name:
            # must not be empty string
            await report_error(request, "upload_kge_file(): empty Content Name?")

        # """
        # END Error Handling
        # """

        # The final key for the object is dependent on its type
        # content metadata -> <file_set_location>
        # edges -> <file_set_location>/edges/
        # nodes -> <file_set_location>/nodes/
        # archive -> <file_set_location>/archive/

        file_set_location, assigned_version = with_version(func=get_object_location, version=kg_version)(kg_id)

        file_type: KgeFileType = KgeFileType.KGX_UNKNOWN

        if kgx_file_content in ['nodes', 'edges']:
            file_set_location = with_subfolder(location=file_set_location, subfolder=kgx_file_content)
            file_type = KgeFileType.KGX_DATA_FILE

        elif kgx_file_content == "metadata":
            # metadata stays in the kg_id 'root' version folder
            file_type = KgeFileType.KGX_CONTENT_METADATA_FILE

            # We coerce the content metadata file name
            # into a standard name, during transfer to S3
            content_name = CONTENT_METADATA_FILE

        elif kgx_file_content == "archive":
            # TODO this is tricky.. not yet sure how to handle an archive
            #      with respect to properly persisting it in the S3 bucket...
            #      Leave it in the kg_id 'root' version folder for now?
            #
            # The archive may has metadata too, but the data's the main thing.
            file_type = KgeFileType.KGE_ARCHIVE

        # we modify the filename so that they can be validated by KGX natively by tar.gz
        content_name = infix_string(
            content_name, f"_{kgx_file_content}"
        ) if kgx_file_content in ['nodes', 'edges'] else content_name

        import uuid
        import os

        object_key = Template('$ROOT$FILENAME$EXTENSION').substitute(
            ROOT=file_set_location,
            FILENAME=Path(content_name).stem,
            EXTENSION=os.path.splitext(content_name)[1]
        )

        with threading.Lock():
            token = str(uuid.uuid4())
            if 'upload' not in _upload_tracker:
                # TODO: not quite sure why we wouldn't
                #       rather store this in the 'session' context?
                #       i.e. session[token] = dict() ?
                _upload_tracker['upload'] = {}
                
            if token not in _upload_tracker['upload']:
                _upload_tracker['upload'][token] = {
                    "kg_id": kg_id,
                    "kg_version": kg_version,
                    "file_set_location": file_set_location,
                    "object_key": object_key,
                    "kgx_file_content": kgx_file_content,
                    "file_type": file_type,
                    "upload_mode": upload_mode,
                    "content_name": content_name,
                }
 
            print('session upload token', token, _upload_tracker['upload'])
            
            upload_token = UploadTokenObject(token).to_dict()

            response = web.json_response(upload_token)
            return await with_session(request, response)
    else:
        # If session is not active, then just a redirect
        # directly back to unauthenticated landing page
        await redirect(request, LANDING_PAGE)


async def get_kge_upload_status(request: web.Request, upload_token: str) -> web.Response:
    """Get the progress of uploading for a specific file of a KGE File Set.

    Poll the status of a given upload process.

    :param request:
    :type request: web.Request
    :param upload_token: Object key associated with a given file for uploading
           to the Archive as specified by a preceding /upload GET call.
    :type upload_token: str

    """

    session = await get_session(request)
    if not session.empty:

        """
        NOTE: Sometimes it takes awhile for end_position to be calculated initialize, particularly if the
        file size is > ~1GB (works fine at ~300mb).
        
        In that case, we leave end_position is going to be undefined. The consumer of this endpoint must be willing
        to consistently poll until end_position is given a value.
        """

        progress_token = UploadProgressToken(
            upload_token=upload_token,
            current_position=_upload_tracker['upload'][upload_token]['current_position'] if 'current_position' in _upload_tracker['upload'][upload_token] else 0,
            end_position=_upload_tracker['upload'][upload_token]['end_position'] if 'end_position' in _upload_tracker['upload'][upload_token] else None,
        ).to_dict()
        response = web.json_response(progress_token)
        return await with_session(request, response)

    else:
        # If session is not active, then just a redirect
        # directly back to unauthenticated landing page
        await redirect(request, LANDING_PAGE)

#########################################################################
# NOTE: Keeping this commented legacy code around a bit longer pending
#       a full resolution of the 'content_from_url' transfers which will
#       now not likely run through the upload_kge_file() handler as
#       previously, but perhaps, in a dedicated endpoint/handler, if
#       attempted at all within the web application.
#########################################################################
#
# if upload_mode == 'content_from_url':
#
#     logger.debug("upload_kge_file(): content_url == '" + content_url + "')")
#
#     uploaded_file_object_key = transfer_file_from_url(
#         url=content_url,
#         file_name=content_name,
#         bucket=_KGEA_APP_CONFIG['bucket'],
#         object_location=file_set_location
#     )
#
# elif upload_mode == 'content_from_local_file':
#
#     """
#     Although earlier on I experimented with approaches that streamed directly into an archive,
#     it failed for what should have been obvious reasons: gzip is non-commutative, so without unpacking
#     then zipping up consecutively uploaded files I can't add new gzip files to the package after compression.
#
#     So for now we're just streaming into the bucket, only archiving when required - on download.
#     """
#
#     uploaded_file_object_key = upload_file(
#         data_file=uploaded_file.file,  # The raw file object (e.g. as a byte stream)
#         file_name=content_name,  # The new name for the file
#         bucket=_KGEA_APP_CONFIG['bucket'],
#         object_location=file_set_location
#     )
#
# else:
#     await report_error(request, "upload_kge_file(): unknown upload_mode: '" + upload_mode + "'?")
#
# """END File Upload Protocol"""
#


async def upload_kge_file(
        request: web.Request,
        upload_token=None,
        uploaded_file=None
):
    """Uploading of a specified file from a local computer.

    :param request:
    :type request: web.Request
    :param upload_token: Object key associated with a given file for uploading.
    :type upload_token: str
    :param uploaded_file: File (blob) object to be uploaded.
    :type uploaded_file: str
    :rtype: web.Response
    """
    logger.debug("Entering upload_kge_file()")

    session = await get_session(request)
    if not session.empty:
        
        global _upload_tracker

        # get details of file upload from token
        details = _upload_tracker['upload'][upload_token]

        # TODO: turn into withable
        async def pathless_file_size(data_file):
            """
            pathless_file_size

            Takes an open file-like object, gets its end location (in bytes),
            and returns it as a measure of the file size.

            Traditionally, one would use a systems-call to get the size
            of a file (using the `os` module). But `TemporaryFileWrapper`s
            do not feature a location in the filesystem, and so cannot be
            tested with `os` methods, as they require access to a filepath,
            or a file-like object that supports a path, in order to work.

            This function seeks the end of a file-like object, records
            the location, and then seeks back to the beginning so that
            the file behaves as if it was opened for the first time.
            This way you can get a file's size before reading it.

            (Note how we aren't using a `with` block, which would close
            the file after use. So this function leaves the file open,
            as an implicit non-effect. Closing is problematic for
             TemporaryFileWrappers which wouldn't be operable again)

            :param data_file:
            :return size:
            """
            if not data_file.closed:
                data_file.seek(0, 2)
                size = data_file.tell()
                print(size)
                data_file.seek(0, 0)
                return size
            else:
                return 0

        def update_session(current_bytes):
            _upload_tracker['upload'][upload_token]['current_position'] = current_bytes

        class ProgressPercentage(object):

            def __init__(self, filename, file_size):
                self._filename = filename
                self.size = file_size
                self._seen_so_far = 0
                self._lock = threading.Lock()

            def __call__(self, bytes_amount):
                # To simplify we'll assume this is hooked up
                # to a single filename.
                # with self._lock:
                self._seen_so_far += bytes_amount
                update_session(self._seen_so_far)
                print('progress_raw', _upload_tracker['upload'][upload_token]['current_position'] / _upload_tracker['upload'][upload_token]['end_position'] * 100)
                # print('progress', upload_token, session['upload'][upload_token]['current_position'] / session['upload'][upload_token]['end_position'], percentage)
        
        # new boto client instance for thread safety
        import boto3
        from botocore.client import Config
        import asyncio
        # import concurrent.futures

        num_threads = 16
        cfg = Config(signature_version='s3v4', max_pool_connections=num_threads)

        filesize = await pathless_file_size(uploaded_file.file)
        _upload_tracker['upload'][upload_token]['end_position'] = filesize

        if 'content_name' in _upload_tracker['upload'][upload_token]:
            content_name = _upload_tracker['upload'][upload_token]['content_name']
        else:
            content_name = uploaded_file.filename
        
        def threaded_upload():
            session_ = boto3.Session()
            client = session_.client("s3", config=cfg)
            uploaded_file_object_key = upload_file(
                data_file=uploaded_file.file,  # The raw file object (e.g. as a byte stream)
                file_name=content_name,        # The new name for the file
                bucket=_KGEA_APP_CONFIG['bucket'],
                object_location=details['file_set_location'],
                callback=ProgressPercentage(
                    uploaded_file.filename,
                    _upload_tracker['upload'][upload_token]['end_position']
                ),
                client=client
            )
            # Assuming success, the new file should be
            # added to into the file set in the Catalog.
            if uploaded_file_object_key:
                try:
                    s3_file_url = create_presigned_url(
                        bucket=_KGEA_APP_CONFIG['bucket'],
                        object_key=uploaded_file_object_key
                    )
            
                    # This action adds a file to the given knowledge graph,
                    # identified by the 'kg_id', initiating or continuing a
                    # the assembly process for the 'kg_version' KGE file set.
                    #
                    # May raise an Exception if something goes wrong.
                    KgeArchiveCatalog.catalog().add_to_kge_file_set(
                        kg_id=details["kg_id"],
                        kg_version=details["kg_version"],
                        file_type=details["file_type"],
                        file_name=content_name,
                        object_key=uploaded_file_object_key,
                        s3_file_url=s3_file_url
                    )

                except Exception as exc:
                    error_msg: str = "upload_kge_file(" + \
                        "kg_id: "+details["kg_id"] + ", " \
                        "kg_version: "+details["kg_version"] + ", " \
                        "file_type: "+details["file_type"] + ", " \
                        "object_key: " + str(uploaded_file_object_key) + \
                        ") threw exception: " + str(exc)
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)
            else:
                raise RuntimeError("upload_kge_file(): " + str(details["file_type"]) + "file upload failed?")

        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, threaded_upload)

        response = web.Response(text=str(_upload_tracker['upload'][upload_token]['end_position']), status=200)
        await with_session(request, response)

    else:
        # If session is not active, then just a redirect
        # directly back to unauthenticated landing page
        await redirect(request, LANDING_PAGE)


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
    :param kg_version: Specific version of KGE File Set for the knowledge graph for which metadata are being accessed
    :type kg_version: str

    :return:  KgeFileSetStatus including an annotated list of KgeFile entries
    """
    logger.debug("Entering get_kge_file_set_contents()...")

    session = await get_session(request)
    if not session.empty:

        if not (kg_id and kg_version):
            await report_not_found(
                request,
                "get_kge_file_set_contents(): Knowledge Graph identifier and File Set version is not specified?"
            )

        logger.debug("...of file set version '" + kg_version + "' for knowledge graph '" + kg_id + "'")

        knowledge_graph: KgeKnowledgeGraph = KgeArchiveCatalog.catalog().get_knowledge_graph(kg_id)

        file_set: KgeFileSet = knowledge_graph.get_file_set(kg_version)

        if file_set:
            file_set_status: Optional[KgeFileSetStatus] = file_set.get_status()
            response = web.json_response(file_set_status, status=200)
            return await with_session(request, response)
        else:
            await report_error(
                request,
                "get_kge_file_set_contents() errors: file set version '" +
                kg_version + "' for knowledge graph '" + kg_id + "'" +
                "could not be accessed?"
            )
    else:
        # If session is not active, then just
        # redirect back to unauthenticated landing page
        await redirect(request, LANDING_PAGE)


async def kge_meta_knowledge_graph(request: web.Request, kg_id: str, kg_version: str):
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
        
        knowledge_graph: KgeKnowledgeGraph = KgeArchiveCatalog.catalog().get_knowledge_graph(kg_id)

        file_set_location, assigned_version = with_version(func=get_object_location, version=kg_version)(kg_id)

        content_metadata_file_key = file_set_location + CONTENT_METADATA_FILE
        
        if not object_key_exists(
                bucket_name=_KGEA_APP_CONFIG['bucket'],
                object_key=content_metadata_file_key
        ):
            await redirect(
                request,
                Template(
                    DATA_UNAVAILABLE +
                    '?kg_version=$kg_version&kg_name=$kg_name&data_type=$data_type'
                ).substitute(
                    kg_version=kg_version,
                    kg_name=knowledge_graph.get_name(),
                    data_type='meta knowledge graph'
                ),
                active_session=True
            )

        # Current implementation of this handler triggers a
        # download of the KGX content metadata file, if available
        download_url = create_presigned_url(
            bucket=_KGEA_APP_CONFIG['bucket'],
            object_key=content_metadata_file_key
        )

        print("download_kge_file_set() download_url: '" + download_url + "'", file=sys.stderr)

        await download(request, download_url)

        # Alternate version could directly return the JSON
        # of the Content Metadata as a direct response?

        # response = web.json_response(text=str(file_set_location))
        # return await with_session(request, response)

    else:
        # If session is not active, then just a redirect
        # directly back to unauthenticated landing page
        await redirect(request, LANDING_PAGE)


async def download_kge_file_set(request: web.Request, kg_id, kg_version):
    """Returns specified KGE File Set as a gzip compressed tar archive


    :param request:
    :type request: web.Request
    :param kg_id: KGE File Set identifier for the knowledge graph being accessed.
    :type kg_id: str
    :param kg_version: Version of KGE File Set of the knowledge graph being accessed.
    :type kg_version: str

    :return: None - redirection responses triggered
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

        file_set_object_key, _ = with_version(get_object_location, kg_version)(kg_id)

        kg_files_for_version = kg_files_in_location(
            _KGEA_APP_CONFIG['bucket'],
            file_set_object_key,
        )

        maybe_archive = [
            kg_path for kg_path in kg_files_for_version
            if ".tar.gz" in kg_path
        ]

        if len(maybe_archive) == 1:
            archive_key = maybe_archive[0]
        else:
            # download_url = download_file(_KGEA_APP_CONFIG['bucket'], archive_key, open_file=True)
            archive_key = await compress_download(_KGEA_APP_CONFIG['bucket'], file_set_object_key)

        download_url = create_presigned_url(bucket=_KGEA_APP_CONFIG['bucket'], object_key=archive_key)
        print("download_kge_file_set() download_url: '" + download_url + "'", file=sys.stderr)

        await download(request, download_url)

    else:
        # If session is not active, then just a redirect
        # directly back to unauthenticated landing page
        await redirect(request, LANDING_PAGE)
