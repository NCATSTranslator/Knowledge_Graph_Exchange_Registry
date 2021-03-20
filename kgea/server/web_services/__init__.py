from os import path
import connexion
import aiohttp_cors

from kgea.server.web_services.kgea_session import KgeaSession


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

    KgeaSession.init(app.app)
    
    app.run(port=8080)
    
    KgeaSession.close_global_session()
