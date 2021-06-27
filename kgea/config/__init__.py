from typing import Dict, Union, Optional
from os import getenv
from os.path import dirname, abspath

import yaml
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

import logging


# Master flag for local development runs bypassing
# authentication and other production processes
DEV_MODE = getenv('DEV_MODE', default=False)

# the following config file should be visible in the 'kgea/config' subdirectory, as
# copied from the available template and populated with site-specific configuration values
CONFIG_FILE_PATH = abspath(dirname(__file__) + '/config.yaml')

PROVIDER_METADATA_FILE = 'provider.yaml'
FILE_SET_METADATA_FILE = 'file_set.yaml'
CONTENT_METADATA_FILE = 'content_metadata.json'  # this particular file is expected to be JSON and explicitly named

# Exported  'application configuration' dictionary
_app_config: Dict[str, Union[Dict[str, Optional[str]], Union[Optional[str], bool]]] = dict()


def get_app_config() -> dict:
    if not _app_config:
        _load_app_config()
    return _app_config


def _load_app_config() -> dict:

    global _app_config

    try:
        with open(CONFIG_FILE_PATH, mode='r', encoding='utf-8') as app_config_file:

            config_raw = yaml.load(app_config_file, Loader=Loader)
            config: Dict[str, Union[Dict[str, Optional[str]], Union[Optional[str], bool]]] = dict(config_raw)

            if 'aws' not in config:
                raise RuntimeError(
                    "Missing mandatory 'aws' configuration section in the "
                    "'~/kgea/config/config.yaml' configuration file."
                )
            else:
                if 'host_account' not in config['aws']:
                    raise RuntimeError(
                        "Missing mandatory 'host_account' configuration section in the"
                        " 'aws' section of the '~/kgea/config/config.yaml' configuration file."
                    )
                else:
                    if 's3' not in config['aws'] or \
                       'bucket' not in config['aws']['s3'] or \
                       'is_access_point' not in config['aws']['s3'] or \
                       'region' not in config['aws']['s3'] or \
                       'archive-directory' not in config['aws']['s3']:
                        raise RuntimeError(
                            "Missing mandatory aws.s3 'bucket', 'is_access_point', 'region' and/or 'archive-directory' "
                            " attribute in the 'aws.s3' section of the '~/kgea/config/config.yaml' configuration file."
                        )
                    if 'guest_external_id' not in config['aws'] or \
                       'iam_role_name' not in config['aws']:
                        logging.warning(
                            "Missing aws 'guest_external_id' and/or 'iam_role_name' attributes" +
                            " in the '~/kgea/config/config.yaml' configuration file. Assume that you are running" +
                            " within an EC2 instance (configured with a suitable instance profile role)."
                        )
                        config['aws']['guest_external_id'] = None
                        config['aws']['iam_role_name'] = None
            if 'github' not in config:
                if DEV_MODE:
                    logging.warning(
                        "Github credentials are missing inside the application config.yaml file?\n" +
                        "These to be set for publication of KGE file set entries to the Translator Registry.\n"
                        "Assume that you don't care... thus, the application will still run (only in DEV_MODE)."
                    )
                else:
                    raise RuntimeError(
                        "Missing 'github.token' attribute in '~/kgea/config/config.yaml' configuration file!"
                    )

            config.setdefault("site_hostname", "https://archive.translator.ncats.io")

        if DEV_MODE:
            # For the EncryptedCookieStorage() managed
            # Session management during development
            if 'secret_key' not in config:
                import base64
                from cryptography import fernet

                fernet_key = fernet.Fernet.generate_key()
                secret_key = base64.urlsafe_b64decode(fernet_key)
                config['secret_key'] = str(secret_key)

                # persist updated updated config back to config.yaml?
                with open(CONFIG_FILE_PATH, mode='w', encoding='utf-8') as app_config_file:
                    yaml.dump(config, app_config_file, Dumper=Dumper)

        # cache the config globally
        _app_config = config

        return _app_config

    except Exception as exc:
        raise RuntimeError('KGE Archive resource configuration file failed to load? :' + str(exc))


#############################################################
# Here, we centralize the various application web endpoints #
#############################################################


BACKEND_PATH = 'archive/'
if DEV_MODE:
    # Development Mode for local testing

    # Point to http://localhost:8090 for frontend UI web application endpoints
    FRONTEND = "http://localhost:8090/"

    # Point to http://localhost:8080 for backend archive web service endpoints
    BACKEND = "http://localhost:8080/" + BACKEND_PATH
else:
    # Production NGINX resolves relative paths otherwise?
    FRONTEND = "/"
    BACKEND = FRONTEND + BACKEND_PATH

##################################################
# Frontend Web Service Endpoints - all GET calls #
##################################################

LANDING_PAGE = FRONTEND
HOME_PAGE = FRONTEND + "home"
GRAPH_REGISTRATION_FORM = FRONTEND + "register/graph"
FILESET_REGISTRATION_FORM = FRONTEND + "register/fileset"
METADATA_PAGE = FRONTEND + "metadata"
UPLOAD_FORM = FRONTEND + "upload"
DATA_UNAVAILABLE = FRONTEND + "unavailable"

#################################
# Backend Web Service Endpoints #
#################################

# catalog controller
GET_KNOWLEDGE_GRAPH_CATALOG = BACKEND + "catalog"  # GET
REGISTER_KNOWLEDGE_GRAPH = BACKEND + "register/graph"  # POST
REGISTER_FILESET = BACKEND + "register/fileset"  # POST
PUBLISH_FILE_SET = BACKEND + "publish"  # GET

# upload controller
SETUP_UPLOAD_CONTEXT = BACKEND + "upload"  # GET
UPLOAD_FILE = BACKEND + "upload"  # POST
GET_UPLOAD_STATUS = BACKEND + "upload/progress"  # GET


# content controllers
def _versioned_backend_target_url(kg_id: str, kg_version: str, target: str):
    return BACKEND + kg_id + "/" + kg_version + "/" + target  # GET


def get_fileset_metadata_url(kg_id: str, kg_version: str):
    return _versioned_backend_target_url(kg_id, kg_version, target="metadata")


def get_meta_knowledge_graph_url(kg_id: str, kg_version: str):
    return _versioned_backend_target_url(kg_id, kg_version, target="meta_knowledge_graph")


def get_fileset_download_url(kg_id: str, kg_version: str):
    return _versioned_backend_target_url(kg_id, kg_version, target="download")
