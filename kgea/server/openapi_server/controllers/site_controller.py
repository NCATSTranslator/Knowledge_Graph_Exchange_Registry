from aiohttp import web

from ..kgea_handlers import (
    kge_client_authentication,
    get_kge_home,
    kge_landing_page,
    kge_login,
    kge_logout
)


async def client_authentication(request: web.Request, code, state):
    """Process client authentication


    :param request:
    :type request: web.Request
    :param code:
    :type code: str
    :param state:
    :type state: str

    """
    # This method raises an obligatory web.HTTPFound exception
    await kge_client_authentication(request, code, state)


async def get_home(request: web.Request, session: str = None) -> web.Response:
    """Display home landing page

    :param request:
    :type request: web.Request
    :param session:
    :type session: str

    """
    return await get_kge_home(request, session)


async def landing_page(request: web.Request, session=None) -> web.Response:
    """Display landing page.

    :param request:
    :type request: web.Request
    :param session:
    :type session: str

    """
    return await kge_landing_page(request, session)


async def login(request: web.Request):
    """Process client user login

    :param request:
    :type request: web.Request

    """
    # This method raises an obligatory web.HTTPFound exception
    await kge_login(request)


async def logout(request: web.Request, session=None):
    """Process client user logout

    :param request:
    :type request: web.Request
    :param session:
    :type session: str

    """
    # This method raises an obligatory web.HTTPFound exception
    await kge_logout(request, session)
