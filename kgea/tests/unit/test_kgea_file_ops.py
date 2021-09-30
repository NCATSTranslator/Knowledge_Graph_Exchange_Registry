"""
Test Parameters + Decorator
"""
from sys import stderr
from os import getenv
from functools import wraps

import logging

import pytest
import requests
from botocore.exceptions import ClientError

from kgea.tests import (
    TEST_BUCKET,
    
    TEST_KG_ID,
    TEST_FS_VERSION,

    TEST_OBJECT,
    
    TEST_SMALL_FILE_PATH,
    TEST_SMALL_FILE_RESOURCE_URL,
    
    TEST_LARGE_NODES_FILE,
    TEST_LARGE_NODES_FILE_KEY,
    TEST_LARGE_FILE_RESOURCE_URL,
    TEST_LARGE_FILE_PATH,

    TEST_HUGE_NODES_FILE,
    TEST_HUGE_NODES_FILE_KEY,
    TEST_HUGE_EDGES_FILE_KEY,
    TEST_HUGE_FILE_RESOURCE_URL,
)

from kgea.server.web_services.kgea_file_ops import (
    upload_from_link, get_url_file_size, get_archive_contents, aggregate_files,
    print_error_trace, compress_fileset, object_keys_in_location, get_object_key,
    upload_file, with_version, get_object_location, upload_file_multipart,
    create_presigned_url, get_fileset_versions_available, random_alpha_string,
    s3_client, location_available, copy_file, object_key_exists,
    object_keys_for_fileset_version, object_folder_contents_size
)

logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")

progress_tracking_on = True

# Running the PyTests in DEV_MODE suppresses deletion of files in S3
# Useful for debugging the tests
DEV_MODE = getenv('DEV_MODE', default=False)


def prepare_test_random_object_location(func):
    """

    :param func:
    :return:
    """
    @wraps(func)
    def wrapper(object_key=random_alpha_string()):
        """

        :param object_key:
        :return:
        """
        s3_client().put_object(
            Bucket=TEST_BUCKET,
            Key=get_object_location(object_key)
        )
        result = func(test_object_location=get_object_location(object_key))
        # TODO: prevent deletion for a certain period of time
        s3_client().delete_object(
            Bucket=TEST_BUCKET,
            Key=get_object_location(object_key)
        )
        return result

    return wrapper


def test_get_fileset_versions_available(test_bucket=TEST_BUCKET):
    try:
        fileset_version_map = get_fileset_versions_available(bucket_name=test_bucket)
        assert (type(fileset_version_map) is dict and len(fileset_version_map) > 0)
    except AssertionError as e:
        raise AssertionError(e)


def test_is_location_available(
    test_object_location=get_object_location(random_alpha_string()),
    test_bucket=TEST_BUCKET
):
    try:
        is_random_location_available = location_available(bucket_name=test_bucket, object_key=test_object_location)
        return is_random_location_available
    except AssertionError as e:
        logger.error("location_available(): found a location that should not exist")
        logger.error(e)
        assert False


def test_is_not_location_available(test_object_location=TEST_LARGE_NODES_FILE_KEY, test_bucket=TEST_BUCKET):
    """
    Test in the positive:
    * make dir
    * test for existence
    * assert not True (because it already exists)
    * close/delete dir
    """
    try:
        is_random_location_available = location_available(bucket_name=test_bucket, object_key=test_object_location)
        assert (is_random_location_available is not True)
    except AssertionError as e:
        logger.error("ERROR: created location was not found")
        logger.error(e)
        assert False


def test_object_keys_in_location(test_object_location=TEST_LARGE_NODES_FILE_KEY, test_bucket=TEST_BUCKET):
    try:
        kg_file_list = object_keys_in_location(bucket=test_bucket, object_location=test_object_location)
        # print(kg_file_list)
        assert (len(kg_file_list) > 0)
    except AssertionError as e:
        raise AssertionError(e)


def test_object_folder_contents_size(
        test_kg_id=TEST_KG_ID,
        test_fileset_version=TEST_FS_VERSION,
        test_bucket=TEST_BUCKET
):
    fk1 = upload_test_file(test_subfolder='archive/')
    fk2 = upload_test_file(test_file_path=TEST_LARGE_FILE_PATH, test_subfolder='archive/')
    
    size = object_folder_contents_size(
        kg_id=test_kg_id,
        fileset_version=test_fileset_version,
        bucket=test_bucket
    )
    logger.info(f"{test_kg_id}/{test_fileset_version} S3 bucket folder is {size} bytes in size")
    
    assert(size > 0)
    
    delete_test_file(test_object_key=fk1)
    delete_test_file(test_object_key=fk2)


def test_create_presigned_url(test_bucket=TEST_BUCKET):
    try:
        # TODO: write tests
        create_presigned_url(bucket=test_bucket, object_key=get_object_location(TEST_KG_ID))
    except AssertionError as e:
        logger.error(e)
        assert False
    except ClientError as e:
        logger.error(e)
        assert False


def upload_test_file(
        test_bucket=TEST_BUCKET,
        test_kg=TEST_KG_ID,
        test_file_path=TEST_SMALL_FILE_PATH,
        test_subfolder=''
):
    """

    :param test_bucket:
    :param test_kg:
    :param test_file_path:
    :param test_subfolder:
    :return:
    """
    # NOTE: file must be read in binary mode!
    logger.debug(f"upload_test_file(): '{test_file_path}' in '{test_kg}' of '{test_bucket}'")
    
    with open(test_file_path, 'rb') as test_file:
        
        content_location, _ = with_version(get_object_location)(test_kg)
        content_location = f"{content_location}{test_subfolder}"
        test_file_object_key = get_object_key(content_location, test_file.name)
        
        # only create the object key if it doesn't already exist?
        if not object_key_exists(object_key=test_file_object_key):
            upload_file(
                bucket=test_bucket,
                object_key=test_file_object_key,
                source=test_file
            )
            assert (test_file_object_key in object_keys_in_location(test_bucket, content_location))

    return test_file_object_key


def delete_test_file(test_object_key, test_bucket=TEST_BUCKET, test_client=s3_client()):
    """

    :param test_object_key:
    :param test_bucket:
    :param test_client:
    """
    logger.debug(f"delete_test_file(): {test_object_key} in {test_bucket}")
    test_client.delete_object(Bucket=test_bucket, Key=test_object_key)


def test_upload_file_to_archive(test_bucket=TEST_BUCKET, test_kg=TEST_KG_ID):
    try:
        test_object_key = upload_test_file(
            test_bucket=test_bucket,
            test_kg=test_kg,
            test_subfolder='archive/'
        )
    except FileNotFoundError as e:
        logger.error("Test is malformed!")
        logger.error(e)
        assert False
    except ClientError as e:
        logger.error('The upload to S3 has failed!')
        logger.error(e)
        assert False
    except AssertionError as e:
        logger.error('The resulting path was not found inside of the knowledge graph folder!')
        logger.error(e)
        assert False

    delete_test_file(test_object_key=test_object_key, test_bucket=test_bucket)


def test_kg_files_for_version(
        test_kg=TEST_KG_ID,
        test_version=TEST_FS_VERSION,
        test_bucket=TEST_BUCKET,
):
    file_list, _ = \
        object_keys_for_fileset_version(
            kg_id=test_kg,
            fileset_version=test_version,
            bucket=test_bucket
        )
    print(file_list)


def test_upload_file_multipart(test_bucket=TEST_BUCKET, test_kg=TEST_KG_ID):
    try:

        # NOTE: file must be read in binary mode!
        with open(TEST_SMALL_FILE_PATH, 'rb') as test_file:
            content_location, _ = with_version(get_object_location)(test_kg)

            object_key = upload_file_multipart(test_file, test_file.name, test_bucket, content_location)

            assert (object_key in object_keys_in_location(test_bucket, content_location))

    except FileNotFoundError as e:
        logger.error("Test is malformed!")
        logger.error(e)
        assert False
    except ClientError as e:
        logger.error('The upload to S3 has failed!')
        logger.error(e)
        assert False
    except AssertionError as e:
        logger.error('The resulting path was not found inside of the knowledge graph folder!')
        logger.error(e)
        assert False


def test_upload_file_timestamp(test_bucket=TEST_BUCKET, test_kg=TEST_KG_ID):
    """
    Use the "with_version" wrapper to modify the object location
    """
    try:
        test_location, time_created = with_version(get_object_location)(test_kg)
        # NOTE: file must be read in binary mode!
        with open(TEST_SMALL_FILE_PATH, 'rb') as test_file:
            object_key = get_object_key(test_location, test_file.name)
            upload_file(
                bucket=test_bucket,
                object_key=object_key,
                source=test_file,
            )
            assert (object_key in object_keys_in_location(test_bucket, test_location))
            assert (time_created in object_key)

    except FileNotFoundError as e:
        logger.error("Test is malformed!")
        logger.error(e)
        assert False
    except ClientError as e:
        logger.error('ERROR: The upload to S3 has failed!')
        logger.error(e)
        assert False
    except AssertionError as e:
        logger.error(
            'The resulting path was not found inside of the ' +
            'knowledge graph folder, OR the timestamp isn\'t in the path!'
        )
        logger.error(e)
        assert False


def test_copy_file():
    try:
        testdir = "test-copy"
        # TODO: how do I bootstrap this test?
        source_key = f"{testdir}/{TEST_OBJECT}"
        s3_client().put_object(
            Bucket=TEST_BUCKET,
            Key=source_key,
            Body=b'Test Object'
        )
        
        target_dir = f"{testdir}/target_dir"
        
        copy_file(
            source_key=source_key,
            target_dir=target_dir,
            bucket=TEST_BUCKET
        )
        target_key = f"{target_dir}/{TEST_OBJECT}"
        
        assert(object_key_exists(object_key=target_key))

        response = s3_client().list_objects_v2(Bucket=TEST_BUCKET, Prefix=testdir)

        for obj in response['Contents']:
            logger.debug(f"Deleting {obj['Key']}")
            s3_client().delete_object(Bucket=TEST_BUCKET, Key=obj['Key'])
        
        assert (not object_key_exists(object_key=testdir))
        
    except Exception as e:
        logger.error(e)
        assert False


async def test_compress_fileset():
    try:
        s3_archive_key: str = compress_fileset(
            kg_id=TEST_KG_ID,
            version=TEST_FS_VERSION,
            bucket=TEST_BUCKET,
            root='kge-data'
        )
        logger.info(f"test_compress_fileset(): s3_archive_key == {s3_archive_key}")
        assert (s3_archive_key == f"s3://{TEST_BUCKET}/kge-data/{TEST_KG_ID}/{TEST_FS_VERSION}"
                                  f"/archive/{TEST_KG_ID + '_' + TEST_FS_VERSION}.tar.gz")
    except Exception as e:
        logger.error(e)
        assert False


def test_large_aggregate_files():
    target_folder = f"kge-data/{TEST_KG_ID}/{TEST_FS_VERSION}/archive"
    try:
        agg_path: str = aggregate_files(
            target_folder=target_folder,
            target_name='nodes.tsv',
            file_object_keys=[TEST_LARGE_NODES_FILE_KEY],
            bucket=TEST_BUCKET,
            match_function=lambda x: True
        )
    except Exception as e:
        print_error_trace("Error while unpacking archive?: " + str(e))
        assert False
    
    assert (agg_path == f"s3://{TEST_BUCKET}/{target_folder}/nodes.tsv")


@pytest.mark.skip(reason="Huge File Test not normally run")
def test_huge_aggregate_files():
    """
    NOTE: This test attempts transfer of a Huge pair or multi-gigabyte files in S3.
    It is best to run this test on an EC2 server with the code.

    :return:
    """
    target_folder = f"kge-data/{TEST_KG_ID}/{TEST_FS_VERSION}/archive"
    try:
        agg_path: str = aggregate_files(
            bucket=TEST_BUCKET,
            target_folder=target_folder,
            target_name='nodes_plus_edges.tsv',
            file_object_keys=[
                TEST_HUGE_NODES_FILE_KEY,
                TEST_HUGE_EDGES_FILE_KEY
            ],
            match_function=lambda x: True
        )
    except Exception as e:
        print_error_trace("Error while unpacking archive?: " + str(e))
        assert False
    
    assert (agg_path == f"s3://{TEST_BUCKET}/{target_folder}/nodes_plus_edges.tsv")


def test_get_archive_contents(test_bucket=TEST_BUCKET):
    logger.info(f"test_get_archive_contents() test output:")
    contents = get_archive_contents(test_bucket)
    logger.info(str(contents))
    

def test_get_url_file_size():
    url_resource_size: int = get_url_file_size(url=TEST_SMALL_FILE_RESOURCE_URL)
    assert (url_resource_size > 0)
    logger.info(
        f"test_get_url_file_size(): reported file size is '{url_resource_size}'" +
        f" for url resource {TEST_SMALL_FILE_RESOURCE_URL}"
    )
    url_resource_size = get_url_file_size(url=TEST_HUGE_FILE_RESOURCE_URL)
    assert (url_resource_size > 0)
    logger.info(
        f"test_get_url_file_size(): reported file size is '{url_resource_size}'" +
        f" for url resource {TEST_HUGE_FILE_RESOURCE_URL}"
    )
    url_resource_size = get_url_file_size(url="https://nonexistent.url")
    assert (url_resource_size < 0)
    url_resource_size = get_url_file_size(url='')
    assert (url_resource_size == 0)
    url_resource_size = get_url_file_size(url='abc')
    assert (url_resource_size < 0)


def test_large_file_upload_from_link():
    wrap_upload_from_link(
        test_bucket=TEST_BUCKET,
        test_kg=TEST_KG_ID,
        test_fileset_version=TEST_FS_VERSION,
        test_link=TEST_LARGE_FILE_RESOURCE_URL,
        test_link_filename=TEST_LARGE_NODES_FILE
    )


@pytest.mark.skip(reason="Huge File Test not normally run")
def test_huge_file_upload_from_link():
    wrap_upload_from_link(
        test_bucket=TEST_BUCKET,
        test_kg=TEST_KG_ID,
        test_fileset_version=TEST_FS_VERSION,
        test_link=TEST_HUGE_FILE_RESOURCE_URL,
        test_link_filename=TEST_HUGE_NODES_FILE,
    )


def wrap_upload_from_link(test_bucket, test_kg, test_fileset_version, test_link, test_link_filename):
    """

    :param test_bucket: 
    :param test_kg: 
    :param test_fileset_version: 
    :param test_link: 
    :param test_link_filename: 
    :return: 
    """
    progress_monitor = None

    if progress_tracking_on:

        class ProgressPercentage(object):
            """
            Class to track percentage completion of an upload.
            """

            REPORTING_INCREMENT: int = 1000000

            def __init__(self, filename, file_size, cont=None):
                self._filename = filename
                self.size = file_size
                self._seen_so_far = 0
                self._report_threshold = self.REPORTING_INCREMENT
                self.cont = cont

            def get_file_size(self):
                """
                :return: file size of the file being uploaded.
                """
                return self.size

            def seen_so_far(self):
                """
                :return: bytes of file size seen so far, for the file being uploaded.
                """
                return self._seen_so_far
            
            def __call__(self, bytes_amount):
                # To simplify we'll assume this is hooked up
                # to a single filename.
                # with self._lock:
                self._seen_so_far += bytes_amount

                if self.cont is not None:
                    # cont lets us inject e.g. logging
                    if self._seen_so_far > self._report_threshold:
                        self.cont(self)
                        self._report_threshold += self.REPORTING_INCREMENT

        # url = "https://speed.hetzner.de/100MB.bin"
        # just a dummy file URL
        info = requests.head(test_link)
        # fetching the header information
        logger.debug(info.headers['Content-Length'])

        progress_monitor = ProgressPercentage(
            test_link_filename,
            info.headers['Content-Length'],
            cont=lambda progress: print(
                f"upload progress for link {test_link} so far: {progress.seen_so_far()}",
                file=stderr, flush=True
            )
        )

    object_key = f"{test_kg}/{test_fileset_version}/{test_link_filename}"

    logger.debug("\ntest_upload_from_link() url: '"+test_link+"' to object key '"+object_key+"':\n")

    try:
        upload_from_link(
            bucket=test_bucket,
            object_key=object_key,
            source=test_link,
            callback=progress_monitor
        )
    except RuntimeError as rte:
        logger.error('Failed?: '+str(rte))
        assert False

    logger.debug('Success!')
