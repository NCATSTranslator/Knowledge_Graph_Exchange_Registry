from typing import List, Dict
from aiohttp import web

from openapi_server import util


async def get_file_upload_form(request: web.Request, session, submitter, kg_name) -> web.Response:
    """Get web form for the KGE File Set upload process

    

    :param session: 
    :type session: str
    :param submitter: 
    :type submitter: str
    :param kg_name: 
    :type kg_name: str

    """
    return web.Response(status=200)


async def get_registration_form(request: web.Request, session) -> web.Response:
    """Prompt user for core parameters of the KGE File Set upload

    

    :param session: 
    :type session: str

    """
    return web.Response(status=200)


async def register_file_set(request: web.Request, session, submitter, kg_name) -> web.Response:
    """Register core parameters for the KGE File Set upload

    

    :param session: 
    :type session: str
    :param submitter: 
    :type submitter: str
    :param kg_name: 
    :type kg_name: str

    """
    return web.Response(status=200)


async def upload_file(request: web.Request, session, upload_mode, content_url=None, content_file=None) -> web.Response:
    """Upload processing of KGE File Set file

    

    :param session: 
    :type session: str
    :param upload_mode: 
    :type upload_mode: str
    :param content_url: 
    :type content_url: str
    :param content_file: 
    :type content_file: str

    """
    return web.Response(status=200)
