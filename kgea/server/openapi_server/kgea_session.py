from asyncio.events import AbstractEventLoop

from aiohttp import ClientSession
import asyncio

# Global KGE Archive Client Session for
# AIOHTTP requests within the application
_kgea_global_session: ClientSession
_kgea_event_loop: AbstractEventLoop


def initialize_global_session():
    """
    Initialize a global KGE Archive Client Session
    """
    global _kgea_global_session
    global _kgea_event_loop
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
