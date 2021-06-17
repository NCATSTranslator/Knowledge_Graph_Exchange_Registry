#!/usr/bin/env python
from typing import Dict

from json import dumps
import boto3

from kgea.config import get_app_config
from kgea.config.aws import (
    validate_session_configuration,
    validate_client_configuration
)

# Opaquely access the configuration dictionary
_KGEA_APP_CONFIG = get_app_config()


class AssumeRole:
    def __init__(
            self,
            host_aws_account_id,
            guest_external_id,
            target_role_name
    ):
        self.account_id = host_aws_account_id
        self.external_id = guest_external_id
        self.role_name = target_role_name
    
        # Create an ARN out of the information provided by the user.
        self.role_arn = "arn:aws:iam::" + self.account_id + ":role/"
        self.role_arn += self.role_name

        # Connect to AWS STS ...
        self.sts_client = None
        try:
            assert (validate_session_configuration())
            assert (validate_client_configuration("sts"))
            self.sts_client = boto3.client('sts')
        except Exception as e:
            print('ERROR: sts configuration failed to load')
            print(e)
    
    def get_credentials_dict(self) -> Dict:
        """
        :return: Python dictionary with temporary AWS credentials of the form
                 {
                    "sessionId": "temp-access_key",
                    "sessionKey": "temp-session-key",
                    "sessionToken": "temp-session-token"
                 }
        """
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
        assumed_role_object = \
            self.sts_client.assume_role(
                RoleArn=self.role_arn,
                RoleSessionName="AssumeRoleSession",
                ExternalId=self.external_id
            )

        # Format resulting temporary credentials into
        # a Python dictionary using known field names
        credentials = assumed_role_object["Credentials"]
        credentials_dict: Dict = {
            "sessionId": credentials["AccessKeyId"],
            "sessionKey": credentials["SecretAccessKey"],
            "sessionToken": credentials["SessionToken"]
        }
        
        return credentials_dict
    
    def get_credentials_jsons(self) -> str:
        """
        :return: JSON formatted string of temporary AWS credentials of form
                 {
                    "sessionId": "temp-access_key",
                    "sessionKey": "temp-session-key",
                    "sessionToken": "temp-session-token"
                 }
        """
        return dumps(self.get_credentials_dict())
