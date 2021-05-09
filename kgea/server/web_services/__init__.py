from os import path
import connexion
import aiohttp_cors

from kgea.server.web_services.catalog.Catalog import KgeArchiveCatalog
from kgea.server.web_services.controllers.content_controller import download_file_set
from kgea.server.web_services.kgea_session import KgeaSession


def main():
    options = {
        "swagger_ui": True
    }
    specification_dir = path.join(path.dirname(__file__), 'openapi')
    app = connexion.AioHttpApp(
        __name__,
        specification_dir=specification_dir,
        options=options,
        server_args={
            "client_max_size": 1024**4
        }
    )
    
    app.add_api('openapi.yaml',
                arguments={
                    'title': 'OpenAPI for the Biomedical Translator Knowledge Graph EXchange Archive. ' +
                             'Although this API is SmartAPI compliant, it will not normally be visible in the ' +
                             'Translator SmartAPI Registry since it is mainly meant to be accessed through ' +
                             'Registry indexed KGE File Sets, which will have distinct entries in the Registry.'
                },
                pythonic_params=True,
                pass_context_arg_name='request')

    # See https://github.com/aio-libs/aiohttp-cors#usage

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

    # Add Amazon bucket CORS permission here?
    #
    # Downloading  URL: 'http://localhost:8080/archive/test_graph_for_kgx_validation/2021-04-24/download'
    # File download error: TypeError: NetworkError when attempting to fetch resource.
    # Cross-Origin Request Blocked: The Same Origin Policy disallows reading the remote resource
    # at ‘https://kgea-bucket.s3.amazonaws.com/kge-data/ \
    # test_graph_for_kgx_validation/2021-04-24/archive/test_graph_for_kgx_validation_2021-04-24.tar.gz? \
    # response-content-disposition=attachment& \
    # X-Amz-Algorithm=AWS4-HMAC-SHA256& \
    # X-Amz-Credential=AKIAI7TYXYCMFQ4BS3VQ/20210427/us-east-1/s3/aws4_request& \
    # X-Amz-Date=20210427T165619Z&X-Amz-Expires=86400&X-Amz-SignedHeaders=host& \
    # X-Amz-Signature=8ce60f9ab102ca90de7a6f7fff405760da42a3a0d1b142d08db2a21010af6448’
    # (Reason: Credential is not supported if the CORS header ‘Access-Control-Allow-Origin’ is ‘*’).

    # resource = cors.add(app.app.router.add_resource("/kge-data/test_graph_for_kgx_validation/2021-04-24/archive/"))
    # cors.add(
    #     resource.add_route("GET", download_file_set), {
    #         "https://kgea-bucket.s3.amazonaws.com": aiohttp_cors.ResourceOptions(
    #             allow_credentials=True,
    #             # expose_headers=("X-Custom-Server-Header",),
    #             allow_headers=( "Content-Type"),
    #             max_age=3600,
    #         )
    #     })

    KgeaSession.initialize(app.app)

    KgeArchiveCatalog.initialize()

    app.run(port=8080)

    KgeaSession.close_global_session()
