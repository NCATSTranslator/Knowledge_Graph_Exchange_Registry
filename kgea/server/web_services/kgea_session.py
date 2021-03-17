from os import getenv

import asyncio
from asyncio.events import AbstractEventLoop

from aiohttp import ClientSession
import aiohttp_session

# Master flag for simplified local development
DEV_MODE = getenv('DEV_MODE', default=False)

# Global KGE Archive Client Session for
# AIOHTTP requests within the application
_kgea_global_session: ClientSession
_kgea_event_loop: AbstractEventLoop


def initialize_global_session(app=None):
    """
    Initialize a global KGE Archive Client Session
    """
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
            aiohttp_session.setup(app, EncryptedCookieStorage(secret_key))
        else:
            import aiomcache
            from aiohttp_session.memcached_storage import MemcachedStorage
        
            # Dockerized service name?
            MEMCACHED_SERVICE = "memcached"
            
            mc = aiomcache.Client(MEMCACHED_SERVICE, 11211)
            storage = MemcachedStorage(mc)
            aiohttp_session.setup(app, storage)
        
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
