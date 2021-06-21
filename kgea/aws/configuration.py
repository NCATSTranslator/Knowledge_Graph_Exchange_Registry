from os.path import expanduser

import configparser
import boto3

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
    
    except FileNotFoundError as f_n_f_e:
        print("ERROR: ~/.aws/credentials isn't found! try running `aws configure` after installing `aws-cli`")
        print(f_n_f_e)
        return False
    except AssertionError as a_e:
        print("ERROR: boto3 s3 client has different configuration information from ~/.aws/credentials!")
        print(a_e)
        return False
    except KeyError as k_e:
        print("ERROR: ~/.aws/credentials does not have all the necessary keys")
        print(k_e)
        return False
    
    return True


def validate_client_configuration(service_name: str):
    try:
        with open(AWS_CONFIG_ROOT + 'config', 'r') as config_file:
            
            client_credentials = boto3.client(service_name).config()
            config = configparser.ConfigParser()
            config.read_file(config_file)
            
            # if config['default']['region'] != 'us-east-1':
            #     print("NOTE: we recommend using us-east-1 as your region",
            #           "(currently %s)" % config['default']['region'])
            #     # this is a warning, no need to return false
            
            try:
                assert (client_credentials.region_name == config['default']['region'])
            except AssertionError:
                raise AssertionError("the boto3 client does not have the same region as `~/.aws/config")
    
    except FileNotFoundError as f_n_f_e:
        print("ERROR: ~/.aws/config isn't found! try running `aws configure` after installing `aws-cli`")
        print(f_n_f_e)
        return False
    except AssertionError as a_e:
        print("ERROR: boto3 s3 client has different configuration information from ~/.aws/config!")
        print(a_e)
        return False
    except KeyError as k_e:
        print("ERROR: ~/.aws/config does not have all the necessary keys")
        print(k_e)
        return False
    finally:
        return True
