#!/usr/bin/env python
#
# This CLI script will take  host AWS account id, guest external id and
# the name of a host account IAM role, to obtain temporary AWS service
# credentials to execute an AWS Secure Token Service-mediated access
# to a Simple Storage Service (S3) bucket given as an argument.
#
import sys
from os.path import abspath, dirname
from pathlib import Path

from json import dumps

from botocore.config import Config

from kgea.aws.assume_role import AssumeRole


def test_assumed_role_s3_access(client, bucket_name: str):
    
    TEST_FILE_PATH = abspath(dirname(__file__) + '/README.md')
    TEST_FILE_OBJECT_KEY = 'test_file.txt'
    
    # Upload a test file
    print(
        "\n###Creating a test object '"+TEST_FILE_OBJECT_KEY +
        "' in the S3 bucket '" + bucket_name + "'\n"
    )

    try:
        client.upload_file(TEST_FILE_PATH, bucket_name, TEST_FILE_OBJECT_KEY)
    except Exception as exc:
        raise RuntimeError("upload_file() exception: " + str(exc))

    # Check for the new file in the bucket listing
    response = client.list_objects_v2(Bucket=bucket_name)

    #
    # s3_client.list_objects_v2() response expected:
    
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
    # print(dumps(response))

    if 'Contents' in response:
        print("### Listing of test object in the S3 bucket '" + bucket_name + "':")
        for entry in response['Contents']:
            print(entry['Key'], ':', entry['Size'])
    else:
        print("S3 bucket '" + bucket_name + "' is empty?")

    # delete the test file
    print(
        "\n### Deleting the test object '"+TEST_FILE_OBJECT_KEY +
        "' in the S3 bucket '" + bucket_name + "'"
    )
    response = client.delete_object(Bucket=bucket_name, Key=TEST_FILE_OBJECT_KEY)
    
    print(dumps(response))


# Run the module as a CLI
if __name__ == '__main__':
    
    account_id_from_user: str = ""
    external_id: str = ""
    role_name_from_user: str = ""
    s3_bucket_name: str = ""
    s3_operation: str = "list"
    
    # Prompt user for target account ID, ExternalID and name of IAM Role
    # to assume, in order to access an S3 bucket, whose name is given
    if len(sys.argv) == 6:
        
        account_id_from_user = sys.argv[1]
        external_id = sys.argv[2]
        role_name_from_user = sys.argv[3]
        s3_bucket_name = sys.argv[4]
        # default, for now, is to simply list the bucket contents
        s3_operation = sys.argv[5]

        assumed_role = AssumeRole(
            account_id_from_user,
            external_id,
            role_name_from_user
        )
        
        s3_client = assumed_role.get_client('s3', config=Config(signature_version='s3v4'))
        
        if s3_operation.upper() == 'TEST':
            test_assumed_role_s3_access(s3_client, s3_bucket_name)
        else:
            print("\nUnknown s3_operation: '" + s3_operation + "'")
            
    else:
        print("Usage: ")
        print(
            "python -m kgea.aws."+Path(sys.argv[0]).stem +
            " <host_account_id> <guest_external_id> <target_iam_role_name>" +
            " <S3 bucket name>"  # <operation>"
        )
        print("At this moment,  'list bucket contents' is the " +
              "only currently supported operation for S3 access.")
        exit(0)
