"""
Test Parameters + Decorator
"""
from sys import stderr

import logging
from functools import wraps

import pytest
import requests
from botocore.exceptions import ClientError

from kgea.tests import (
    TEST_DATA_DIR,
    
    TEST_BUCKET,
    TEST_KG_NAME,
    TEST_FS_VERSION,
    
    TEST_SMALL_FILE_PATH,
    TEST_SMALL_FILE_RESOURCE_URL,
    
    TEST_LARGE_NODES_FILE_KEY,
    TEST_LARGE_FILE_RESOURCE_URL,
    
    TEST_HUGE_NODES_FILE,
    TEST_HUGE_NODES_FILE_KEY,
    TEST_HUGE_EDGES_FILE_KEY,
    TEST_HUGE_FILE_RESOURCE_URL, TEST_LARGE_NODES_FILE
)

from kgea.server.web_services.kgea_file_ops import (
    upload_from_link, get_url_file_size, get_archive_contents, aggregate_files, print_error_trace,
    compress_fileset, kg_files_in_location, get_object_key, upload_file, with_version,
    get_object_location, upload_file_multipart, create_presigned_url,
    get_fileset_versions_available, random_alpha_string, s3_client, location_available
)

logger = logging.getLogger(__name__)

progress_tracking_on = True


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
            Bucket='kgea-test-bucket',
            Key=get_object_location(object_key)
        )
        result = func(test_object_location=get_object_location(object_key))
        # TODO: prevent deletion for a certain period of time
        s3_client().delete_object(
            Bucket='kgea-test-bucket',
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
    return True


def test_is_location_available(
    test_object_location=get_object_location(random_alpha_string()),
    test_bucket=TEST_BUCKET
):
    try:
        isRandomLocationAvailable = location_available(bucket_name=test_bucket, object_key=test_object_location)
        return isRandomLocationAvailable
    except AssertionError as e:
        logger.error("location_available(): found a location that should not exist")
        logger.error(e)
        return False


# note: use this decorator only if the child function satisfies `test_object_location` in its arguments
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
        return False
    return True


# note: use this decorator only if the child function satisfies `test_object_location` in its arguments
def test_kg_files_in_location(test_object_location=TEST_LARGE_NODES_FILE_KEY, test_bucket=TEST_BUCKET):
    try:
        kg_file_list = kg_files_in_location(bucket_name=test_bucket, object_location=test_object_location)
        # print(kg_file_list)
        assert (len(kg_file_list) > 0)
    except AssertionError as e:
        raise AssertionError(e)
    return True


def test_create_presigned_url(test_bucket=TEST_BUCKET):
    try:
        # TODO: write tests
        create_presigned_url(bucket=test_bucket, object_key=get_object_location(TEST_KG_NAME))
    except AssertionError as e:
        logger.error(e)
        return False
    except ClientError as e:
        logger.error(e)
        return False
    return True


def test_upload_file_to_archive(test_bucket=TEST_BUCKET, test_kg=TEST_KG_NAME):
    try:
        # NOTE: file must be read in binary mode!
        with open(TEST_SMALL_FILE_PATH, 'rb') as test_file:
            content_location, _ = with_version(get_object_location)(test_kg)
            object_key = get_object_key(content_location, test_file.name)
            upload_file(
                bucket=test_bucket,
                object_key=object_key,
                source=test_file,  # packaged_file - not really implemented? what was the idea behind it?
            )
            assert (object_key in kg_files_in_location(test_bucket, content_location))
    except FileNotFoundError as e:
        logger.error("Test is malformed!")
        logger.error(e)
        return False
    except ClientError as e:
        logger.error('The upload to S3 has failed!')
        logger.error(e)
        return False
    except AssertionError as e:
        logger.error('The resulting path was not found inside of the knowledge graph folder!')
        logger.error(e)
        return False
    return True


def test_upload_file_multipart(test_bucket=TEST_BUCKET, test_kg=TEST_KG_NAME):
    try:

        # NOTE: file must be read in binary mode!
        with open(TEST_SMALL_FILE_PATH, 'rb') as test_file:
            content_location, _ = with_version(get_object_location)(test_kg)

            object_key = upload_file_multipart(test_file, test_file.name, test_bucket, content_location)

            assert (object_key in kg_files_in_location(test_bucket, content_location))

    except FileNotFoundError as e:
        logger.error("Test is malformed!")
        logger.error(e)
        return False
    except ClientError as e:
        logger.error('The upload to S3 has failed!')
        logger.error(e)
        return False
    except AssertionError as e:
        logger.error('The resulting path was not found inside of the knowledge graph folder!')
        logger.error(e)
        return False
    return True


def test_upload_file_timestamp(test_bucket=TEST_BUCKET, test_kg=TEST_KG_NAME):
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
            assert (object_key in kg_files_in_location(test_bucket, test_location))
            assert (time_created in object_key)

    except FileNotFoundError as e:
        logger.error("Test is malformed!")
        logger.error(e)
        return False
    except ClientError as e:
        logger.error('ERROR: The upload to S3 has failed!')
        logger.error(e)
        return False
    except AssertionError as e:
        logger.error(
            'The resulting path was not found inside of the ' +
            'knowledge graph folder, OR the timestamp isn\'t in the path!'
        )
        logger.error(e)
        return False
    return True


async def test_compress_fileset():
    try:
        s3_archive_key: str = await compress_fileset(
            kg_id=TEST_KG_NAME,
            version=TEST_FS_VERSION,
            bucket=TEST_BUCKET,
            root='kge-data'
        )
        logger.info(f"test_compress_fileset(): s3_archive_key == {s3_archive_key}")
        assert (s3_archive_key == f"s3://{TEST_BUCKET}/kge-data/{TEST_KG_NAME}/{TEST_FS_VERSION}"
                                  f"/archive/{TEST_KG_NAME + '_' + TEST_FS_VERSION}.tar.gz")
    except Exception as e:
        logger.error(e)
        
        return False
    return True


def test_large_aggregate_files():
    target_folder = f"kge-data/{TEST_KG_NAME}/{TEST_FS_VERSION}/archive"
    try:
        agg_path: str = aggregate_files(
            bucket=TEST_BUCKET,
            target_folder=target_folder,
            target_name='nodes.tsv',
            file_object_keys=[TEST_LARGE_NODES_FILE_KEY],
            match_function=lambda x: True
        )
    except Exception as e:
        print_error_trace("Error while unpacking archive?: " + str(e))
        return False
    
    assert (agg_path == f"s3://{TEST_BUCKET}/{target_folder}/nodes.tsv")
    
    return True


@pytest.mark.skip(reason="Huge File Test not normally run")
def test_huge_aggregate_files():
    """
    NOTE: This test attempts transfer of a Huge pair or multi-gigabyte files in S3.
    It is best to run this test on an EC2 server with the code.

    :return:
    """
    target_folder = f"kge-data/{TEST_KG_NAME}/{TEST_FS_VERSION}/archive"
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
        return False
    
    assert (agg_path == f"s3://{TEST_BUCKET}/{target_folder}/nodes_plus_edges.tsv")
    
    return True


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
    
    return True


def test_large_file_upload_from_link():
    wrap_upload_from_link(
        test_bucket=TEST_BUCKET,
        test_kg=TEST_KG_NAME,
        test_fileset_version=TEST_FS_VERSION,
        test_link=TEST_LARGE_FILE_RESOURCE_URL,
        test_link_filename=TEST_LARGE_NODES_FILE
    )


@pytest.mark.skip(reason="Huge File Test not normally run")
def test_huge_file_upload_from_link():
    wrap_upload_from_link(
        test_bucket=TEST_BUCKET,
        test_kg=TEST_KG_NAME,
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
                f"upload progress for link {test_link} so far: {progress._seen_so_far}",
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
