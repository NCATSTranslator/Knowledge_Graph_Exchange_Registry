from aiohttp import web

from kgea.server.archiver.kge_archiver_handlers import process_kge_fileset, get_kge_fileset_processing_status


async def process_fileset(request: web.Request) -> web.Response:
    """Posts a KGE File Set for post-processing after upload.

    Posts a KGE File Set for post-processing after upload.

    :param request:
    :type request: web.Request

    """
    return await process_kge_fileset(request)


async def get_processing_status(request: web.Request, process_token: str) -> web.Response:
    """Get the progress of post-processing of a KGE File Set.

    Poll the status of a given post-processing task.

    :param request:
    :type request: web.Request
    :param process_token: Process token associated with a KGE File Set post-processing task.
    :type process_token: str

    """
    return await get_kge_fileset_processing_status(request, process_token)
