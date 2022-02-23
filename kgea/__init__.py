"""
Configure KGE Logging
"""
from logging.config import dictConfig
from os.path import abspath, dirname

from kgea.config import get_app_config

_KGEA_APP_CONFIG = get_app_config()

dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    }},
    'handlers': {
        'tostdout': {
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stdout',
            'formatter': 'default'
        }
    },
    'loggers': {
        '': {  # root logger
            'level': 'WARNING',
            'handlers': ['tostdout'],
            'propagate': False
        },
        "kgea": {
            'level': _KGEA_APP_CONFIG["log_level"],
            'handlers': ['tostdout'],
            'propagate': False
        }
    }
})

API_DIR = f"{dirname(__file__)}/api"
PROVIDER_METADATA_TEMPLATE_FILE_PATH = abspath(f"{API_DIR}/kge_provider_metadata.yaml")
FILE_SET_METADATA_TEMPLATE_FILE_PATH = abspath(f"{API_DIR}/kge_fileset_metadata.yaml")
TRANSLATOR_SMARTAPI_TEMPLATE_FILE_PATH = abspath(f"{API_DIR}/kge_smartapi_entry.yaml")
