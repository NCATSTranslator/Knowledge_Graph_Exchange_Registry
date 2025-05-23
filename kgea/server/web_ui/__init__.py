"""
KGE Web User Interface Application Code package.
"""
from os import getenv, path
import logging

from kgea.server.web_services.kgea_session import KgeaSession

import jinja2
import aiohttp_jinja2
from aiohttp import web
import aiohttp_cors

from .kgea_ui_handlers import (
    kge_landing_page,
    kge_login,
    kge_client_authentication,
    get_kge_home,
    kge_logout,
    get_kge_graph_registration_form,
    view_kge_metadata,
    get_kge_fileset_registration_form,
    get_kge_file_upload_form,
    get_kge_fileset_submitted,
    get_kge_data_unavailable
)


async def make_app():
    """

    :return:
    """
    app = web.Application()

    # Configure Jinja2 template map
    templates_dir = path.join(path.dirname(__file__), 'templates')
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(templates_dir))

    app.router.add_get('/', kge_landing_page)
    app.router.add_get('/login', kge_login)
    app.router.add_get('/oauth2callback', kge_client_authentication)
    app.router.add_get('/home', get_kge_home)
    app.router.add_get('/logout', kge_logout)
    app.router.add_get('/register/graph', get_kge_graph_registration_form)
    app.router.add_get('/metadata', view_kge_metadata)
    app.router.add_get('/register/fileset', get_kge_fileset_registration_form)
    app.router.add_get('/upload', get_kge_file_upload_form)
    app.router.add_get('/submitted', get_kge_fileset_submitted)
    app.router.add_get('/unavailable', get_kge_data_unavailable)

    app.router.add_static('/css/',
                          path=templates_dir + '/css',
                          name='css')
    app.router.add_static('/images/',
                          path=templates_dir + '/images',
                          name='images')

    # Enable CORS for all origins.
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
            allow_methods="*"
        )
    })

    # Register all routers for CORS.
    for route in list(app.router.routes()):
        cors.add(route)

    KgeaSession.initialize(app)

    return app


def main():
    """
    Main application entry point.
    """
    # Master flag for local development runs bypassing
    # authentication and other production processes
    DEV_MODE = getenv('DEV_MODE', default=False)
    
    if DEV_MODE:
        logging.basicConfig(level=logging.DEBUG)

    web.run_app(make_app(), port=8090)

    KgeaSession.close_global_session()


