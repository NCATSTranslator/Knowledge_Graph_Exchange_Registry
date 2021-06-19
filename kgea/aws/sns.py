#!/usr/bin/env python
#
# This CLI script will take  host AWS account id, guest external id and
# the name of a host account IAM role, to obtain temporary AWS service
# credentials to execute an AWS Secure Token Service-mediated access
# to a Simple Notification Service (SNS).
#
import sys
from os.path import abspath, dirname
from pathlib import Path

from json import dumps

import boto3

from kgea.aws.assume_role import AssumeRole


account_id_from_user: str = ""
external_id: str = ""
role_name_from_user: str = ""


# Prompt user for target account ID, ExternalID and name of IAM Role
# to assume, in order to configure and access an SNS service
if len(sys.argv) == 4:
    account_id_from_user = sys.argv[1]
    external_id = sys.argv[2]
    role_name_from_user = sys.argv[3]

else:
    print("Usage: ")
    print(
        "python -m kgea.aws."+Path(sys.argv[0]).stem +
        " <host_account_id> <guest_external_id> <target_iam_role_name>"
    )
    exit(0)


_assumed_role = AssumeRole(
                    host_aws_account_id=account_id_from_user,
                    guest_external_id=external_id,
                    target_role_name=role_name_from_user
                )
#
# Get the temporary credentials, in a Python dictionary
# with temporary AWS credentials of the form:
#
# {
#     "sessionId": "temp-access_key-id",
#     "sessionKey": "temp-secret-access-key",
#     "sessionToken": "temp-session-token"
# }#
credentials = _assumed_role.get_credentials_dict()

aws_session = boto3.Session(
    aws_access_key_id=credentials["sessionId"],
    aws_secret_access_key=credentials["sessionKey"],
    aws_session_token=credentials["sessionToken"]
)

s3_client = aws_session.client('sns')  # , region_name=region)

# TODO: need to define SNS actions here
