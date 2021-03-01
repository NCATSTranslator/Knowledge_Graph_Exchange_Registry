from aiohttp import web

from ..kgea_handlers import (
    kge_client_authentication,
    get_kge_home,
    kge_landing_page,
    kge_login,
    kge_logout
)


async def client_authentication(request: web.Request, code, state) -> web.Response:
    """Process client authentication

    
    :param request:
    :type request: web.Request
    :param code: 
    :type code: str
    :param state: 
    :type state: str

    """
    return kge_client_authentication(request, code, state)


async def get_home(request: web.Request, session: str = None) -> web.Response:
    """Display home landing page

    :param request:
    :type request: web.Request
    :param session: 
    :type session: str

    """
    return get_kge_home(request, session)


async def landing_page(request: web.Request, session=None) -> web.Response:
    """Display landing page.

    :param request:
    :type request: web.Request
    :param session: 
    :type session: str

    """
    return kge_landing_page(request, session)


async def login(request: web.Request, ) -> web.Response:
    """Process client user login

    :param request:
    :type request: web.Request

    """
    return kge_login(request)


async def logout(request: web.Request, session=None) -> web.Response:
    """Process client user logout

    :param request:
    :type request: web.Request
    :param session: 
    :type session: str

    """
    return kge_logout(request, session)
