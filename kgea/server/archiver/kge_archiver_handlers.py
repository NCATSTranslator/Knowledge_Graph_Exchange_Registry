from aiohttp import web
from os.path import sep, dirname, abspath

from kgea.aws.assume_role import aws_config
from kgea.server import run_script

import logging

logger = logging.getLogger(__name__)

s3_config = aws_config['s3']
default_s3_bucket = s3_config['bucket']
default_s3_root_key = s3_config['archive-directory']

_KGEA_ARCHIVER_SCRIPT = f"{dirname(abspath(__file__))}{sep}scripts{sep}kge_archiver.bash"


async def compress_fileset(
        kg_id,
        version,
        bucket=default_s3_bucket,
        root=default_s3_root_key
) -> str:
    """
    :param kg_id:
    :param version:
    :param bucket:
    :param root:
    :return:
    """
    s3_archive_key = f"s3://{bucket}/{root}/{kg_id}/{version}/archive/{kg_id + '_' + version}.tar.gz"

    logger.info(f"Initiating execution of compress_fileset({s3_archive_key})")

    try:
        return_code = await run_script(
            script=_KGEA_ARCHIVER_SCRIPT,
            args=(bucket, root, kg_id, version)
        )
        logger.info(f"Finished archive script build {s3_archive_key}, return code: {str(return_code)}")

    except Exception as e:
        logger.error(f"compress_fileset({s3_archive_key}) exception: {str(e)}")

    logger.info(f"Exiting compress_fileset({s3_archive_key})")

    return s3_archive_key


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
