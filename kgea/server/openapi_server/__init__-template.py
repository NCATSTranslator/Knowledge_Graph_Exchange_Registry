import os
import connexion
import aiohttp_cors

import aiohttp_session
import aiomcache
from aiohttp_session.memcached_storage import MemcachedStorage

# TODO: configure the session management storage Docker-aware
MEMCACHED_SERVICE = "localhost"

# Docker Service container name
# MEMCACHED_SERVICE = "memcached"


def main():
    options = {
        "swagger_ui": True
        }
    specification_dir = os.path.join(os.path.dirname(__file__), 'openapi')
    app = connexion.AioHttpApp(__name__, specification_dir=specification_dir, options=options)

    app.add_api('openapi.yaml',
                arguments={'title': 'OpenAPI for the NCATS Biomedical Translator Knowledge Graph EXchange (KGE) Archive'},
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

    mc = aiomcache.Client(MEMCACHED_SERVICE, 11211)
    storage = MemcachedStorage(mc)
    aiohttp_session.setup(app, storage)

    app.run(port=8080)
