"""
Knowledge Graph Exchange File Set Archiver process
"""
import asyncio
import logging
from aiohttp import web

from .kge_archiver_handlers import kge_archiver
from .kge_archiver_util import KgeArchiver

logging.basicConfig(level=logging.DEBUG)


async def make_app():
    """

    :return:
    """
    app = web.Application()

    app.router.add_get('/process', kge_archiver)

    return app


def main():
    """
    Main application entry point.
    """
    web.run_app(make_app(), port=8100)

    # The main event_loop is already closed in the web.run_app() so I retrieve a new one?
    loop = asyncio.get_event_loop()

    # Close the KgeArchiver worker tasks
    loop.run_until_complete(KgeArchiver.get_archiver().shutdown_workers())

    # Close the KgxValidator worker tasks
    # TODO: This code is commented out until the KgxValidator implementation is revisited
    # loop.run_until_complete(KgxValidator.shutdown_tasks())

    # see https://docs.aiohttp.org/en/v3.7.4.post0/client_advanced.html#graceful-shutdown
    # Zero-sleep to allow underlying connections to close
    loop.run_until_complete(asyncio.sleep(0))

    loop.close()
