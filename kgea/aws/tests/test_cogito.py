from os.path import join

from kgea.aws.tests import DATA_DIR
from kgea.aws.assume_role import AssumeRole, aws_config
from kgea.aws.cognito import read_user_attributes, create_user, delete_user


TEST_USER_NAME = "cognito-test-user"
TEST_TEMP_PASSWORD = "KGE@_Te5t_U$er#1"
TEST_USER_ATTRIBUTES = {
    "email": "richard.bruskiewich@cropinformatics.com",
    "family_name": "Lator",
    "given_name": "Trans",
    "email_verified": "true",
    "website": "https://ncats.nih.gov",
    "custom:Team": "SRI",
    "custom:Affiliation": "NCATS",
    "custom:Contact_PI": "da Boss",
    "custom:User_Role": "2"  # give this bloke editorial privileges
}

UA_TEST_FILE = join(DATA_DIR, "test-ua.ini")


def test_read_user_attributes():
    uaa = read_user_attributes(filename=UA_TEST_FILE, section=TEST_USER_NAME)
    assert "given_name" in uaa
    assert uaa["given_name"] == "Trans"
    assert "custom:User_Role" in uaa


def test_create_user():
    upi: str = aws_config["cognito"]["user-pool-id"]
    role = AssumeRole()
    client = role.get_client('cognito-idp')
    create_user(
        client=client,
        upi=upi,
        uid=TEST_USER_NAME,
        tpw=TEST_TEMP_PASSWORD,
        attributes=TEST_USER_ATTRIBUTES
    )


def test_delete_user():
    upi: str = aws_config["cognito"]["user-pool-id"]
    role = AssumeRole()
    client = role.get_client('cognito-idp')
    delete_user(
        client=client,
        upi=upi,
        uid=TEST_USER_NAME
    )
