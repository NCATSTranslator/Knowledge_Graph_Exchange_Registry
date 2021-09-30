"""
Unit tests for AWS utilities
"""
from os import getenv, remove
from os.path import isfile

from botocore.config import Config

from kgea.aws.assume_role import aws_config, AssumeRole
from kgea.aws.s3 import local_copy, s3_client, upload_file, list_files, delete_object, remote_copy, download_file
from kgea.server.web_services.kgea_file_ops import object_key_exists
from kgea.tests import (
    TEST_BUCKET_2,
    TEST_BUCKET,
    TEST_SMALL_FILE,
    TEST_SMALL_FILE_PATH,
    TEST_SMALL_FILE_KEY
)
from kgea.tests.unit.test_kgea_file_ops import upload_test_file, delete_test_file

# Master flag for local development retaining
# created test files in S3 after the test is run
KEEP_TEST_FILES = getenv('KEEP_TEST_FILES', default=False) == 'True'


def test_assumed_role_s3_access(
        bucket_name: str = TEST_BUCKET,
        client=s3_client
):
    """
    Test for assumed role s3 access on a given bucket.

    :param client:
    :param bucket_name:
    :return:
    """
    
    upload_file(bucket_name, TEST_SMALL_FILE_PATH, TEST_SMALL_FILE_KEY, client)
    
    list_files(bucket_name, client)
    
    delete_object(bucket_name, TEST_SMALL_FILE_KEY, client)


def test_upload_file(
        bucket_name: str = TEST_BUCKET,
        client=s3_client
):
    """
    Test for uploading of file to S3.

    :param client:
    :param bucket_name:
    :return:
    """
    upload_file(
        bucket_name=bucket_name,
        source_file=TEST_SMALL_FILE_PATH,
        target_object_key=TEST_SMALL_FILE_KEY,
        client=client
    )
    
    # successful upload?
    assert (object_key_exists(object_key=TEST_SMALL_FILE_KEY))
    
    # clean up after test
    delete_object(
        bucket_name=bucket_name,
        target_object_key=TEST_SMALL_FILE_KEY,
        client=client
    )

    with open(TEST_SMALL_FILE_PATH, mode='rb') as test_fd:
        upload_file(
            bucket_name=bucket_name,
            source_file=test_fd,
            target_object_key=TEST_SMALL_FILE_KEY,
            client=client
        )
        
    # successful upload?
    assert (object_key_exists(object_key=TEST_SMALL_FILE_KEY))

    # clean up after test
    delete_object(
        bucket_name=bucket_name,
        target_object_key=TEST_SMALL_FILE_KEY,
        client=client
    )


def test_download_file(
        bucket_name: str = TEST_BUCKET,
        client=s3_client
):
    """
    Test for downloading of a S3 object to a target file.

    :param client:
    :param bucket_name:
    :return:
    """

    # ensure that a test file exists for downloading
    src_test_key = upload_test_file()
    assert (object_key_exists(object_key=src_test_key))
    
    # Test first downloading to a file of given name
    download_file(
        bucket_name=bucket_name,
        source_object_key=src_test_key,
        target_file=TEST_SMALL_FILE,
        client=client
    )

    # successful download?
    assert isfile(TEST_SMALL_FILE)
    
    # Clean up test file
    remove(TEST_SMALL_FILE)
    
    # Test next downloading the test object to write to a open file object of a given name
    with open(TEST_SMALL_FILE, 'wb') as test_fd:
        download_file(
            bucket_name=bucket_name,
            source_object_key=src_test_key,
            target_file=test_fd,
            client=client
        )

    # successful download?
    assert isfile(TEST_SMALL_FILE)

    # Clean up test file
    remove(TEST_SMALL_FILE)

    # Clean up test object in S3
    delete_object(
        bucket_name=bucket_name,
        target_object_key=src_test_key,
        client=client
    )


def test_s3_local_copy_to_new_key_in_same_bucket():
    
    src_test_key = upload_test_file()
    assert(object_key_exists(object_key=src_test_key))
    
    tgt_test_key = f"{src_test_key}_copy"
    
    local_copy(
        source_key=src_test_key,
        target_key=tgt_test_key
    )
    assert (object_key_exists(object_key=tgt_test_key))
    
    if not KEEP_TEST_FILES:
        delete_test_file(src_test_key)
        delete_test_file(tgt_test_key)


def test_s3_local_copy_to_new_key_in_different_bucket():
    
    src_test_key = upload_test_file()
    
    assert (object_key_exists(object_key=src_test_key))
    
    tgt_test_key = f"{src_test_key}_copy"
    
    local_copy(
        source_key=src_test_key,
        target_key=tgt_test_key,
        target_bucket=TEST_BUCKET_2
    )
    
    assert (object_key_exists(object_key=tgt_test_key, bucket_name=TEST_BUCKET_2))
    
    if not KEEP_TEST_FILES:
        delete_test_file(src_test_key)
        delete_test_file(tgt_test_key, test_bucket=TEST_BUCKET_2)


def test_s3_local_copy_to_new_key_in_different_bucket_and_account():
    
    # config.yaml 's3_remote' override - must be completely specified?
    assert([
            tag in aws_config["s3_remote"]
            for tag in [
                'guest_external_id',
                'host_account',
                'iam_role_name',
                'archive-directory',
                'bucket',
                'region'
            ]
        ]
    )
    
    target_bucket = aws_config["s3_remote"]["bucket"]

    target_assumed_role = AssumeRole(
        host_account=aws_config["s3_remote"]['host_account'],
        guest_external_id=aws_config["s3_remote"]['guest_external_id'],
        iam_role_name=aws_config["s3_remote"]['iam_role_name']
    )

    target_client = \
        target_assumed_role.get_client(
            's3',
            config=Config(
                signature_version='s3v4',
                region_name=aws_config["s3_remote"]["region"]
            )
        )
        
    src_test_key = upload_test_file()

    # Sanity check - is the file there?
    assert object_key_exists(
        object_key=src_test_key,
        bucket_name=TEST_BUCKET
    )
    
    # Expect the local 'src_test_key' resource
    # to be copied into the default remote bucket?
    remote_copy(
        source_key=src_test_key,
        target_key=src_test_key,
        source_bucket=TEST_BUCKET,
        target_bucket=target_bucket,
        target_client=target_client
    )
    
    assert object_key_exists(
        object_key=src_test_key,
        bucket_name=target_bucket,
        assumed_role=target_assumed_role
    )
    
    list_files(target_bucket, target_client)
    
    if not KEEP_TEST_FILES:
        delete_test_file(
            test_object_key=src_test_key,
            test_bucket=target_bucket,
            test_client=target_client
        )
