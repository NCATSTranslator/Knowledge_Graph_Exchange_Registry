from string import Template
from os.path import splitext
from pathlib import Path
from urllib.parse import urlparse

import asyncio

# For details of aiohttp usage, See https://docs.aiohttp.org/en/stable/client_quickstart.html#make-a-request
import aiohttp

import boto3
from botocore.exceptions import ClientError

from .kgea_file_ops import (
    get_object_location,
    kg_files_in_location,
    with_timestamp
)

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Allow for a default maximum of 5 minutes to transfer a relatively large file
URL_TRANSFER_TIMEOUT = 300

"""
Test Parameters + Decorator
"""
TEST_BUCKET = 'kgea-test-bucket'
TEST_KG_NAME = 'test_kg'


def prepare_test(func):
    def wrapper():
        TEST_BUCKET = 'kgea-test-bucket'
        TEST_KG_NAME = 'test_kg'
        return func()
    return wrapper


# Stub function...  TODO: check kgea_file_ops.py for real implementation
def object_location(filename: str) -> str:
    return filename


S3_CHUNK_SIZE = 1024 * 1024 * 5 # 5 MB at the time


# TODO: Perhaps need to manage the aiohttp sessions globally in the application?
# See https://docs.aiohttp.org/en/stable/client_quickstart.html#make-a-request
async def mpu_file_from_url(url):
    """
    Multipart fetch from  URL... not sure that this is needed or makes sense here (for URL acccess)
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:

            reader = aiohttp.MultipartReader.from_response(resp)
            data = None
            filename = None

            part = await reader.next()
            # Should be a non-empty BodyPartReader text instance here

            # grab the filename here
            if part:
                filename = part.filename

            while part:
                # Should be a non-empty BodyPartReader text instance here

                data = await part.read(S3_CHUNK_SIZE)

                # send a data segment back
                yield data, filename

                part = await reader.next()


async def stream_from_url(url) -> str:
    """
    Streaming of data from URL endpoint.

    :param url: URL endpoint source of data
    :type url: str

    :yield: chunk of data
    :rtype: str
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            while True:
                chunk = await resp.content.read(S3_CHUNK_SIZE)
                if not chunk:
                    break
                yield chunk


TEST_FILE_URL = "https://raw.githubusercontent.com/NCATSTranslator/Knowledge_Graph_Exchange_Registry/master/LICENSE"


async def merge_from_url(url):
    """
    Merge chunks from data stream from URL.
    Normally won't use this for large files.
    v
    :param url: URL endpoint source of data
    :type url: str

    :return: data aggregated from stream
    :rtype: str
    """
    filedata = b''
    async for data in stream_from_url(url):
        filedata += data
    return filedata


@prepare_test
def test_data_stream_from_url(test_url=TEST_FILE_URL):
    loop = asyncio.get_event_loop()
    tasks = [asyncio.ensure_future(merge_from_url(test_url))]
    loop.run_until_complete(asyncio.wait(tasks))
    print("test_data_stream_from_url results: %s" % [task.result() for task in tasks])
    return True


async def mpu_transfer_from_url(mpu, url):
    part_number = 0
    parts = []
    async for data in stream_from_url(url):
        # there is more data, upload it as a part
        part_number += 1
        part = mpu.Part(part_number)
        response = part.upload(Body=data)
        parts.append({
            "PartNumber": part_number,
            "ETag": response["ETag"]
        })
    return parts


# TODO: should I wrap any exceptions within this function?
def transfer_file_from_url(url, bucket, root_location, timeout=URL_TRANSFER_TIMEOUT):
    """Upload a file from a URL  endpoint, to a S3 bucket

    :param url: URL to file to upload (can be read in binary mode)
    :param bucket: Bucket to which to upload the file
    :param root_location: root S3 object location name.
    :param timeout: URL file transfer timeout (default: 300 seconds)
    :return: True if file was uploaded, else False
    """

    # Strive to isolate the file name in the URL path
    url_parts = urlparse(url)
    url_path = url_parts.path

    object_key = Template('$ROOT$FILENAME$EXTENSION').substitute(
        ROOT=root_location,
        FILENAME=Path(url_path).stem,
        EXTENSION=splitext(url_path)[1]
    )

    # Attempt to transfer the file from the URL
    try:

        # AWS Boto3 session should already be initialized
        s3res = boto3.resource('s3')

        target_s3obj = s3res.Object(bucket, object_key)

        # initiate MultiPartUpload
        mpu = target_s3obj.initiate_multipart_upload()

        loop = asyncio.get_event_loop()
        transfer_task = asyncio.ensure_future(mpu_transfer_from_url(mpu, url))
        loop.run_until_complete(asyncio.wait_for(transfer_task, timeout=timeout))

        # MPU Parts returned as the result
        parts = transfer_task.result()

        logging.debug(parts)

        # no more data, complete the multipart upload
        part_info = {"Parts": parts}
        mpu_result = mpu.complete(MultipartUpload=part_info)

    except ClientError as error_message:
        raise ClientError(error_message)

    return object_key


@prepare_test
def test_transfer_file_from_url(test_url=TEST_FILE_URL, test_bucket=TEST_BUCKET, test_kg=TEST_KG_NAME):
    try:
        content_location, _ = with_timestamp(get_object_location)(test_kg)
        object_key = transfer_file_from_url(test_url, test_bucket, content_location)
        assert(object_key in kg_files_in_location(test_bucket, content_location))
    except ClientError as e:
        logger.error('The upload to S3 has failed!')
        logger.error(e)
        return False
    except AssertionError as e:
        logger.error('The resulting S3 object_key of file transferred from url '+
                     test_url+' was not found inside of the knowledge graph folder!')
        logger.error(e)
        return False
    return True


"""
Unit Tests
* Run each test function as an assertion if we are debugging the project
"""
DEBUG = True
if DEBUG:
    assert(test_data_stream_from_url())
    print("test_data_stream_from_url passed")

    assert(test_transfer_file_from_url())
    print("test_transfer_file_from_url passed")
