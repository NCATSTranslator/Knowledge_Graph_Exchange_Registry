from aiohttp import web

from ..kgea_handlers import (
    register_kge_file_set,
    upload_kge_file,
)


async def register_file_set(request: web.Request):
    """Register core parameters for the KGE File Set upload

    :param request:
    :type request: web.Request

    """
    # This method raises an obligatory web.HTTPFound exception
    await register_kge_file_set(request)


async def upload_file(request: web.Request) -> web.Response:
    """Upload processing of KGE File Set file

    :param request:
    :type request: web.Request

    """
    return await upload_kge_file(request)
