"""
Archiver service API handlers
"""

from aiohttp import web

from kgea.server.archiver.models import KgeFileSetMetadata
from kgea.server.archiver.kge_archiver_util import KgeArchiver

import logging

from kgea.server.catalog import KgeFileSet
from kgea.server.kgea_session import report_bad_request

logger = logging.getLogger(__name__)


async def process_kge_fileset(request: web.Request, body: KgeFileSetMetadata) -> web.Response:
    """Posts a KGE File Set for post-processing after upload.

    Posts a KGE File Set for post-processing after upload.

    :param request: includes the KGE File Set in the POST body, for processing.
    :type request: web.Request
    :param body: Metadata of the KGE File Set to be post-processed.
    :type body: KgeFileSetMetadata

    """
    file_set: KgeFileSet = KgeFileSet.load(metadata=body)

    process_token: str = ''
    try:
        archiver: KgeArchiver = KgeArchiver.get_archiver()
        process_token = await archiver.process(file_set)

    except Exception as error:
        msg = f"kge_archiver(): {str(error)}"
        await report_bad_request(request, msg)

    return web.json_response(text='{"process_token": "'+process_token+'"}')


async def get_kge_fileset_processing_status(request: web.Request, process_token: str) -> web.Response:
    """Get the progress of post-processing of a KGE File Set.

    Poll the status of a given post-processing task.

    :param request:
    :type request: web.Request
    :param process_token: Process token associated with a KGE File Set post-processing task.
    :type process_token: str

    """
    # TODO: Stub...Implement me!
    return web.json_response(text='{"process_token": "' + process_token + '"}')
