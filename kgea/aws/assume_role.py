#!/usr/bin/env python
from typing import Dict, Tuple, Optional
# from os import getenv
from os.path import expanduser

from datetime import datetime

from json import dumps
# import configparser

import boto3
from botocore.config import Config

from kgea.config import get_app_config
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Opaquely access the configuration dictionary
_KGEA_APP_CONFIG: Dict = get_app_config()
aws_config: Dict = _KGEA_APP_CONFIG['aws']

home = expanduser("~")
AWS_CONFIG_ROOT = home + "/.aws/"


class AssumeRole:
    """
    AWS IAM 'AssumeRole' wrapper
    """
    def __init__(
            self,
            host_account=aws_config['host_account'],
            guest_external_id=aws_config['guest_external_id'],
            iam_role_name=aws_config['iam_role_name']
    ):
        if not iam_role_name:
            logger.info("AssumeRole(): assume default credentials")
            self._default_credentials = True
        else:
            logger.info("AssumeRole() using assumed role credentials")
            self._default_credentials = False
            self.host_account = host_account
            self.guest_external_id = guest_external_id
            self.iam_role_name = iam_role_name

            # Create an ARN out of the information provided by the user.
            self.role_arn = "arn:aws:iam::" + self.host_account + ":role/"
            self.role_arn += self.iam_role_name

            self.assumed_role_object = None
            self.credentials_dict: Dict = dict()
            self.expiration = datetime.now()
            self.aws_session: Optional[boto3.Session] = None

        # Connect to AWS STS ... using local guest credentials
        self.sts_client = None
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
        if self._default_credentials:
            credentials = boto3.Session().get_credentials().get_frozen_credentials()
            return dumps({
                    "sessionId": credentials['aws_access_key_id'],
                    "sessionKey": credentials['aws_secret_access_key'],
                    "sessionToken": credentials['aws_session_token']
                 })
        else:
            # We don't care here if the Credentials
            # were renewed... we just pass 'em along
            credentials, _ = self.get_credentials_dict()
            return dumps(credentials)

    def get_client(self, service: str, config: Optional[Config] = None):
        """

        :param service:
        :param config:
        :return:
        """
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
        if self._default_credentials:
            logging.debug("AssumeRole.get_client(): using default credentials")
            return boto3.client(service, config=config)
        else:
            credentials, session_renewed = self.get_credentials_dict()

            if not self.aws_session or session_renewed:

                self.aws_session = boto3.Session(
                    aws_access_key_id=credentials["sessionId"],
                    aws_secret_access_key=credentials["sessionKey"],
                    aws_session_token=credentials["sessionToken"]
                )

            return self.aws_session.client(service, config=config)

    def get_resource(self, service, **kwargs):
        """

        :param service:
        :param kwargs:
        :return:
        """
        if self._default_credentials:
            return boto3.resource('s3', **kwargs)
        else:
            credentials, session_renewed = self.get_credentials_dict()

            if not self.aws_session or session_renewed:
                self.aws_session = boto3.Session(
                    aws_access_key_id=credentials["sessionId"],
                    aws_secret_access_key=credentials["sessionKey"],
                    aws_session_token=credentials["sessionToken"]
                )
            return self.aws_session.resource(service_name=service, **kwargs)
