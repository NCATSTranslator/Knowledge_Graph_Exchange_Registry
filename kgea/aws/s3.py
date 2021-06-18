#!/usr/bin/env python
#
# This CLI script will take  host AWS account id, guest external id and
# the name of a host account IAM role, to obtain temporary AWS service
# credentials to execute an AWS Secure Token Service-mediated access
# to a Simple Storage Service (S3) bucket given as an argument.
#
import sys
from pathlib import Path

from json import dumps

import boto3

from kgea.aws.assume_role import AssumeRole



account_id_from_user: str = ""
external_id: str = ""
role_name_from_user: str = ""
s3_bucket_name: str = ""
s3_operation: str = "list"

# Prompt user for target account ID, ExternalID and name of IAM Role
# to assume, in order to access an S3 bucket, whose name is given
if len(sys.argv) == 5: # 6:
    account_id_from_user = sys.argv[1]
    external_id = sys.argv[2]
    role_name_from_user = sys.argv[3]
    s3_bucket_name = sys.argv[4]
    # default, for now, is to simply list the bucket contents
    # s3_operation = sys.argv[5]
else:
    print("Usage: ")
    print(
        "python -m kgea.aws."+Path(sys.argv[0]).stem +
        " <host_account_id> <guest_external_id> <target_iam_role_name>"
        " <S3 bucket name>"  # <operation>"
    )
    print("At this moment,  'list bucket contents' is the " +
          "only currently supported operation for S3 access.")
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

s3_client = aws_session.client('s3')  # , region_name=region)

# response expected:
# {
#     'IsTruncated': True|False,
#     'Contents': [
#         {
#             'Key': 'string',
#             'LastModified': datetime(2015, 1, 1),
#             'ETag': 'string',
#             'Size': 123,
#             'StorageClass': 'STANDARD'|'REDUCED_REDUNDANCY'|'GLACIER'|'STANDARD_IA'|'ONEZONE_IA'|'INTELLIGENT_TIERING'|'DEEP_ARCHIVE'|'OUTPOSTS',
#             'Owner': {
#                 'DisplayName': 'string',
#                 'ID': 'string'
#             }
#         },
#     ],
#     'Name': 'string',
#     'Prefix': 'string',
#     'Delimiter': 'string',
#     'MaxKeys': 123,
#     'CommonPrefixes': [
#         {
#             'Prefix': 'string'
#         },
#     ],
#     'EncodingType': 'url',
#     'KeyCount': 123,
#     'ContinuationToken': 'string',
#     'NextContinuationToken': 'string',
#     'StartAfter': 'string'
# }

response = s3_client.list_objects_v2(Bucket=s3_bucket_name)

# print(dumps(response))

if 'KeyCount' in response and response['KeyCount']:
    print("Listing of contents of the S3 bucket '" + s3_bucket_name + "':")
    for entry in response['Contents']:
        print(entry['Key'], ':', entry['Size'])
else:
    print("S3 bucket '" + s3_bucket_name + "' is empty?")

