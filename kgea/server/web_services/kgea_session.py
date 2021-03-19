from os import getenv
from uuid import uuid4

import asyncio
from asyncio.events import AbstractEventLoop

from aiohttp import web, ClientSession
from aiohttp_session import AbstractStorage, setup, new_session, get_session
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


async def initialize_user_session(request, uid: str = None):
    try:
        session = await new_session(request)
        
        if uid:
            user_id = uid
        else:
            user_id = uuid4().hex
        
        # the identifier field value doesn't seem to be
        # propagated (in aiohttp 3.6 - review status in 3.7)
        session.set_new_identity(user_id)
        
        session['user_id'] = user_id
    
    except RuntimeError as rte:
        logger.error("initialize_user_session() ERROR: " + str(rte))
        raise RuntimeError(rte)


async def save_session(request, response, session):
    await _kgea_global_session_storage.save_session(request, response, session)

# Design pattern for aiohttp session aware handlers:
# async def handler(request):
#     session = await get_session(request)
#     last_visit = session['last_visit'] if 'last_visit' in session else None
#     text = 'Last visited: {}'.format(last_visit)
#     return web.Response(text=text)


async def with_session(request, response):
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


# AIOHTTP Redirects don't seem to propagate
# cookies (problematic for propagating session state)
# As a workaround, if the session exists, add the
# session.identity string as a 'uid' querystring to the
# redirection location for possible recovery again at the other end(?)
async def redirect(request, location, active_session: bool = False):
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
            # response = web.HTTPFound(location+"?uid="+session.identity)
            await save_session(request, response, session)
        except RuntimeError as rte:
            logger.error("kgea_session.redirect() RuntimeError: " + str(rte))
            raise RuntimeError(rte)
    # else:
    #     response = web.HTTPFound(location)
    raise response


def report_error(reason: str):
    raise web.HTTPBadRequest(reason=reason)
    

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
    # The main event_loop is already closed in
    # the web.run_app() so I retrieve a new one?
    loop = asyncio.get_event_loop()
    
    # Close the global Client Session
    loop.run_until_complete(_close_kgea_global_session())
    
    # see https://docs.aiohttp.org/en/v3.7.4.post0/client_advanced.html#graceful-shutdown
    # Zero-sleep to allow underlying connections to close
    loop.run_until_complete(asyncio.sleep(0))
    
    loop.close()
