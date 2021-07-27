#!/usr/bin/env python
#
# This CLI script will take  host AWS account id, guest external id and
# the name of a host account IAM role, to obtain temporary AWS service
# credentials to execute an AWS Secure Token Service-mediated access
# to the AWS Cognito (OAuth2) management service.
#
import sys
from os.path import abspath, dirname
from pathlib import Path

from json import dumps

import boto3

from kgea.aws.assume_role import AssumeRole


def usage(err_msg: str = ''):
    if err_msg:
        print(err_msg)
    print("Usage: ")
    print(
        "python -m kgea.aws." + Path(sys.argv[0]).stem +
        " <host_account_id> <guest_external_id> <target_iam_role_name>"
    )
    exit(0)


# Run the module as a CLI
if __name__ == '__main__':

    assumed_role = AssumeRole( )

    sns_client = assumed_role.get_client('cognito')

    # TODO: Cognito specific actions here
