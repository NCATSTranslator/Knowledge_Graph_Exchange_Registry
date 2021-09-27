#!/usr/bin/env python
#
# This CLI script will take  host AWS account id, guest external id and
# the name of a host account IAM role, to obtain temporary AWS service
# credentials to execute an AWS Secure Token Service-mediated access
# to the AWS Cognito (OAuth2) management service.
#
import sys
from pathlib import Path
from typing import Dict, Optional
from pprint import PrettyPrinter
import logging

from boto3.exceptions import Boto3Error

from kgea.aws.assume_role import AssumeRole, aws_config

logger = logging.getLogger(__name__)
pp = PrettyPrinter(indent=4)


# Cognito CLI commands
GET_USER_DETAILS = "get-user-details"
SET_USER_ATTRIBUTE = "set-user-attribute"


def usage(
        err_msg: str = '',
        command: str = '',
        args:  Optional[Dict] = None
):
    if err_msg:
        print(err_msg)

    if not command:
        cmd = " <operation>"
        description = f"where <operation> is one of '{GET_USER_DETAILS}' or '{SET_USER_ATTRIBUTE}'\n"
    else:
        cmd = f" {command}"
        description = ''
        for arg, desc in args.items():
            cmd += f" {arg}"
            description += f"\t{arg} is the {desc}\n"
    print(
        f"Usage:\n\npython -m kgea.aws.{Path(sys.argv[0]).stem}{cmd}\n\n" +
        "where:\n" +
        f"{description}\n"

    )
    exit(0)


def get_user_details(
        client,
        upi: str,
        uid: str
):
    """

    :param client:
    :param upi:
    :param uid:
    """
    try:
        response = client.admin_get_user(
            UserPoolId=upi,
            Username=uid
        )
        logger.info(f"get_user_details() response:\n{pp.pprint(response)}")

    except Boto3Error as b3e:
        logger.error(f"get_user_details() exception: {b3e}")


def update_user_attributes(
        client,
        upi: str,
        uid: str,
        attributes: Dict
):
    """

    :param client:
    :param upi:
    :param uid:
    :param attributes:
    """
    try:
        response = client.admin_update_user_attributes(
            UserPoolId=upi,
            Username=uid,
            UserAttributes=[
                {'Name': key, 'Value': value}
                for key, value in attributes.items()
            ],
        )
        logger.info(f"update_user_attributes() response:\n{pp.pprint(response)}")

    except Boto3Error as b3e:
        logger.error(f"update_user_attributes() exception: {b3e}")


# Run the module as a CLI
if __name__ == '__main__':

    if len(sys.argv) > 1:

        user_pool_id: str = aws_config["cognito"]["user-pool-id"]

        operation = sys.argv[1]

        assumed_role = AssumeRole()

        cognito_client = assumed_role.get_client('cognito-idp')

        if operation.lower() == GET_USER_DETAILS:
            if len(sys.argv) >= 3:

                username = sys.argv[2]

                get_user_details(
                    cognito_client,
                    upi=user_pool_id,
                    uid=username
                )
            else:
                usage(
                    err_msg="get-user-details needs the target username",
                    command=GET_USER_DETAILS,
                    args={
                        "<username>": 'user account'
                    }
                )
        elif operation.lower() == SET_USER_ATTRIBUTE:
            if len(sys.argv) >= 5:
                username = sys.argv[2]
                name = sys.argv[3]
                value = sys.argv[4]

                user_attributes = {name: value}

                update_user_attributes(
                    cognito_client,
                    upi=user_pool_id,
                    uid=username,
                    attributes=user_attributes
                )
            else:
                usage(
                    err_msg="set-user-attribute needs more arguments",
                    command=SET_USER_ATTRIBUTE,
                    args={
                        "<username>": 'user account',
                        "<name>": "attribute 'name'",
                        "<value>": "attribute 'value'"
                    }
                )
        # elif operation.upper() == 'OTHER':
        #     pass
        else:
            usage("\nUnknown Operation: '" + operation + "'")
    else:
        usage()
