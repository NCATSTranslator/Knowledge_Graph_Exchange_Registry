import os
import logging

import aiohttp_session
import aiomcache
from aiohttp_session.memcached_storage import MemcachedStorage

import jinja2
import aiohttp_jinja2
from aiohttp import web

from .kgea_ui_handlers import (
    kge_landing_page,
    kge_login,
    kge_client_authentication,
    get_kge_home,
    kge_logout,
    get_kge_registration_form,
    get_kge_file_upload_form
)

# TODO: configure the session management storage to automatically be Docker-aware and have a mock session instead
# MEMCACHED_SERVICE = "localhost"

# Docker Service container name
MEMCACHED_SERVICE = "memcached"


async def make_app():

    app = web.Application()

    mc = aiomcache.Client(MEMCACHED_SERVICE, 11211)
    storage = MemcachedStorage(mc)
    aiohttp_session.setup(app, storage)

    # Configure Jinja2 template map
    templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(templates_dir))

    app.router.add_get('/', kge_landing_page)
    app.router.add_get('/login', kge_login)
    app.router.add_get('/oauth2callback', kge_client_authentication)
    app.router.add_get('/home', get_kge_home)
    app.router.add_get('/logout', kge_logout)
    app.router.add_get('/register', get_kge_registration_form)
    app.router.add_get('/upload', get_kge_file_upload_form)

    return app


def main():
    logging.basicConfig(level=logging.DEBUG)
    web.run_app(make_app(), port=8090)

