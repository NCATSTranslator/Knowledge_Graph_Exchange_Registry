from typing import Optional
from uuid import uuid4

from aiohttp import web

from kgea.server.archiver.kge_archiver_util import KgeArchiver

import logging

from kgea.server.catalog import KgeFileSet

logger = logging.getLogger(__name__)


async def process_kge_fileset(request: web.Request) -> web.Response:
    """Posts a KGE File Set for post-processing after upload.

    Posts a KGE File Set for post-processing after upload.

    :param request:
    :type request: web.Request
    """
    data = await request.post()

    kg_id = data.get('kg_id', default='')
    if not kg_id:
        err_msg = "kge_archiver(): missing the knowledge graph 'kg_id' POST parameter"
        logger.error(err_msg)
        raise web.HTTPBadRequest(reason=err_msg)

    # TODO: How do I really access the file set here?
    fileset = data.get('fileset', default='')
    if not fileset:
        err_msg = "kge_archiver(): missing 'fileset' POST parameter"
        logger.error(err_msg)
        raise web.HTTPBadRequest(reason=err_msg)

    file_set: Optional[KgeFileSet] = None

    try:
        # Assemble a standard KGX Fileset archive ('tar.gz') with a computed SHA1 hash sum
        archiver: KgeArchiver = KgeArchiver.get_archiver()
        await archiver.process(file_set)

    except Exception as error:
        msg = f"kge_archiver(): {str(error)}"
        file_set.report_error(msg)

    # Need something to track the activity here?
    process_token = uuid4().hex

    return web.json_response(text='{"archive_token": "'+process_token+'"}')


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
