#
# Unit tests for AWS utilities
#
from os import getenv

from botocore.config import Config

from kgea.aws.assume_role import aws_config, AssumeRole
from kgea.aws.s3 import copy, s3_client
from kgea.server.web_services.kgea_file_ops import object_key_exists
from kgea.tests import TEST_BUCKET_2, PROD_TEST_FILE_KEY, TEST_BUCKET
from kgea.tests.unit.test_kgea_file_ops import upload_test_file, delete_test_file

# Master flag for local development retaining
# created test files in S3 after the test is run
KEEP_TEST_FILES = getenv('KEEP_TEST_FILES', default=False) == 'True'


def test_s3_local_copy_to_new_key_in_same_bucket():
    
    src_test_key = upload_test_file()
    assert(object_key_exists(object_key=src_test_key))
    
    tgt_test_key = f"{src_test_key}_copy"
    
    copy(
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
    
    copy(
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
    
    # Expect the remote 'src_test_key' resource
    # to be copied into the local test bucket?

    copy(
        source_key=src_test_key,
        target_key=src_test_key,
        source_bucket=TEST_BUCKET,
        target_bucket=target_bucket,
        target_client=target_client
    )
    
    assert (object_key_exists(object_key=src_test_key, bucket_name=target_bucket))
    
    if not KEEP_TEST_FILES:
        # Don't delete the original source key!!! It's a real data file!!!
        # However, you can delete the key in the default bucket == TEST_BUCKET
        delete_test_file(test_object_key=src_test_key, test_bucket=target_bucket)
