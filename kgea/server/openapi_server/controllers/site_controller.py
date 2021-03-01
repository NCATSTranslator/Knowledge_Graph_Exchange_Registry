from typing import List, Dict
from aiohttp import web

from openapi_server import util


async def client_authentication(request: web.Request, code, state) -> web.Response:
    """Process client authentication

    

    :param code: 
    :type code: str
    :param state: 
    :type state: str

    """
    return web.Response(status=200)


async def get_home(request: web.Request, session=None) -> web.Response:
    """Display home landing page

    

    :param session: 
    :type session: str

    """
    return web.Response(status=200)


async def landing_page(request: web.Request, session=None) -> web.Response:
    """Display landing page.

    

    :param session: 
    :type session: str

    """
    return web.Response(status=200)


async def login(request: web.Request, ) -> web.Response:
    """Process client user login

    


    """
    return web.Response(status=200)


async def logout(request: web.Request, session=None) -> web.Response:
    """Process client user logout

    

    :param session: 
    :type session: str

    """
    return web.Response(status=200)
