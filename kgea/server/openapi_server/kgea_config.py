import boto3
from botocore.client import Config

import configparser
import yaml
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

from os.path import expanduser, abspath
from pathlib import Path

home = expanduser("~")
AWS_CONFIG_ROOT = home+"/.aws/"


def validate_session_configuration():
    try:
        with open(AWS_CONFIG_ROOT+'credentials', 'r') as credentials_file:
            client_credentials = boto3.Session().get_credentials().get_frozen_credentials()

            credentials_config = configparser.ConfigParser()
            credentials_config.read_file(credentials_file)

            try:
                assert(client_credentials.access_key == credentials_config['default']['aws_access_key_id'])
            except AssertionError:
                raise AssertionError("the boto3 client does not have correct aws_access_key_id")
                return False

            try:
                assert(client_credentials.secret_key == credentials_config['default']['aws_secret_access_key'])
            except AssertionError:
                raise AssertionError("the boto3 client does not have correct aws_secret_access_key")
                return False

    except FileNotFoundError as e:
        print("~/.aws/credentials isn't found! try running `aws configure` after installing `aws-cli`")
        print(e)
        return False        
    except AssertionError as e:
        print("boto3 s3 client has different configuration information from ~/.aws/credentials!")
        print(e)
        return False
    except KeyError as e:
        print("~/.aws/credentials does not have all the necessary keys")
        print(e)
        return False

    return True

def validate_client_configuration():
    try:
        with open(AWS_CONFIG_ROOT+'config', 'r') as config_file:
            client_credentials = boto3.client("s3")._client_config
            config = configparser.ConfigParser()
            config.read_file(config_file)

            # if config['default']['region'] != 'us-east-1':
            #     print("NOTE: we recommend using us-east-1 as your region", "(currently %s)" % config['default']['region'])
            #     # this is a warning, no need to return false

            try:
                assert(client_credentials.region_name == config['default']['region'])
            except AssertionError:
                raise AssertionError("the boto3 client does not have the same region as `~/.aws/config")
                return False

    except FileNotFoundError as e:
        print("~/.aws/config isn't found! try running `aws configure` after installing `aws-cli`")
        print(e)
        return False
    except AssertionError as e:
        print("boto3 s3 client has different configuration information from ~/.aws/config!")
        print(e)
        return False
    except KeyError as e:
        print("~/.aws/config does not have all the necessary keys")
        print(e)
        return False
    finally:
        return True
 

s3_client = None
try:
    assert(validate_session_configuration())
    assert(validate_client_configuration())
    s3_client = boto3.client('s3', config=Config(signature_version='s3v4'))
except Exception as e:
    print('ERROR: s3 configuration failed to load, kgea may not work properly')
    print(e)


resources = None
try: 
    with open(abspath('kgea_config.yaml'), 'r') as resource_config_file:
        resource_config = yaml.load(resource_config_file, Loader=Loader)

        try:
            resource_config['bucket']

            if s3_client is not None:
                # TODO: detect the bucket here
                # if not detected, raise an error
                pass

        except KeyError as e:
            print("The resource_config doesn't have all its necessary attributes")
            print(e)

        resources = dict(resource_config)
except Exception as e:
    print('ERROR: resource configuration file failed to load')
    print(e)
