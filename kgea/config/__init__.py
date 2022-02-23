from typing import Dict
from os import getenv
from os.path import dirname, abspath

import yaml

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def get_flag(name):
    value = getenv(name, default=0)
    value = int(value) if value else 0
    logger.debug(f"{name}=={not (not value)}")
    return value


# Master flag for local development runs bypassing
# authentication and other production processes
DEV_MODE = get_flag('DEV_MODE')
ARCHIVER_DEV_MODE = get_flag('ARCHIVER_DEV_MODE')
DOCKER_RUNNING = get_flag('DOCKER_RUNNING')

# the following config file should be visible in the 'kgea/config' subdirectory, as
# copied from the available template and populated with site-specific configuration values
CONFIG_FILE_PATH = abspath(dirname(__file__) + '/config.yaml')

PROVIDER_METADATA_FILE = 'provider.yaml'
FILE_SET_METADATA_FILE = 'file_set.yaml'
CONTENT_METADATA_FILE = 'content_metadata.json'  # this particular file is expected to be JSON and explicitly named

# Exported  'application configuration' dictionary
_app_config: Dict = dict()


def get_app_config() -> dict:
    """
    Gets application parameters
    :return:
    """
    if not _app_config:
        _load_app_config()
    return _app_config


def _load_app_config() -> dict:

    global _app_config

    try:
        with open(CONFIG_FILE_PATH, mode='r', encoding='utf-8') as app_config_file:

            config_raw = yaml.load(app_config_file, Loader=Loader)
            config: Dict = dict(config_raw)

            if 'aws' not in config:
                raise RuntimeError(
                    "Missing mandatory 'aws' configuration section in the "
                    "'~/kgea/config/config.yaml' configuration file."
                )
            else:
                if 's3' not in config['aws'] or \
                   'bucket' not in config['aws']['s3'] or \
                   'region' not in config['aws']['s3'] or \
                   'archive-directory' not in config['aws']['s3']:
                    raise RuntimeError(
                        "Missing mandatory aws.s3 'bucket', 'region' and/or 'archive-directory' "
                        " attribute in the 'aws.s3' section of the '~/kgea/config/config.yaml' configuration file."
                    )
                if 'access_key_id' not in config['aws'] or \
                   'secret_access_key' not in config['aws']:
                    logging.warning(
                        "Warning: AWS 'access_key_id' and 'secret_access_key' are " +
                        "not set in the '~/kgea/config/config.yaml' configuration file."
                    )
                    config['aws']['access_key_id'] = None
                    config['aws']['secret_access_key'] = None

                if 'default_region_name' not in config['aws'] or \
                   'host_account' not in config['aws'] or \
                   'guest_external_id' not in config['aws'] or \
                   'iam_role_name' not in config['aws']:
                    logging.warning(
                        "Missing AWS 'default_region_name', 'host_account', 'guest_external_id' and/or " +
                        "'iam_role_name' attributes in the '~/kgea/config/config.yaml' configuration file. You are "
                        "likely running within an EC2 instance (configured with a suitable instance profile role)."
                    )
                    config['aws'] = None
                    config['aws']['host_account'] = None
                    config['aws']['guest_external_id'] = None
                    config['aws']['iam_role_name'] = None
            if 'github' not in config:
                if DEV_MODE:
                    logger.warning(
                        "Github credentials are missing inside the application config.yaml file?\n" +
                        "These to be set for publication of KGE file set entries to the Translator Registry.\n" +
                        "Assume that you don't care... thus, the application will still run " +
                        "(only in DEV_MODE)."
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
                config['secret_key'] = fernet_key.decode("utf-8")

        if "log_level" in config:
            config["log_level"] = config["log_level"].upper()
        else:
            config["log_level"] = "INFO"
            
        # persist any updates back to config.yaml?
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

BACKEND_PATH = 'api/'
ARCHIVER_PATH = 'archiver/'
if DEV_MODE:
    # Development Mode for local testing

    # Point to http://localhost:8090 for frontend UI web application endpoints
    FRONTEND = "http://localhost:8090/"

    # Point to http://localhost:8080 for backend archive web service endpoints
    BACKEND = "http://localhost:8080/" + BACKEND_PATH

    if DOCKER_RUNNING:
        ARCHIVER = "http://archiver:8100/" + ARCHIVER_PATH
    else:
        ARCHIVER = "http://localhost:8100/" + ARCHIVER_PATH
else:
    # Production NGINX resolves relative paths otherwise?
    FRONTEND = "/"
    BACKEND = FRONTEND + BACKEND_PATH
    if DOCKER_RUNNING:
        ARCHIVER = "http://archiver:8100/" + ARCHIVER_PATH
    else:
        ARCHIVER = FRONTEND + ARCHIVER_PATH

##################################################
# Frontend Web Service Endpoints - all GET calls #
##################################################

LANDING_PAGE = FRONTEND
HOME_PAGE = f"{FRONTEND}home"
GRAPH_REGISTRATION_FORM = f"{FRONTEND}register/graph"
FILESET_REGISTRATION_FORM = f"{FRONTEND}register/fileset"
METADATA_PAGE = f"{FRONTEND}metadata"
UPLOAD_FORM = f"{FRONTEND}upload"
SUBMISSION_CONFIRMATION = f"{FRONTEND}submitted"
DATA_UNAVAILABLE = f"{FRONTEND}unavailable"

#################################
# Backend Web Service Endpoints #
#################################

# catalog controller
GET_KNOWLEDGE_GRAPH_CATALOG = f"{BACKEND}catalog"  # GET
REGISTER_KNOWLEDGE_GRAPH = f"{BACKEND}register/graph"  # POST
REGISTER_FILESET = f"{BACKEND}register/fileset"  # POST
PUBLISH_FILE_SET = f"{BACKEND}publish"  # GET

# upload controller
SETUP_UPLOAD_CONTEXT = f"{BACKEND}upload"  # GET
UPLOAD_FILE = f"{BACKEND}upload"  # POST
DIRECT_URL_TRANSFER = f"{BACKEND}upload/url"  # GET
CANCEL_UPLOAD = f"{BACKEND}upload/cancel"  # DELETE

GET_UPLOAD_STATUS = f"{BACKEND}upload/progress"  # GET

##################################
# Archiver Web Service Endpoints #
##################################
FILESET_TO_ARCHIVER = f"{ARCHIVER}process"
FILESET_ARCHIVER_STATUS = f"{ARCHIVER}status"


def _versioned_backend_target_url(kg_id: str, kg_version: str, target: str):
    return BACKEND + kg_id + "/" + kg_version + "/" + target  # GET


def get_fileset_metadata_url(kg_id: str, kg_version: str):
    """

    :param kg_id:
    :param kg_version:
    :return:
    """
    return _versioned_backend_target_url(kg_id, kg_version, target="metadata")


def get_meta_knowledge_graph_url(kg_id: str, kg_version: str):
    """

    :param kg_id:
    :param kg_version:
    :return:
    """
    return _versioned_backend_target_url(kg_id, kg_version, target="meta_knowledge_graph")


def get_fileset_download_url(kg_id: str, kg_version: str):
    """

    :param kg_id:
    :param kg_version:
    :return:
    """
    return _versioned_backend_target_url(kg_id, kg_version, target="download")
