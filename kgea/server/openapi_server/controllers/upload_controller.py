from aiohttp import web

from ..kgea_handlers import (
    get_kge_file_upload_form,
    get_kge_registration_form,
    register_kge_file_set,
    upload_kge_file,
)


async def get_file_upload_form(request: web.Request, session: str, submitter: str, kg_name: str) -> web.Response:
    """Get web form for the KGE File Set upload process


    :param request:
    :type request: web.Request
    :param session:
    :type session: str
    :param submitter:
    :type submitter: str
    :param kg_name:
    :type kg_name: str

    """
    return await get_kge_file_upload_form(request, session, submitter, kg_name)


async def get_registration_form(request: web.Request, session: str) -> web.Response:
    """Prompt user for core parameters of the KGE File Set upload

    :param request:
    :type request: web.Request
    :param session:
    :type session: str

    """
    return await get_kge_registration_form(request, session)


async def register_file_set(request: web.Request) -> web.Response:
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
