from os import getenv, path
import logging

import aiohttp_session

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

# Master flag for local development runs bypassing authentication and other production processes
DEV_MODE = getenv('DEV_MODE', default=False)


async def make_app():

    app = web.Application()

    if DEV_MODE:
        # Development mode user sessions - probably don't work?
        import base64
        from cryptography import fernet
        from aiohttp_session.cookie_storage import EncryptedCookieStorage
        
        # TODO: this needs to be global across the UI and Archive code bases(?!?)
        # maybe share the secret_key across a common VOLUME path
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

    # Configure Jinja2 template map
    templates_dir = path.join(path.dirname(__file__), 'templates')
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
    if DEV_MODE:
        logging.basicConfig(level=logging.DEBUG)
    web.run_app(make_app(), port=8090)

