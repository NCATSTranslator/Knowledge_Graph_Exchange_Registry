from os import path, getenv
import connexion
import aiohttp_cors

import aiohttp_session

from .kgea_session import (
    initialize_global_session,
    close_global_session
)

# Master flag for local development runs bypassing authentication and other production processes
DEV_MODE = getenv('DEV_MODE', default=False)

if DEV_MODE:
    import base64
    from cryptography import fernet
    from aiohttp_session.cookie_storage import EncryptedCookieStorage
else:
    import aiomcache
    from aiohttp_session.memcached_storage import MemcachedStorage
    
    # Dockerized service name?
    MEMCACHED_SERVICE = "memcached"


def main():
    options = {
        "swagger_ui": True
    }
    specification_dir = path.join(path.dirname(__file__), 'openapi')
    app = connexion.AioHttpApp(__name__, specification_dir=specification_dir, options=options)
    
    app.add_api('openapi.yaml',
                arguments={
                    'title': 'OpenAPI for the NCATS Biomedical Translator Knowledge Graph EXchange (KGE) Archive'},
                pythonic_params=True,
                pass_context_arg_name='request')
    
    # Enable CORS for all origins.
    cors = aiohttp_cors.setup(app.app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
        )
    })
    
    # Register all routers for CORS.
    for route in list(app.app.router.routes()):
        cors.add(route)
    
    if DEV_MODE:
        # TODO: this needs to be global across the UI and Archive code bases(?!?)
        fernet_key = fernet.Fernet.generate_key()
        secret_key = base64.urlsafe_b64decode(fernet_key)
        aiohttp_session.setup(app.app, EncryptedCookieStorage(secret_key))
    else:
        mc = aiomcache.Client(MEMCACHED_SERVICE, 11211)
        storage = MemcachedStorage(mc)
        aiohttp_session.setup(app.app, storage)
    
    initialize_global_session()
    
    app.run(port=8080)
    
    close_global_session()
