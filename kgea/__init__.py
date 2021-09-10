"""
Configure KGE Logging
"""
from logging.config import dictConfig

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
