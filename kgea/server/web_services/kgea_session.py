from os import getenv

import asyncio
from asyncio.events import AbstractEventLoop

from aiohttp import web, ClientSession
from aiohttp_session import AbstractStorage, setup, get_session

import logging

# Master flag for simplified local development
DEV_MODE = getenv('DEV_MODE', default=False)

logger = logging.getLogger(__name__)
if DEV_MODE:
    logger.setLevel(logging.DEBUG)

# Global KGE Archive Client Session for
# AIOHTTP requests within the application
_kgea_global_session_storage: AbstractStorage
_kgea_global_session: ClientSession
_kgea_event_loop: AbstractEventLoop


async def is_active_session(request):
    cookie = _kgea_global_session_storage.load_cookie(request)
    if cookie is not None:
        return True
    else:
        return False


async def save_session(request, response, session):
    await _kgea_global_session_storage.save_session(request, response, session)

# Design pattern for aiohttp session aware handlers:
# async def handler(request):
#     session = await get_session(request)
#     last_visit = session['last_visit'] if 'last_visit' in session else None
#     text = 'Last visited: {}'.format(last_visit)
#     return web.Response(text=text)


def with_session(request, response):
    """
    Wraps a response with a session cookie
    :param request: input request object
    :param response: target output response object
    :return:
    """
    try:
        session = await get_session(request)
        await save_session(request, response, session)
    except RuntimeError as rte:
        logger.error("kgea_session.with_session() RuntimeError: " + str(rte))
        raise RuntimeError(rte)
    return response


def redirect(request, location, active_session: bool = False):
    """
    Redirects to a web path location, with or without session cookie.

    :param request: input request
    :param location: target URL of redirection
    :param active_session: add session cookie if True (default: False)
    :type active_session: bool
    :return: raised web.HTTPFound(location)
    """
    response = web.HTTPFound(location)
    if active_session:
        try:
            session = await get_session(request)
            await save_session(request, response, session)
        except RuntimeError as rte:
            logger.error("kgea_session.redirect() RuntimeError: " + str(rte))
            raise RuntimeError(rte)
    raise response


def initialize_global_session(app=None):
    """
    Initialize a global KGE Archive Client Session
    """
    global _kgea_global_session_storage
    global _kgea_global_session
    global _kgea_event_loop
    
    if app:
        if DEV_MODE:
            import base64
            from cryptography import fernet
            from aiohttp_session.cookie_storage import EncryptedCookieStorage
            
            # TODO: this needs to be global across the UI and Archive code bases(?!?)
            fernet_key = fernet.Fernet.generate_key()
            secret_key = base64.urlsafe_b64decode(fernet_key)
            _kgea_global_session_storage = EncryptedCookieStorage(secret_key)
        else:
            import aiomcache
            from aiohttp_session.memcached_storage import MemcachedStorage
        
            # Dockerized service name?
            MEMCACHED_SERVICE = "memcached"
            
            mc = aiomcache.Client(MEMCACHED_SERVICE, 11211)
            _kgea_global_session_storage = MemcachedStorage(mc)
            
        setup(app, _kgea_global_session_storage)
        
    _kgea_event_loop = asyncio.get_event_loop()
    _kgea_global_session = ClientSession(loop=_kgea_event_loop)


def get_event_loop() -> AbstractEventLoop:
    return _kgea_event_loop


def get_global_session() -> ClientSession:
    return _kgea_global_session


async def _close_kgea_global_session():
    await _kgea_global_session.close()


def close_global_session():
    """
    Close the current global KGE Archive Client Session
    """
    # Close the global Client Session
    _kgea_event_loop.run_until_complete(_close_kgea_global_session())
    
    # see https://docs.aiohttp.org/en/v3.7.4.post0/client_advanced.html#graceful-shutdown
    # Zero-sleep to allow underlying connections to close
    _kgea_event_loop.run_until_complete(asyncio.sleep(0))
    
    _kgea_event_loop.close()
