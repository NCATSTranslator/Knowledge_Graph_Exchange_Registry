"""
Knowledge Graph Exchange File Set Archiver process
"""
import logging
from aiohttp import web

from .kge_archiver_handlers import kge_archiver

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
