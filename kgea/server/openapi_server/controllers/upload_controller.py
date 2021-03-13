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


async def upload_file(
        request: web.Request,
        kg_name,
        submitter,
        upload_mode: str,
        content_url: str = None,
        uploaded_file=None
) -> web.Response:
    """Upload processing of KGE File Set file

    :param request:
    :type request: web.Request
    :param kg_name:
    :type kg_name: str
    :param submitter:
    :type submitter: str
    :param upload_mode:
    :type upload_mode: str
    :param content_url:
    :type content_url: str
    :param uploaded_file:
    :type uploaded_file: FileField

    """
    return await upload_kge_file(request, kg_name, submitter, upload_mode, content_url, uploaded_file)
