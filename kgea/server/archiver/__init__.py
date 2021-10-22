import os
import connexion


def main():
    options = {
        "swagger_ui": True
        }
    specification_dir = os.path.join(os.path.dirname(__file__), 'openapi')
    app = connexion.AioHttpApp(__name__, specification_dir=specification_dir, options=options)
    app.add_api('openapi.yaml',
                arguments={'title': 'OpenAPI for the Biomedical Translator Knowledge Graph EXchange Archiver'
                                    ' worker process which post-processes KGE File Sets which have been uploaded.'
                                    ' Although this API is SmartAPI compliant, it will not normally be visible'
                                    ' in the Translator SmartAPI Registry since it is mainly meant to be only'
                                    ' accessed internally by the KGE Archiver back end.'
                           },
                pythonic_params=True,
                pass_context_arg_name='request')

    app.run(port=8100)
