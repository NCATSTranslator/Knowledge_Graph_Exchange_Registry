#!/usr/bin/env python
#
# This CLI script will take  host AWS account id, guest external id and
# the name of a host account IAM role, to obtain temporary AWS service
# credentials to execute an AWS Secure Token Service-mediated access
# to the AWS Cognito (OAuth2) management service.
#
from sys import argv
from typing import Dict, List
from pprint import PrettyPrinter

from configparser import ConfigParser

from boto3.exceptions import Boto3Error

from kgea.aws import Help
from kgea.aws.assume_role import AssumeRole, aws_config

import logging
logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")

pp = PrettyPrinter(indent=4)

# Cognito CLI commands
CREATE_USER = "create-user"
GET_USER_DETAILS = "get-user-details"
SET_USER_ATTRIBUTE = "set-user-attribute"  # including disabling
DELETE_USER = "delete-user"

help_doc = Help(
    default_usage="where <operation> is one of " +
                  f"'{CREATE_USER}', '{GET_USER_DETAILS}', '{SET_USER_ATTRIBUTE}' or '{DELETE_USER}'\n"
)

# Hack around peculiar case sensitivity
# TODO: Should perhaps convert Translator User Pool custom attributes to all lower case
_CUSTOM_ATTRIBUTE_MAP = {
    "custom_team": "custom:Team",
    "custom_affiliation": "custom:Affiliation",
    "custom_contact_pi": "custom:Contact_PI",
    "custom_user_role": "custom:User_Role",
}


def read_user_attributes(filename: str, section: str = 'DEFAULT') -> Dict:
    """
    Read in user attributes (in an MS Windows-style configuration file).

    Parameters
    ----------
    filename: str
        (Path) name of file.
    section: str
        Section in the configuration file (generally, the username)

    Returns
    -------
    Dict
        A dictionary of user attributes belonging to the section.
    """
    ua: Dict = dict()
    try:
        config = ConfigParser()
        config.read(filename)
        sections = "\n".join(config.sections())
        logger.debug(f"read_user_attributes(): Sections: {sections}")
    except (FileNotFoundError,):
        config = dict()
        logger.warning(f"cognito.read_user_attributes(): file '{filename}' not found?")
    if section in config:
        for k, v in config[section].items():
            # patch custom attribute keys
            if k.startswith("custom_"):
                if k not in _CUSTOM_ATTRIBUTE_MAP:
                    continue
                k = _CUSTOM_ATTRIBUTE_MAP.get(k)
            ua[k] = v
    return ua


def create_user(
    client,
    upi: str,
    uid: str,
    tpw: str,
    attributes: Dict[str, str]
):
    """
    Create user with given user name, temporary password and attributes
    :param client:
    :param upi:
    :param uid:
    :param tpw: temporary password, 15 characters, with at least one upper, lower, number and symbol
    :param attributes: Dict
    """
    user_attributes: List[Dict[str, str]] = list()
    for n, v in attributes.items():
        user_attributes.append(
            {
                "Name": n,
                "Value": v
            }
        )

    try:
        kwargs: Dict = {
            "UserPoolId": upi,
            "Username": uid,
            "UserAttributes": user_attributes,
            "MessageAction": 'SUPPRESS',
            "DesiredDeliveryMediums": ['EMAIL']
        }
        if tpw:
            kwargs["TemporaryPassword"] = tpw
        response = client.admin_create_user(**kwargs)
        logger.debug(f"create_user() response:\n{pp.pformat(response)}")

    except Boto3Error as b3e:
        logger.error(f"create_user() exception: {b3e}")


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
        logger.debug(f"get_user_details() response:\n{pp.pformat(response)}")

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
        logger.info(f"update_user_attributes() response:\n{pp.pformat(response)}")

    except Boto3Error as b3e:
        logger.error(f"update_user_attributes() exception: {b3e}")


def delete_user(
    client,
    upi: str,
    uid: str
):
    """
    Delete the user with  the given username ('uid')
    :param client: Cognito IDP client handle
    :param upi: user pool within which the user exists
    :param uid: username to delete
    """
    try:
        response = client.admin_delete_user(
            UserPoolId=upi,
            Username=uid
        )
        logger.debug(f"delete_user() response:\n{pp.pformat(response)}")

    except Boto3Error as b3e:
        logger.error(f"delete_user() exception: {b3e}")


if __name__ == '__main__':

    if len(argv) > 1:

        user_pool_id: str = aws_config["cognito"]["user-pool-id"]

        operation = argv[1]

        assumed_role = AssumeRole()

        cognito_client = assumed_role.get_client('cognito-idp')

        if operation.lower() == CREATE_USER:

            if len(argv) > 3:

                username = argv[2]

                ua_file = argv[3]

                attributes: Dict = read_user_attributes(filename=ua_file, section=username)

                if 'temporary_password' in attributes:
                    temporary_password = attributes.pop('temporary_password')
                else:
                    temporary_password = None  # empty - let Cognito set?

                create_user(
                    cognito_client,
                    upi=user_pool_id,
                    uid=username,
                    tpw=temporary_password,
                    attributes=attributes
                )
            else:
                help_doc.usage(
                    err_msg=f"{CREATE_USER} needs more parameters!",
                    command=CREATE_USER,
                    args={
                        "<username>": 'user account',
                        "<filename>": 'name of the user attribute properties file',
                    }
                )
        elif operation.lower() == GET_USER_DETAILS:

            if len(argv) >= 3:

                username = argv[2]

                get_user_details(
                    cognito_client,
                    upi=user_pool_id,
                    uid=username
                )
            else:
                help_doc.usage(
                    err_msg=f"{GET_USER_DETAILS} needs the target username",
                    command=GET_USER_DETAILS,
                    args={
                        "<username>": 'user account'
                    }
                )
        elif operation.lower() == SET_USER_ATTRIBUTE:

            if len(argv) >= 5:

                username = argv[2]
                name = argv[3]
                value = argv[4]

                attributes = {name: value}

                update_user_attributes(
                    cognito_client,
                    upi=user_pool_id,
                    uid=username,
                    attributes=attributes
                )
            else:
                help_doc.usage(
                    err_msg=f"{SET_USER_ATTRIBUTE} needs more arguments",
                    command=SET_USER_ATTRIBUTE,
                    args={
                        "<username>": 'user account',
                        "<name>": "attribute 'name'",
                        "<value>": "attribute 'value'"
                    }
                )
        elif operation.lower() == DELETE_USER:

            if len(argv) > 2:

                username = argv[2]
                prompt = input(
                    f"\nWarning: deleting user name '{username}' " +
                    f"in user pool '{user_pool_id}'? (Type 'delete' again to proceed) "
                )
                if prompt.upper() == "DELETE":
                    delete_user(
                        client=cognito_client,
                        upi=user_pool_id,
                        uid=username
                    )
                    print(f"\nUser '{username}' successfully deleted!\n")
                else:
                    print("\nCancelling deletion of user...\n")
            else:
                help_doc.usage(
                    err_msg=f"{DELETE_USER} needs more arguments",
                    command=DELETE_USER,
                    args={
                        "<username>": 'user account'
                    }
                )
        # elif operation.upper() == 'OTHER':
        #     pass
        else:
            help_doc.usage("\nUnknown Operation: '" + operation + "'")
    else:
        help_doc.usage()
