#!/usr/bin/env python
"""
This CLI script will take  host AWS account id, guest external id and
the name of a host account IAM role, to obtain temporary AWS service
credentials to execute an AWS Secure Token Service-mediated access
to a Simple Storage Service (S3) bucket given as an argument.
"""
import sys
from json import dumps
from os.path import abspath, dirname
from pathlib import Path

from typing import List

from botocore.config import Config

from kgea.aws.assume_role import AssumeRole, aws_config


def upload_file(client, bucket_name: str, filepath: str, object_key: str):
    """
    Upload a test file.
    
    :param client:
    :param bucket_name:
    :param filepath:
    :param object_key:
    :return:
    """
    print(
        "\n###Uploading file '" + filepath + "' object '" + object_key +
        "' in the S3 bucket '" + bucket_name + "'\n"
    )
    
    try:
        client.upload_file(filepath, bucket_name, object_key)
    except Exception as exc:
        raise RuntimeError("upload_file() exception: " + str(exc))


def get_object_keys(client, bucket_name: str, filter_prefix='') -> List[str]:
    """
    Check for the new file in the bucket listing.
    :param client:
    :param bucket_name:
    :param filter_prefix:
    :return:
    """
    response = client.list_objects_v2(Bucket=bucket_name, Prefix=filter_prefix)

    if 'Contents' in response:
        print("### Returning list of keys with prefix '" + filter_prefix +
              "'from the S3 bucket '" + bucket_name + "'")
        return [item['Key'] for item in response['Contents']]
    else:
        print("S3 bucket '" + bucket_name + "' is empty?")
        return []


def list_files(client, bucket_name: str):
    """
    Check for the new file in the bucket listing.
    :param client:
    :param bucket_name:
    :return:
    """
    response = client.list_objects_v2(Bucket=bucket_name)
    
    if 'Contents' in response:
        print("### Listing contents of the S3 bucket '" + bucket_name + "':")
        for entry in response['Contents']:
            print(entry['Key'], ':', entry['Size'])
    else:
        print("S3 bucket '" + bucket_name + "' is empty?")


def download_file(client, bucket_name, object_key: str, filename: str = ''):
    """
    Delete an object key (file) in a given bucket.

    :param client: S3 client to access S3 bucket
    :param bucket_name: the target bucket
    :param object_key: the target object_key
    :param filename: filename to which to save the file
    :return:
    """
    print(
        "\n### Downloading the test object '" + object_key +
        "' from the S3 bucket '" + bucket_name + "' to file " + str(filename)
    )
    with open(filename, 'wb') as fd:
        client.download_fileobj(Bucket=bucket_name, Key=object_key, Fileobj=fd)


def delete_object(client, bucket_name, object_key: str):
    """
    Delete an object key (file) in a given bucket.
    
    :param client:
    :param bucket_name:
    :param object_key:
    :return:
    """
    # print(
    #     "\n### Deleting the test object '" + object_key +
    #     "' in the S3 bucket '" + bucket_name + "'"
    # )
    response = client.delete_object(Bucket=bucket_name, Key=object_key)
    # print(dumps(response))


def test_assumed_role_s3_access(client, bucket_name: str):
    """
    Test for assumed role s3 access on a given bucket.
    
    :param client:
    :param bucket_name:
    :return:
    """
    TEST_FILE_PATH = abspath(dirname(__file__) + '/README.md')
    TEST_FILE_OBJECT_KEY = 'test_file.txt'
    
    upload_file(client, bucket_name, TEST_FILE_PATH, TEST_FILE_OBJECT_KEY)

    list_files(client, bucket_name)

    delete_object(client, bucket_name, TEST_FILE_OBJECT_KEY)


# Run the module as a CLI
if __name__ == '__main__':

    s3_bucket_name: str = aws_config["s3"]["bucket"]
    s3_region_name: str = aws_config["s3"]["region"]
    s3_operation: str = ''
    
    # Prompt user for target account ID, ExternalID and name of IAM Role
    # to assume, in order to access an S3 bucket, whose name is given
    if len(sys.argv) > 1:
        # default, for now, is to simply list the bucket contents
        s3_operation = sys.argv[1]

        assumed_role = AssumeRole()
        
        s3_client = \
            assumed_role.get_client(
                        's3',
                        config=Config(
                            signature_version='s3v4',
                            region_name=s3_region_name
                        )
            )
        
        if s3_operation.upper() == 'HELP':
            print()

        elif s3_operation.upper() == 'TEST':
    
            test_assumed_role_s3_access(s3_client, s3_bucket_name)
    
        elif s3_operation.upper() == 'UPLOAD':
            if len(sys.argv) >= 3:
                filepath = sys.argv[2]
                object_key = sys.argv[3] if len(sys.argv) >= 4 else filepath
                upload_file(s3_client, s3_bucket_name, filepath, object_key)
            else:
                print("\nMissing path to file to upload?")

        elif s3_operation.upper() == 'LIST':
            list_files(s3_client, s3_bucket_name)

        elif s3_operation.upper() == 'DOWNLOAD':
            if len(sys.argv) >= 3:
                object_key = sys.argv[2]
                filename = sys.argv[3] if len(sys.argv) >= 4 else object_key.split("/")[-1]
                download_file(s3_client, s3_bucket_name, object_key, filename)
            else:
                print("\nMissing S3 object key for file to download?")
        
        elif s3_operation.upper() == 'DELETE':
            if len(sys.argv) >= 3:
                object_keys = sys.argv[2:]
                for key in object_keys:
                    print("\t" + key)
                prompt = input("Proceed (Type 'yes')? ")
                if prompt.upper() == "YES":
                    for key in object_keys:
                        delete_object(s3_client, s3_bucket_name, key)
                else:
                    print("Cancelling deletion of objects...")
            else:
                print("\nMissing S3 key(s) of object(s) to delete?")

        elif s3_operation.upper() == 'DELETE-BATCH':
            if len(sys.argv) >= 3:
                object_keys = get_object_keys(s3_client, s3_bucket_name, filter_prefix=sys.argv[2])
                print("Deleting key(s): ")
                for key in object_keys:
                    print("\t"+key)
                prompt = input("Proceed (Type 'yes')? ")
                if prompt.upper() == "YES":
                    for key in object_keys:
                        delete_object(s3_client, s3_bucket_name, key)
                    print("Key(s) deleted!")
                else:
                    print("Cancelling deletion of objects...")
            else:
                print("\nMissing prefix filter for keys of S3 object(s) to delete?")

        else:
            print("\nUnknown s3_operation: '" + s3_operation + "'")
    else:
        print("Usage:\n")
        print(
            "\tpython -m kgea.aws."+Path(sys.argv[0]).stem +
            " <operation> [<object_key>+|<prefix_filter>]\n\n" +
            "where <operation> is one of upload, list, download, delete, delete-batch and test.\n\n"
            "Note:\tone or more <object_key> strings are only required for 'delete' operation.\n" +
            "\tA <prefix_filter> string is only required for 'delete-batch' operation.\n"
        )
        exit(0)
