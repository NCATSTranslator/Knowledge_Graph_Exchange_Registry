from aiohttp import web

from kgea.server.archiver.kge_archiver_util import compress_fileset

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

    s3_archive_key = await compress_fileset(kg_id, fileset_version)

    return web.json_response(text='{"s3_archive_key": "'+s3_archive_key+'"}')
