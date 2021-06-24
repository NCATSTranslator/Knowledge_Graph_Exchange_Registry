#!/usr/bin/env python
from typing import Dict, Tuple, Optional
# from os import getenv
from os.path import expanduser

from datetime import datetime

from json import dumps
# import configparser

import boto3
from botocore.config import Config

home = expanduser("~")
AWS_CONFIG_ROOT = home + "/.aws/"

# We fall back here on Environment Variables as the
# default source of AWS credentials and configuration
# AWS_ACCESS_KEY_ID = getenv('AWS_ACCESS_KEY_ID')
# AWS_SECRET_ACCESS_KEY = getenv('AWS_SECRET_ACCESS_KEY')
# REGION_NAME = getenv('REGION_NAME')
# boto3.setup_default_session(
#     aws_access_key_id=AWS_ACCESS_KEY_ID,
#     aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
#     aws_session_token=None,
#     region_name=REGION_NAME,
#     botocore_session=None,
#     profile_name=None
# )


# def validate_session_configuration():
#     try:
#         with open(AWS_CONFIG_ROOT + 'credentials', 'r') as credentials_file:
#
#             client_credentials = boto3.Session().get_credentials().get_frozen_credentials()
#             credentials_config = configparser.ConfigParser()
#             credentials_config.read_file(credentials_file)
#
#             try:
#                 assert (client_credentials.access_key == credentials_config['default']['aws_access_key_id'])
#             except AssertionError:
#                 raise AssertionError("the boto3 client does not have correct aws_access_key_id")
#
#             try:
#                 assert (client_credentials.secret_key == credentials_config['default']['aws_secret_access_key'])
#             except AssertionError:
#                 raise AssertionError("the boto3 client does not have correct aws_secret_access_key")
#
#     except FileNotFoundError as f_n_f_e:
#         print("ERROR: ~/.aws/credentials isn't found! try running `aws configure` after installing `aws-cli`")
#         print(f_n_f_e)
#         return False
#     except AssertionError as a_e:
#         print("ERROR: boto3 s3 client has different configuration information from ~/.aws/credentials!")
#         print(a_e)
#         return False
#     except KeyError as k_e:
#         print("ERROR: ~/.aws/credentials does not have all the necessary keys")
#         print(k_e)
#         return False
#
#     return True
#
#
# def validate_client_configuration(service_name: str):
#     try:
#         with open(AWS_CONFIG_ROOT + 'config', 'r') as config_file:
#
#             client_credentials = boto3.client(service_name).config()
#             config = configparser.ConfigParser()
#             config.read_file(config_file)
#
#             # if config['default']['region'] != 'us-east-1':
#             #     print("NOTE: we recommend using us-east-1 as your region",
#             #           "(currently %s)" % config['default']['region'])
#             #     # this is a warning, no need to return false
#
#             try:
#                 assert (client_credentials.region_name == config['default']['region'])
#             except AssertionError:
#                 raise AssertionError("the boto3 client does not have the same region as `~/.aws/config")
#
#     except FileNotFoundError as f_n_f_e:
#         print("ERROR: ~/.aws/config isn't found! try running `aws configure` after installing `aws-cli`")
#         print(f_n_f_e)
#         return False
#     except AssertionError as a_e:
#         print("ERROR: boto3 s3 client has different configuration information from ~/.aws/config!")
#         print(a_e)
#         return False
#     except KeyError as k_e:
#         print("ERROR: ~/.aws/config does not have all the necessary keys")
#         print(k_e)
#         return False
#     finally:
#         return True
#

class AssumeRole:
    def __init__(
            self,
            host_account,
            guest_external_id,
            iam_role_name
    ):
        self.host_account = host_account
        self.guest_external_id = guest_external_id
        self.iam_role_name = iam_role_name
    
        # Create an ARN out of the information provided by the user.
        self.role_arn = "arn:aws:iam::" + self.host_account + ":role/"
        self.role_arn += self.iam_role_name

        # Connect to AWS STS ... using local guest credentials
        self.sts_client = None
        self.assumed_role_object = None
        self.credentials_dict: Dict = dict()
        self.expiration = datetime.now()
        self.aws_session: Optional[boto3.Session] = None
        
        try:
            # assert (validate_session_configuration())
            # assert (validate_client_configuration("sts"))
            self.sts_client = boto3.client("sts")
        except Exception as ex:
            print('ERROR: AWS STS configuration failed to load')
            print(ex)
    
    def get_credentials_dict(self) -> Tuple[Dict, bool]:
        """
        :return: 2-Tuple consisting first, of a  Python dictionary,
                 with temporary AWS credentials, of the form
                 {
                    "sessionId": "temp-access_key",
                    "sessionKey": "temp-session-key",
                    "sessionToken": "temp-session-token"
                 }
                 and second, a boolean flag which is True
                 if the session credentials were renewed.
        """
        session_renewed: bool = False
        
        if not self.assumed_role_object or \
                self.expiration.timestamp() <= datetime.now().timestamp():
            
            session_renewed = True

            # Full STS "Assume Role" method signature, returns temporary security credentials.
            # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sts.html#STS.Client.assume_role
            #
            # response = client.assume_role(
            #     RoleArn='string',
            #     RoleSessionName='string',
            #     PolicyArns=[
            #         {
            #             'arn': 'string'
            #         },
            #     ],
            #     Policy='string',
            #     DurationSeconds=123,
            #     Tags=[
            #         {
            #             'Key': 'string',
            #             'Value': 'string'
            #         },
            #     ],
            #     TransitiveTagKeys=[
            #         'string',
            #     ],
            #     ExternalId='string',
            #     SerialNumber='string',
            #     TokenCode='string',
            #     SourceIdentity='string'
            # )
            #
            # Response Syntax
            #
            # {
            #     'Credentials': {
            #         'AccessKeyId': 'string',
            #         'SecretAccessKey': 'string',
            #         'SessionToken': 'string',
            #         'Expiration': datetime(2015, 1, 1)
            #     },
            #     'AssumedRoleUser': {
            #         'AssumedRoleId': 'string',
            #         'Arn': 'string'
            #     },
            #     'PackedPolicySize': 123,
            #     'SourceIdentity': 'string'
            # }
            self.assumed_role_object = \
                self.sts_client.assume_role(
                    RoleArn=self.role_arn,
                    RoleSessionName="AssumeRoleSession",
                    ExternalId=self.guest_external_id
                )

            # Format resulting temporary credentials into
            # a Python dictionary using known field names
            credentials = self.assumed_role_object["Credentials"]
            self.credentials_dict = {
                "sessionId": credentials["AccessKeyId"],
                "sessionKey": credentials["SecretAccessKey"],
                "sessionToken": credentials["SessionToken"],
            }
            self.expiration = credentials["Expiration"]
        
        return self.credentials_dict, session_renewed
    
    def get_credentials_jsons(self) -> str:
        """
        :return: JSON formatted string of temporary AWS credentials of form
                 {
                    "sessionId": "temp-access_key-id",
                    "sessionKey": "temp-secret-access-key",
                    "sessionToken": "temp-session-token"
                 }
        """
        # We don't care here if the Credentials
        # were renewed... we just pass 'em along
        credentials, _ = self.get_credentials_dict()
        return dumps(credentials)

    def get_client(self, service: str, config: Optional[Config] = None):
        #
        # Get the temporary credentials, in a Python dictionary
        # with temporary AWS credentials of the form:
        #
        # {
        #     "sessionId": "temp-access_key-id",
        #     "sessionKey": "temp-secret-access-key",
        #     "sessionToken": "temp-session-token"
        # }
        #
        credentials, session_renewed = self.get_credentials_dict()
        
        if not self.aws_session or session_renewed:
            
            self.aws_session = boto3.Session(
                aws_access_key_id=credentials["sessionId"],
                aws_secret_access_key=credentials["sessionKey"],
                aws_session_token=credentials["sessionToken"]
            )
        
        return self.aws_session.client(service, config=config)
