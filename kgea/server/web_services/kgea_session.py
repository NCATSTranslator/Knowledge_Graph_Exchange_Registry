# Design pattern for aiohttp session aware handlers:
#
# async def handler(request):
#     session = await get_session(request)
#     last_visit = session['last_visit'] if 'last_visit' in session else None
#     text = 'Last visited: {}'.format(last_visit)
#     return web.Response(text=text)

from os import getenv
from typing import Dict
from uuid import uuid4

import asyncio
from asyncio.events import AbstractEventLoop

from aiohttp import web, ClientSession
from aiohttp_session import AbstractStorage, setup, new_session, get_session
from multidict import MultiDict

from kgea.config import get_app_config

import logging

# Master flag for simplified local development
from kgea.server.web_services import KgeArchiveCatalog

DEV_MODE = getenv('DEV_MODE', default=False)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class KgeaSession:
    _session_storage: AbstractStorage
    _event_loop: AbstractEventLoop
    _client_session: ClientSession

    @classmethod
    def initialize(cls, app=None):
        """
        Initialize a global KGE Archive Client Session
        """

        if app:
            storage = cls.get_storage()
            setup(app, storage)
        else:
            raise RuntimeError("Invalid web application?")

        cls._event_loop = asyncio.get_event_loop()
        cls._client_session = ClientSession(loop=cls._event_loop)

    @classmethod
    def _initialize_storage(cls):
        app_config = get_app_config()
        if DEV_MODE:
            from aiohttp_session.cookie_storage import EncryptedCookieStorage
            # TODO: this needs to be global across the UI and Archive code bases(?!?)
            import base64
            secret_key = base64.urlsafe_b64decode(str.encode(app_config['secret_key'],"utf-8"))
            cls._session_storage = EncryptedCookieStorage(secret_key)
        else:
            import aiomcache
            from aiohttp_session.memcached_storage import MemcachedStorage
            mc = aiomcache.Client("memcached", 11211)
            # we assume an HTTPS SSL secured site, hence 'secure=True'
            cls._session_storage = MemcachedStorage(mc, secure=True)

    @classmethod
    def get_storage(cls) -> AbstractStorage:
        """

        :return:
        """
        try:
            cls._session_storage
        except AttributeError:
            # I'm not sure why this may have to
            # be called more than twice... some
            # async contexts may call it more often?
            cls._initialize_storage()

        return cls._session_storage

    @classmethod
    def get_event_loop(cls) -> AbstractEventLoop:
        """

        :return:
        """
        return cls._event_loop

    @classmethod
    async def save_session(cls, request, response, session):
        """

        :param request:
        :param response:
        :param session:
        """
        storage = cls.get_storage()
        await storage.save_session(request, response, session)

    @classmethod
    def get_global_session(cls) -> ClientSession:
        """
        Get the current global KGE Archive Client Session
        """
        return cls._client_session

    @classmethod
    async def _close_kgea_global_session(cls):
        await cls._client_session.close()

    @classmethod
    def close_global_session(cls):
        """
        Close the current global KGE Archive Client Session
        """
        # The main event_loop is already closed in
        # the web.run_app() so I retrieve a new one?
        loop = asyncio.get_event_loop()

        # Close the global Client Session
        loop.run_until_complete(cls._close_kgea_global_session())

        # Close the KgeArchiveCatalog
        loop.run_until_complete(KgeArchiveCatalog.catalog().close())
        
        # see https://docs.aiohttp.org/en/v3.7.4.post0/client_advanced.html#graceful-shutdown
        # Zero-sleep to allow underlying connections to close
        loop.run_until_complete(asyncio.sleep(0))

        loop.close()


async def initialize_user_session(request, uid: str = None, user_attributes: Dict = None):
    """

    :param request:
    :param uid:
    :param user_attributes:
    """
    try:
        session = await new_session(request)

        if not uid:
            uid = uuid4().hex

        # TODO: the identifier field value doesn't seem to be propagated (in aiohttp 3.6 - review status in 3.7)
        session.set_new_identity(uid)

        session['uid'] = uid

        if user_attributes:
            session['username'] = user_attributes.setdefault("preferred_username", 'anonymous')
            session['name'] = user_attributes.setdefault("given_name", '') + ' ' + \
                              user_attributes.setdefault("family_name", 'anonymous')
            session['email'] = user_attributes.setdefault("email", '')

    except RuntimeError as rte:
        await report_error(request, "initialize_user_session() ERROR: " + str(rte))


async def with_session(request, response):
    """
    Wraps a response with a session cookie
    :param request: input request object
    :param response: target output response object
    :return:
    """
    try:
        session = await get_session(request)
        await KgeaSession.save_session(request, response, session)
    except RuntimeError as rte:
        await report_error(request, "kgea_session.with_session() RuntimeError: " + str(rte))

    return response


# TODO: session propagation with redirects only work
#       for aiohttp<3.7 (now) or aiohttp>3.8 (later)
async def _process_redirection(request, response, active_session):
    """
    Redirects to a web path location, with or without session cookie.

    :param request: input request
    :param response: redirection response
    :param active_session: add session cookie if True (default: False)
    :type active_session: bool
    :return: raised web.HTTPFound(location)
    """
    if active_session:
        try:
            session = await get_session(request)
            await KgeaSession.save_session(request, response, session)
        except RuntimeError as rte:
            await report_error(request, "kgea_session._process_redirection() RuntimeError: " + str(rte))

    raise response


async def redirect(request, location: str, active_session: bool = False):
    """

    :param request:
    :param location:
    :param active_session:
    """
    # TODO: might need to urlencode query parameter values in the location?
    logger.debug('redirect() to location: ' + str(location))
    await _process_redirection(
        request,
        web.HTTPFound(location),
        active_session
    )


async def download(request, location: str, active_session: bool = False):
    """

    :param request:
    :param location:
    :param active_session:
    """
    logger.debug('download() file from location: ' + str(location))
    await _process_redirection(
        request,
        web.HTTPFound(location, headers=MultiDict({
            'CONTENT-DISPOSITION': 'attachment'
        })),
        active_session
    )


async def report_not_found(request, reason: str, active_session: bool = False):
    """

    :param request:
    :param reason:
    :param active_session:
    """
    await _process_redirection(
        request,
        web.HTTPNotFound(reason=reason),
        active_session
    )


async def report_error(request, reason: str, active_session: bool = False):
    """

    :param request:
    :param reason:
    :param active_session:
    """
    await _process_redirection(
        request,
        web.HTTPBadRequest(reason=reason),
        active_session
    )
