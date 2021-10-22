from typing import Optional
from uuid import uuid4

from aiohttp import web

from kgea.server.web_services.catalog import KgeFileSet
from kgea.server.archiver.kge_archiver_util import compress_fileset, KgeArchiver

import logging

logger = logging.getLogger(__name__)


async def kge_archiver(request: web.Request) -> web.Response:

    kg_id = request.query.get('kg_id', default='')
    if not kg_id:
        err_msg = "kge_archiver(): missing the knowledge graph 'kg_id'"
        logger.error(err_msg)
        raise web.HTTPBadRequest(reason=err_msg)

    fileset_version = request.query.get('fileset_version', default='')
    if not fileset_version:
        err_msg = "kge_archiver(): missing 'fileset_version'"
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
    archive_token = uuid4().hex

    return web.json_response(text='{"archive_token": "'+archive_token+'"}')
