from os import getenv
from os.path import expanduser, dirname, abspath

import boto3
from botocore.client import Config

import configparser
import yaml

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

# the following config file should be visible in the 'kgea/server/config' subdirectory, as
# copied from the available template and populated with site-specific configuration values
CONFIG_FILE_PATH = abspath(dirname(__file__) + '/config.yaml')

# Master flag for local development runs bypassing
# authentication and other production processes
DEV_MODE = getenv('DEV_MODE', default=False)

home = expanduser("~")
AWS_CONFIG_ROOT = home + "/.aws/"


def validate_session_configuration():
    try:
        with open(AWS_CONFIG_ROOT + 'credentials', 'r') as credentials_file:
            client_credentials = boto3.Session().get_credentials().get_frozen_credentials()
            
            credentials_config = configparser.ConfigParser()
            credentials_config.read_file(credentials_file)
            
            try:
                assert (client_credentials.access_key == credentials_config['default']['aws_access_key_id'])
            except AssertionError:
                raise AssertionError("the boto3 client does not have correct aws_access_key_id")
            
            try:
                assert (client_credentials.secret_key == credentials_config['default']['aws_secret_access_key'])
            except AssertionError:
                raise AssertionError("the boto3 client does not have correct aws_secret_access_key")
    
    except FileNotFoundError as e:
        print("ERROR: ~/.aws/credentials isn't found! try running `aws configure` after installing `aws-cli`")
        print(e)
        return False
    except AssertionError as e:
        print("ERROR: boto3 s3 client has different configuration information from ~/.aws/credentials!")
        print(e)
        return False
    except KeyError as e:
        print("ERROR: ~/.aws/credentials does not have all the necessary keys")
        print(e)
        return False
    
    return True


def validate_client_configuration():
    try:
        with open(AWS_CONFIG_ROOT + 'old_config', 'r') as config_file:
            client_credentials = boto3.client("s3")._client_config
            config = configparser.ConfigParser()
            config.read_file(config_file)
            
            # if old_config['default']['region'] != 'us-east-1':
            #     print("NOTE: we recommend using us-east-1 as your region", "(currently %s)" % old_config['default']['region'])
            #     # this is a warning, no need to return false
            
            try:
                assert (client_credentials.region_name == config['default']['region'])
            except AssertionError:
                raise AssertionError("the boto3 client does not have the same region as `~/.aws/old_config")
    
    except FileNotFoundError as e:
        print("ERROR: ~/.aws/old_config isn't found! try running `aws configure` after installing `aws-cli`")
        print(e)
        return False
    except AssertionError as e:
        print("ERROR: boto3 s3 client has different configuration information from ~/.aws/old_config!")
        print(e)
        return False
    except KeyError as e:
        print("ERROR: ~/.aws/old_config does not have all the necessary keys")
        print(e)
        return False
    finally:
        return True


s3_client = None

try:
    assert (validate_session_configuration())
    assert (validate_client_configuration())
    s3_client = boto3.client('s3', config=Config(signature_version='s3v4'))
except Exception as e:
    print('ERROR: s3 configuration failed to load, kgea may not work properly')
    print(e)

# Exported  'application configuration' dictionary
app_config: dict = dict()


def get_app_config() -> dict:
    return app_config


def load_app_config() -> dict:
    
    global app_config
    
    try:
        with open(CONFIG_FILE_PATH, mode='r', encoding='utf-8') as app_config_file:
            
            app_config_raw = yaml.load(app_config_file, Loader=Loader)
            
            if 'bucket' not in app_config_raw:
                raise RuntimeError("The app_config doesn't have all its necessary attributes")
            else:
                if s3_client is not None:
                    # TODO: detect the bucket here
                    # if not detected, raise an error
                    pass
            
            app_config = dict(app_config_raw)
        
        if DEV_MODE:
            # For the EncryptedCookieStorage() managed
            # Session management during development
            if 'secret_key' not in app_config:
                import base64
                from cryptography import fernet
                
                fernet_key = fernet.Fernet.generate_key()
                secret_key = base64.urlsafe_b64decode(fernet_key)
                app_config['secret_key'] = secret_key
                
                # persist updated old_config back?
                with open(CONFIG_FILE_PATH, mode='w', encoding='utf-8') as app_config_file:
                    yaml.dump(app_config, app_config_file, Dumper=Dumper)
        
        return app_config
    
    except Exception as exc:
        raise RuntimeError('KGE Archive resource configuration file failed to load? :' + str(exc))
