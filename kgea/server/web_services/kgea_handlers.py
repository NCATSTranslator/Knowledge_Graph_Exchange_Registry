"""
Knowledge Graph Exchange Archive backend web service handlers.
"""
import sys
from os import getenv, path
from pathlib import Path
from typing import Dict, Tuple, Any
import logging

import uuid
import time

from .models import (
    KgeMetadata,
    UploadTokenObject,
    UploadProgressToken, KgeFileSetStatusCode
)
from .models.kge_upload_progress_status_code import KgeUploadProgressStatusCode
from ...aws.assume_role import AssumeRole

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

from aiohttp import web
from aiohttp_session import get_session

import threading

from botocore.client import Config

import asyncio

#############################################################
# Application Configuration
#############################################################

from kgea.config import (
    get_app_config,
    CONTENT_METADATA_FILE,

    LANDING_PAGE,

    FILESET_REGISTRATION_FORM,
    DATA_UNAVAILABLE,

    UPLOAD_FORM,
    SUBMISSION_CONFIRMATION
)

from .kgea_session import (
    redirect,
    download,
    with_session,
    report_bad_request,
    report_not_found
)

from .kgea_file_ops import (
    create_presigned_url,
    kg_files_in_location,
    get_object_location,
    with_version,
    object_key_exists,
    get_default_date_stamp,
    with_subfolder,
    infix_string,
    s3_client,
    get_object_key,
    get_pathless_file_size,
    get_url_file_size,
    upload_file,
    upload_from_link
)

from kgea.server.web_services.catalog import (
    KgeArchiveCatalog,
    KgeKnowledgeGraph,
    KgeFileSet, KgeFileType
)

logger = logging.getLogger(__name__)

#############################################################
# Configuration
#############################################################

# Master flag for local development runs bypassing authentication and other production processes
DEV_MODE = getenv('DEV_MODE', default=False)

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

_upload_tracker = {'upload': {}}


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
    print("Entering register_kge_knowledge_graph()")
    logger.debug("Entering register_kge_knowledge_graph()")

    session = await get_session(request)
    if not session.empty:

        # submitter: name & email of submitter of the KGE file set,
        # cached in session from user authentication
        submitter_name = session['name']
        submitter_email = session['email']

        data = await request.post()

        # kg_name: human readable name of the knowledge graph
        kg_name = data['kg_name']

        if not kg_name:
            await report_bad_request(request, "register_kge_knowledge_graph(): knowledge graph name is unspecified?")

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
                await report_bad_request(
                    request,
                    "register_kge_knowledge_graph(): unknown licence_name: '" + license_name + "'?"
                )

        # terms_of_service: specifically relating to the project, beyond the licensing
        terms_of_service = data['terms_of_service']

        logger.debug(
            "register_kge_knowledge_graph() form parameters:\n\t" +
            "\n\tkg_name: " + kg_name +
            "\n\tkg_description: " + kg_description +
            "\n\ttranslator_component: " + translator_component +
            "\n\ttranslator_team: " + translator_team +
            "\n\tsubmitter_name: " + submitter_name +
            "\n\tsubmitter_email: " + submitter_email +
            "\n\tlicense_name: " + license_name +
            "\n\tlicense_url: " + license_url +
            "\n\tterms_of_service: " + terms_of_service
        )

        # Use a normalized version of the knowledge
        # graph name as the KGE File Set identifier.
        kg_id = KgeKnowledgeGraph.normalize_name(kg_name)

        if True:  # TODO location_available(bucket_name, object_key):
            if True:  # TODO api_specification and url:
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
                    submitter_name=submitter_name,
                    submitter_email=submitter_email,
                    license_name=license_name,
                    license_url=license_url,
                    terms_of_service=terms_of_service,
                )

                # Also publish a new 'provider.yaml' metadata file to the KGE Archive
                provider_metadata_key = knowledge_graph.publish_provider_metadata()
                
                if not provider_metadata_key:
                    await report_not_found(
                        request,
                        "register_kge_knowledge_graph(): provider metadata could not be published?",
                        active_session=True
                    )

                await redirect(
                    request,
                    f"{FILESET_REGISTRATION_FORM}?kg_id={kg_id}&kg_name={knowledge_graph.get_name()}",
                    active_session=True
                )

        #     else:
        #         # TODO: more graceful front end failure signal
        #         await redirect(request, HOME_PAGE)
        # else:
        #     # TODO: more graceful front end failure signal
        #     await print_error_trace(request, "Unknown failure")

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
    print("Entering register_kge_file_set()")
    logger.debug("Entering register_kge_file_set()")

    session = await get_session(request)
    if not session.empty:

        # submitter: name & email of submitter of the KGE file set,
        # cached in session from user authentication
        submitter_name = session['name']
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

        #  SemVer major versioning of the Biolink Model release associated with the file set
        biolink_model_release = data['biolink_model_release']
        if not biolink_model_release:
            await report_not_found(
                request,
                "register_kge_file_set(): missing Biolink Model SemVer release?",
                active_session=True
            )

        # SemVer minor versioning of the new KGE File Set
        fileset_major_version = data['fileset_major_version']
        if not fileset_major_version:
            await report_not_found(
                request,
                "register_kge_file_set(): missing file set SemVer major version parameter?",
                active_session=True
            )

        # SemVer minor versioning of the new KGE File Set
        fileset_minor_version = data['fileset_minor_version']
        if not fileset_minor_version:
            await report_not_found(
                request,
                "register_kge_file_set(): missing file set SemVer minor version parameter?",
                active_session=True
            )

        # Consolidated version of new KGE File Set
        # TODO: Should the fileset_version include more than just the major and minor SemVer versioning?
        fileset_version = str(fileset_major_version) + "." + str(fileset_minor_version)

        # TODO: do we need to check if this fileset_version of
        #       file set already exists? If so, then what?

        # Date stamp of the new KGE File Set
        date_stamp = data['date_stamp'] if 'date_stamp' in data else get_default_date_stamp()

        logger.debug(
            "register_kge_file_set() form parameters:\n\t" +
            "\n\tsubmitter_name: " + submitter_name +
            "\n\tsubmitter_email: " + submitter_email +
            "\n\tkg_id: " + kg_id +
            "\n\tbiolink_model_release: " + biolink_model_release +
            "\n\tfileset version: " + fileset_version +
            "\n\tdate_stamp: " + date_stamp
        )

        knowledge_graph: KgeKnowledgeGraph = \
            KgeArchiveCatalog.catalog().get_knowledge_graph(kg_id)

        if not knowledge_graph:
            await report_not_found(
                request,
                f"register_kge_file_set(): knowledge graph '{kg_id}' was not found in the catalog?",
                active_session=True
            )

        if True:  # location_available(bucket_name, object_key):
            if True:  # api_specification and url:
                # TODO: repair return
                #  1. Store url and api_specification (if needed) in the session
                #  2. replace with /upload form returned

                # Here we start to start to track a specific
                # knowledge graph submission within KGE Archive
                file_set: KgeFileSet = knowledge_graph.get_file_set(fileset_version)

                if file_set is not None:
                    # existing file set for specified version... hmm... what do I do here?
                    if DEV_MODE:
                        # TODO: need to fail more gracefully here
                        await report_bad_request(
                            request,
                            "register_kge_file_set(): encountered duplicate file set version '" +
                            fileset_version + "' for knowledge graph '" + kg_id + "'?",
                            active_session=True
                        )
                else:
                    # expected new instance of KGE File Set to be created and initialized
                    file_set = KgeFileSet(
                        kg_id=kg_id,
                        biolink_model_release=biolink_model_release,
                        fileset_version=fileset_version,
                        date_stamp=date_stamp,
                        submitter_name=submitter_name,
                        submitter_email=submitter_email
                    )

                print("knowledge_graph.add_file_set", knowledge_graph, file_set)
                # Add new versioned KGE File Set to the Catalog Knowledge Graph entry
                knowledge_graph.add_file_set(fileset_version, file_set)

                await redirect(
                        request,
                        f"{UPLOAD_FORM}?kg_id={kg_id}&kg_name={knowledge_graph.get_name()}"
                        f"&fileset_version={fileset_version}&submitter_name={submitter_name}",
                        active_session=True
                    )
        #     else:
        #         # TODO: more graceful front end failure signal
        #         await redirect(request, HOME_PAGE)
        # else:
        #     # TODO: more graceful front end failure signal
        #     await print_error_trace(request, "Unknown failure")

    else:
        # If session is not active, then just a redirect
        # directly back to unauthenticated landing page
        await redirect(request, LANDING_PAGE)


async def publish_kge_file_set(request: web.Request, kg_id: str, fileset_version: str):
    """Publish a registered File Set

    :param request:
    :type request: web.Request
    :param kg_id: KGE Knowledge Graph Identifier for the knowledge graph from which data files are being accessed.
    :type kg_id: str
    :param fileset_version: specific version of KGE File Set published for the specified Knowledge Graph Identifier
    :type fileset_version: str
    """
    print("Entering publish_kge_file_set()")
    logger.debug("Entering publish_kge_file_set()")

    session = await get_session(request)
    if not session.empty:

        if not (kg_id and fileset_version):
            await report_not_found(
                request,
                "publish_kge_file_set(): knowledge graph id or file set version are null?"
            )

        knowledge_graph: KgeKnowledgeGraph = KgeArchiveCatalog.catalog().get_knowledge_graph(kg_id)

        if not knowledge_graph:
            await report_not_found(
                request,
                f"publish_kge_file_set(): knowledge graph '{kg_id}' was not found in the catalog?",
                active_session=True
            )
            
        file_set: KgeFileSet = knowledge_graph.get_file_set(fileset_version)

        if not file_set:
            await report_not_found(
                request,
                f"publish_kge_file_set() errors: unknown '{fileset_version}' for knowledge graph '{kg_id}'?"
            )
            
        if file_set.get_file_set_status() == KgeFileSetStatusCode.CREATED:
            # Assume that it still needs to be processed
            logger.debug(f"\tPublishing fileset version '{fileset_version}' of graph '{kg_id}'")
            try:
                await file_set.publish()
            except Exception as exception:
                logger.error(str(exception))
    
        if file_set.get_file_set_status() == KgeFileSetStatusCode.ERROR:
            await report_bad_request(
                request,
                f"publish_kge_file_set() errors: file set version '{fileset_version}' " +
                f"for knowledge graph '{kg_id}' has errors thus could not be published?"
            )

        # Should either be under PROCESSING or VALIDATED at this point.
        await redirect(
            request,
            f"{SUBMISSION_CONFIRMATION}?" +
            f"kg_name={knowledge_graph.get_name()}&" +
            f"fileset_version={fileset_version}&" +
            f"validated={str(file_set.get_file_set_status() == KgeFileSetStatusCode.VALIDATED)}",
            active_session=True
        )

    else:
        # If session is not active, then just a redirect
        # directly back to unauthenticated landing page
        await redirect(request, LANDING_PAGE)


#############################################################
# Upload Controller Handler
#
# Insert imports and return calls into upload_controller.py:
#
# from ..kgea_handlers import (
#     setup_kge_upload_context,
#     kge_transfer_from_url,
#     get_kge_upload_status,
#     upload_kge_file
# )
#############################################################
async def _validate_and_set_up_archive_target(
        request: web.Request,
        kg_id: str,
        fileset_version: str,
        kgx_file_content: str,
        content_name: str
) -> Tuple[Any, str, KgeFileType]:
    """

    :param request:
    :param kg_id:
    :param fileset_version:
    :param kgx_file_content:
    :param content_name:
    :return:
    """
    # """
    # BEGIN Error Handling: checking if parameters
    # passed are sufficient for a well-formed request
    # """
    if not kg_id:
        # must not be empty string
        await report_bad_request(request, "_validate_and_set_up_archive_target(): empty Knowledge Graph Identifier?")
    
    if kgx_file_content not in KGX_FILE_CONTENT_TYPES:
        # must not be empty string
        await report_bad_request(
            request,
            f"_validate_and_set_up_archive_target(): empty or invalid KGX file content type: '{kgx_file_content}'?"
        )
    
    if not content_name:
        # must not be empty string
        await report_bad_request(request, "_validate_and_set_up_archive_target(): empty Content Name?")
    
    # """
    # END Error Handling
    # """
    
    # The final key for the object is dependent on its type
    # content metadata -> <file_set_location>
    # edges -> <file_set_location>/edges/
    # nodes -> <file_set_location>/nodes/
    # archive -> <file_set_location>/archive/
    
    file_set_location, assigned_version = with_version(func=get_object_location, version=fileset_version)(kg_id)
    
    file_type: KgeFileType = KgeFileType.KGX_UNKNOWN
    
    if kgx_file_content in ['nodes', 'edges']:
        file_set_location = with_subfolder(location=file_set_location, subfolder=kgx_file_content)
        file_type = KgeFileType.KGX_DATA_FILE
    
    elif kgx_file_content == "metadata":
        
        # TODO: this file is expected to be JSON; how do we protect here against users
        #       inadvertently or deliberately (maliciously?) uploading a large, non-JSON
        #       file, like a gzip archive of node or edge data? Can we perhaps quietly
        #       intercept it within the upload.html form, by checking the declared
        #       MIME type of the File object? See https://developer.mozilla.org/en-US/docs/Web/API/File
        
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
    if kgx_file_content in ['nodes', 'edges']:
        part = content_name.split(".")
        if not (len(part) > 1 and part[-2].find(kgx_file_content) >= 0):
            content_name = infix_string(
                content_name, f"_{kgx_file_content}"
            )
    
    object_key = f"{file_set_location}{Path(content_name).stem}{path.splitext(content_name)[1]}"
    
    return file_set_location, object_key, file_type


async def _initialize_upload_token(
        request: web.Request,
        kg_id: str,
        fileset_version: str,
        kgx_file_content: str,
        content_name: str
) -> UploadTokenObject:
    """
    Set up Progress Indication Token mechanism
    """
    file_set_location, object_key, file_type = \
        await _validate_and_set_up_archive_target(
            request, kg_id, fileset_version, kgx_file_content, content_name
        )
    
    logger.debug(
        "_initialize_upload_token(): " +
        "file_set_location == '" + file_set_location + "'" +
        "object_key == '" + object_key + "'" +
        "file_type == '" + str(file_type) + "')"
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
                "fileset_version": fileset_version,
                "file_set_location": file_set_location,
                "object_key": object_key,
                "kgx_file_content": kgx_file_content,
                "file_type": file_type,
                "content_name": content_name,
                "active": True  # Upload/transfer cancelled when this value becomes 'False'?
            }
        
        print('session upload token', token, _upload_tracker['upload'][token])
        
        upload_token_object = UploadTokenObject(token)
        
        return upload_token_object


def get_upload_tracker_details(upload_token: str) -> Dict:
    """
    Get upload tracker details.
    
    :param upload_token:
    :return:
    """
    global _upload_tracker
    
    # get details of file upload from token
    details = _upload_tracker['upload'][upload_token]
    
    return details


async def setup_kge_upload_context(
        request: web.Request,
        kg_id: str,
        fileset_version: str,
        kgx_file_content: str,
        content_name: str
):
    """
    Configure file upload context (for a progress monitored multi-part upload.

    :param request:
    :param kg_id:
    :param fileset_version:
    :param kgx_file_content:
    :param content_name:
    :return:
    """
    logger.debug("Entering setup_kge_upload_context()")
    
    session = await get_session(request)
    if not session.empty:
        
        upload_token_object: UploadTokenObject = \
            await _initialize_upload_token(request, kg_id, fileset_version, kgx_file_content, content_name)
        
        response = web.json_response(upload_token_object.to_dict())
        
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

        In that case, we leave end_position to be undefined.
        The consumer of this endpoint must be willing to consistently
        poll until end_position is given a value.
        """
        tracker: Dict = get_upload_tracker_details(upload_token)
        
        progress_token = UploadProgressToken(
            upload_token=upload_token,
            current_position=tracker['current_position'] if 'current_position' in tracker else 0,
            end_position=tracker['end_position'] if 'end_position' in tracker else None,
            status=tracker['status'] if 'status' in tracker else KgeUploadProgressStatusCode.ONGOING
        )
        
        response = web.json_response(progress_token.to_dict())
        
        return await with_session(request, response)
    
    else:
        # If session is not active, then just a redirect
        # directly back to unauthenticated landing page
        await redirect(request, LANDING_PAGE)


class ProgressPercentage(object):
    """
    Class to track percentage completion of an upload.
    """
    def __init__(self, filename, transfer_tracker):
        self._filename = filename
        # transfer_tracker should be a Python dictionary
        # used to monitor file upload/transfer metadata
        self.transfer_tracker = transfer_tracker
        self._seen_so_far = 0
        self.dt_log_min = 10
        self.t0 = time.time()
        self.t_log_prev = self.t0

    def get_file_size(self):
        """
        :return: file size of the file being uploaded.
        """
        return self.transfer_tracker['end_position']
    
    def __call__(self, bytes_amount):
        # Here, we check if the transfer/upload is not cancelled
        if not self.transfer_tracker['active']:
            logger.warning("Transfer/upload was cancelled?")
            # Maybe too harsh but throw some kind of exception here?
            raise RuntimeWarning("Transfer/upload was cancelled?")
        else:
            self._seen_so_far += bytes_amount
            self.transfer_tracker['current_position'] = self._seen_so_far
            t_now = time.time()
            dt = t_now-self.t0+0.001
            mb = self._seen_so_far / (1024*1024)
            mbps = mb / dt
            dt_log = t_now-self.t_log_prev
            if dt_log >= self.dt_log_min:
                logger.info(f"ProgressPercentage mbps={mbps} mb={mb}")
                self.t_log_prev = t_now


_num_s3_threads = 16
_s3_transfer_cfg = Config(signature_version='s3v4', max_pool_connections=_num_s3_threads)


def threaded_file_transfer(filename, tracker, transfer_function, source):
    """

    :param filename:
    :param tracker:
    :param transfer_function:
    :param source:
    """
    
    def threaded_upload():
        """
        Threaded upload process.
        :return:
        """
        
        local_role = AssumeRole()
        client = s3_client(assumed_role=local_role, config=_s3_transfer_cfg)
        
        if 'content_name' in tracker:
            content_name = tracker['content_name']
        else:
            content_name = filename
        
        progress_monitor = ProgressPercentage(
            filename=content_name,
            transfer_tracker=tracker
        )
        
        try:
            object_key = get_object_key(tracker['file_set_location'], content_name)
            transfer_function(
                bucket=_KGEA_APP_CONFIG['aws']['s3']['bucket'],
                object_key=object_key,
                source=source,
                client=client,
                callback=progress_monitor
            )
        except Exception as exc:
            exc_msg: str = "threaded_file_transfer(" + \
                           "kg_id: " + tracker["kg_id"] + ", " + \
                           "fileset_version: " + tracker["fileset_version"] + ", " + \
                           "file_type: " + str(tracker["file_type"]) + ") threw exception: " + str(exc)
            logger.error(exc_msg)
            raise RuntimeError(exc_msg)
        
        # Assuming success, the new file should be
        # added to into the file set in the Catalog.
        try:
            s3_file_url = create_presigned_url(
                bucket=_KGEA_APP_CONFIG['aws']['s3']['bucket'],
                object_key=object_key
            )
            
            # This action adds a file to the given knowledge graph,
            # identified by the 'kg_id', initiating or continuing a
            # the assembly process for the 'fileset_version' KGE file set.
            # May raise an Exception if something goes wrong.
            KgeArchiveCatalog.catalog().add_to_kge_file_set(
                kg_id=tracker["kg_id"],
                fileset_version=tracker["fileset_version"],
                file_type=tracker["file_type"],
                file_name=content_name,
                file_size=progress_monitor.get_file_size(),
                object_key=object_key,
                s3_file_url=s3_file_url
            )
        
        except Exception as exc:
            exc_msg: str = "threaded_file_transfer(" + \
                           "kg_id: " + tracker["kg_id"] + ", " + \
                           "fileset_version: " + tracker["fileset_version"] + ", " + \
                           "file_type: " + str(tracker["file_type"]) + ", " + \
                           "object_key: " + str(object_key) + ") threw exception: " + str(exc)
            logger.error(exc_msg)
            raise RuntimeError(exc_msg)

    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, threaded_upload)


async def upload_kge_file(
        request: web.Request,
        upload_token,
        uploaded_file
):
    """Uploading of a specified file from a local computer.

    :param request:
    :type request: web.Request
    :param upload_token: Object key associated with a given file for uploading.
    :type upload_token: str
    :param uploaded_file: File (blob) object to be uploaded.
    :type uploaded_file: blob
    :rtype: web.Response
    """
    logger.debug("Entering upload_kge_file()")
    
    session = await get_session(request)
    if not session.empty:
        
        tracker: Dict = get_upload_tracker_details(upload_token)
        
        tracker['end_position'] = get_pathless_file_size(uploaded_file.file)

        tracker['status'] = KgeUploadProgressStatusCode.ONGOING

        # TODO: create a wrapper of the upload_file function to modify status codes on success or failure
        def _upload_file(*args, **kwargs):
            try:
                upload_file(*args, **kwargs)
                tracker['status'] = KgeUploadProgressStatusCode.COMPLETED
            except Exception as e:
                tracker['status'] = KgeUploadProgressStatusCode.ERROR
                raise e

        threaded_file_transfer(
            filename=uploaded_file.filename,
            tracker=tracker,
            transfer_function=_upload_file,
            source=uploaded_file.file  # The raw file object (e.g. as a byte stream)
        )
        
        response = web.Response(text=str(tracker['end_position']), status=200)
        
        await with_session(request, response)
    
    else:
        # If session is not active, then just a redirect
        # directly back to unauthenticated landing page
        await redirect(request, LANDING_PAGE)


async def kge_transfer_from_url(
        request: web.Request,
        kg_id: str,
        fileset_version: str,
        kgx_file_content: str,
        content_url: str,
        content_name: str
):
    """
    Trigger direct URL file transfer of a specific file of a KGE File Set.

    :param request:
    :param kg_id:
    :param fileset_version:
    :param kgx_file_content:
    :param content_url:
    :param content_name:
    :return:
    """
    logger.debug("Entering kge_transfer_from_url()")



    session = await get_session(request)
    if not session.empty:
        
        if not content_url:
            # must not be empty string
            await report_bad_request(request, "kge_transfer_from_url(): empty Content URL?")
        
        logger.debug("kge_transfer_from_url(): content_url == '" + content_url + "')")
        
        upload_token_object: UploadTokenObject = \
            await _initialize_upload_token(request, kg_id, fileset_version, kgx_file_content, content_name)
        
        tracker: Dict = get_upload_tracker_details(upload_token_object.upload_token)
        
        tracker['end_position'] = get_url_file_size(content_url)
        
        if tracker['end_position'] <= 0:
            await report_bad_request(request, f"kge_transfer_from_url({content_url}): unknown URL resource size?")
            
        tracker['status'] = KgeUploadProgressStatusCode.ONGOING

        # create a wrapper of the upload_from_link function to modify status codes
        def _upload_from_link(*args, **kwargs):
            try:
                upload_from_link(*args, **kwargs)
                tracker['status'] = KgeUploadProgressStatusCode.COMPLETED
            except Exception as e:
                tracker['status'] = KgeUploadProgressStatusCode.ERROR
                raise e

        threaded_file_transfer(
            filename=content_name,
            tracker=tracker,
            transfer_function=_upload_from_link,
            source=content_url
        )
        
        response = web.json_response(upload_token_object.to_dict())
        
        return await with_session(request, response)
    
    else:
        # If session is not active, then just a redirect
        # directly back to unauthenticated landing page
        await redirect(request, LANDING_PAGE)


def abort_upload(upload_token: str):
    """
    Signal cancellation of a given upload or transfer.

    :param upload_token:
    :return:
    """
    global _upload_tracker

    _upload_tracker['upload'][upload_token]['active'] = False
    

async def cancel_kge_upload(request: web.Request, upload_token):
    """Cancel uploading of a specific file of a KGE File Set.

    Cancel a given upload process identified by upload token.

    :param request:
    :type request: web.Request
    :param upload_token: Upload token associated with a given file whose uploading is to be cancelled.
    :type upload_token: str

    """
    logger.debug("Entering cancel_kge_upload()")

    session = await get_session(request)
    if not session.empty:
        
        if not upload_token:
            # must not be empty string
            await report_bad_request(request, "cancel_kge_upload(): can't cancel an empty upload_token?")
        
        # TODO: trigger deletion of the current upload/transfer operation here(?)
        logger.info(f"cancel_kge_upload() called for upload token '{upload_token}'")
        
        abort_upload(upload_token)
        
        # Standard success response for upload file
        # operation deletion, without any returned content
        response = web.Response(status=204)
        return await with_session(request, response)

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
#     get_kge_file_set_metadata,
#     kge_meta_knowledge_graph,
#     download_kge_file_set_archive
# )
#############################################################
def _sanitize_metadata(metadata: Dict):
    """
    Cleans up the metadata for JSON serialization. For now,
    just coercing the fileset.date_stamp into an ISOFormat string
    
    :param metadata: Dictionary from KgeMetadata
    :return: nothing... the metadata is mutable, thus changed in situ
    """
    if metadata:
        if 'fileset' in metadata and 'date_stamp' in metadata['fileset']:
            # date_stamp assumed in KgeFileSetMetadata to be a
            # Python datetime.date object, so serialize it to ISOFormat
            metadata['fileset']['date_stamp'] = metadata['fileset']['date_stamp'].isoformat()


async def get_kge_file_set_metadata(request: web.Request, kg_id: str, fileset_version: str) -> web.Response:
    """Get KGE File Set provider metadata.

    :param request:
    :type request: web.Request
    :param kg_id: KGE File Set identifier for the knowledge graph for which data files are being accessed
    :type kg_id: str
    :param fileset_version: Specific version of KGE File Set for the knowledge graph for which metadata are accessed
    :type fileset_version: str

    :return:  KgeMetadata including provider and content metadata with an annotated list of KgeFile entries
    """
    logger.debug("Entering get_kge_file_set_metadata()...")

    session = await get_session(request)
    if not session.empty:

        if not (kg_id and fileset_version):
            await report_not_found(
                request,
                "get_kge_file_set_metadata(): Knowledge Graph identifier and File Set version is not specified?"
            )

        logger.debug("...of file set version '" + fileset_version + "' for knowledge graph '" + kg_id + "'")

        knowledge_graph: KgeKnowledgeGraph = KgeArchiveCatalog.catalog().get_knowledge_graph(kg_id)

        if not knowledge_graph:
            await report_not_found(
                request,
                f"get_kge_file_set_metadata(): knowledge graph '{kg_id}' was not found in the catalog?",
                active_session=True
            )
        
        try:
            file_set_metadata: KgeMetadata = knowledge_graph.get_metadata(fileset_version)

            if not file_set_metadata:
                await report_not_found(
                    request,
                    f"file_set_metadata(): file set metadata for knowledge graph '{kg_id}' is not available?",
                    active_session=True
                )
            
            file_set_status_as_dict = file_set_metadata.to_dict()

            _sanitize_metadata(file_set_status_as_dict)

            response = web.json_response(file_set_status_as_dict, status=200)  # , dumps=kge_dumps)

            return await with_session(request, response)

        except RuntimeError as rte:
            await report_bad_request(
                request,
                "get_kge_file_set_metadata() errors: file set version '" +
                fileset_version + "' for knowledge graph '" + kg_id + "'" +
                "could not be accessed. Error: "+str(rte)
            )
    else:
        # If session is not active, then just
        # redirect back to unauthenticated landing page
        await redirect(request, LANDING_PAGE)


async def kge_meta_knowledge_graph(request: web.Request, kg_id: str, fileset_version: str, downloading: bool = True):
    """Get supported relationships by source and target

    :param request:
    :type request: web.Request
    :param kg_id: KGE File Set identifier for the knowledge graph for which graph metadata is being accessed.
    :type kg_id: str
    :param fileset_version: Version of KGE File Set for a given knowledge graph.
    :type fileset_version: str
    :param downloading: flag set 'True' if file downloading in progress.
    :type downloading: bool

    :rtype: web.Response( Dict[str, Dict[str, List[str]]] )
    """
    if not (kg_id and fileset_version):
        await report_not_found(
            request,
            "kge_meta_knowledge_graph(): KGE File Set 'kg_id' has value " + str(kg_id) +
            " and 'fileset_version' has value " + str(fileset_version) + "... both must be non-null."
        )

    logger.debug("Entering kge_meta_knowledge_graph(kg_id: " + kg_id + ", fileset_version: " + fileset_version + ")")

    session = await get_session(request)
    if not session.empty:
        
        knowledge_graph: KgeKnowledgeGraph = KgeArchiveCatalog.catalog().get_knowledge_graph(kg_id)

        if not knowledge_graph:
            await report_not_found(
                request,
                f"kge_meta_knowledge_graph(): knowledge graph '{kg_id}' was not found in the catalog?",
                active_session=True
            )
            
        file_set_location, assigned_version = with_version(func=get_object_location, version=fileset_version)(kg_id)

        content_metadata_file_key = file_set_location + CONTENT_METADATA_FILE
        
        if not object_key_exists(
                object_key=content_metadata_file_key,
                bucket_name=_KGEA_APP_CONFIG['aws']['s3']['bucket']
        ):
            if downloading:
                await redirect(
                    request,
                    f"{DATA_UNAVAILABLE}?fileset_version={fileset_version}"
                    f"&kg_name={knowledge_graph.get_name()}&data_type=meta%20knowledge%20graph",
                    active_session=True
                )
            else:
                response = web.Response(text="unavailable")
                return await with_session(request, response)

        # Current implementation of this handler triggers a
        # download of the KGX content metadata file, if available
        download_url = create_presigned_url(
            bucket=_KGEA_APP_CONFIG['aws']['s3']['bucket'],
            object_key=content_metadata_file_key
        )
        print("kge_meta_knowledge_graph() download_url: '" + download_url + "'", file=sys.stderr)
        if downloading:
            await download(request, download_url)
        else:
            response = web.Response(text=download_url)
            return await with_session(request, response)

        # Alternate version could directly return the JSON
        # of the Content Metadata as a direct response?

        # response = web.json_response(text=str(file_set_location))
        # return await with_session(request, response)

    else:
        # If session is not active, then just a redirect
        # directly back to unauthenticated landing page
        await redirect(request, LANDING_PAGE)


async def download_kge_file_set_archive(request: web.Request, kg_id, fileset_version):
    """Returns specified KGE File Set as a gzip compressed tar archive

    :param request:
    :type request: web.Request
    :param kg_id: KGE File Set identifier for the knowledge graph being accessed.
    :type kg_id: str
    :param fileset_version: Version of KGE File Set of the knowledge graph being accessed.
    :type fileset_version: str

    :return: None - redirection responses triggered
    """
    if not (kg_id and fileset_version):
        await report_not_found(
            request,
            "download_kge_file_set_archive(): KGE File Set 'kg_id' has value " + str(kg_id) +
            " and 'fileset_version' has value " + str(fileset_version) + "... both must be non-null."
        )

    logger.debug(f"Entering download_kge_file_set_archive(kg_id: '{kg_id}', fileset_version: '{fileset_version}')")

    session = await get_session(request)
    if not session.empty:

        file_set_object_key, _ = with_version(get_object_location, fileset_version)(kg_id)

        kg_files_for_version = kg_files_in_location(
            _KGEA_APP_CONFIG['aws']['s3']['bucket'],
            file_set_object_key,
        )

        # TODO: I don't think that this code snippet is reliable now,
        #       if the user uploads one or more tar.gz files
        #       which are meant to be partial input data without metadata?
        maybe_archive = [
            kg_path for kg_path in kg_files_for_version
            if ".tar.gz" in kg_path
        ]

        if len(maybe_archive) == 1:
            download_url = create_presigned_url(
                bucket=_KGEA_APP_CONFIG['aws']['s3']['bucket'],
                object_key=maybe_archive[0]
            )
            print("download_kge_file_set_archive() download_url: '" + download_url + "'", file=sys.stderr)

            await download(request, download_url)
        else:
            await report_not_found(
                request,
                f"download_kge_file_set_archive(): archive not (yet) available for {kg_id}.{fileset_version}"
            )

    else:
        # If session is not active, then just a redirect
        # directly back to unauthenticated landing page
        await redirect(request, LANDING_PAGE)


async def download_kge_file_set_archive_sha1hash(request: web.Request, kg_id, fileset_version):
    """Returns SHA1 hash of the current KGE File Set as a small text file.

    :param request:
    :type request: web.Request
    :param kg_id: Identifier of the knowledge graph of the KGE File Set a file set version for which is being accessed.
    :type kg_id: str
    :param fileset_version: Version of file set of the knowledge graph being accessed.
    :type fileset_version: str

    :return: None - redirection responses triggered
    """
    if not (kg_id and fileset_version):
        await report_not_found(
            request,
            "download_kge_file_set_archive_sha1hash(): KGE File Set 'kg_id' has value " + str(kg_id) +
            " and 'fileset_version' has value " + str(fileset_version) + "... both must be non-null."
        )

    logger.debug(
        f"Entering download_kge_file_set_archive_sha1hash(kg_id: '{kg_id}', fileset_version: '{fileset_version}')"
    )

    session = await get_session(request)
    if not session.empty:

        file_set_object_key, fileset_version = with_version(get_object_location, fileset_version)(kg_id)

        kg_files_for_version = kg_files_in_location(
            _KGEA_APP_CONFIG['aws']['s3']['bucket'],
            file_set_object_key,
        )

        maybe_sha1hash = [
            kg_path for kg_path in kg_files_for_version
            if "sha1.txt" in kg_path
        ]

        sha1hash_file_key: str = ''
        if len(maybe_sha1hash) == 1:
            sha1hash_file_key = maybe_sha1hash[0]
        else:
            await report_not_found(
                request,
                f"download_kge_file_set_archive_sha1hash(): SHA1 Hash file for archive of graph {str(kg_id)}" +
                f" file set '{str(fileset_version)}' is unavailable?"
            )

        if sha1hash_file_key:
            download_url = create_presigned_url(
                bucket=_KGEA_APP_CONFIG['aws']['s3']['bucket'],
                object_key=sha1hash_file_key
            )
    
            await download(request, download_url)

    else:
        # If session is not active, then just a redirect
        # directly back to unauthenticated landing page
        await redirect(request, LANDING_PAGE)
