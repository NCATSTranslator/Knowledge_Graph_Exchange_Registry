from string import Template
from os import getenv
from typing import List, Dict

from asyncio import (
    ensure_future,
    wait,
    wait_for
)
from collections.abc import AsyncIterable

import boto3
from botocore.exceptions import ClientError

from .kgea_file_ops import (
    get_object_location,
    kg_files_in_location,
    with_timestamp
)

from .kgea_session import (
    initialize_global_session,
    get_event_loop,
    get_global_session,
    close_global_session
)

import logging

# Master flag for local development runs bypassing authentication and other production processes
DEV_MODE = getenv('DEV_MODE', default=False)
RUN_TESTS = getenv('RUN_TESTS', default=False)

logger = logging.getLogger(__name__)
if DEV_MODE:
    logger.setLevel(logging.DEBUG)


# Allow for a default maximum of 5 minutes to transfer a relatively large file
KB = 1024
MB = KB * KB

if DEV_MODE:
    S3_CHUNK_SIZE = 1 * KB  # MPU threshold 1 KB at a time for test transfers
else:
    S3_CHUNK_SIZE = 8 * MB  # MPU threshold 8 MB at a time for production AWS transfers

URL_TRANSFER_TIMEOUT = 300   # default timeout, in seconds


# TODO: Perhaps need to manage the aiohttp sessions globally in the application?
# See https://docs.aiohttp.org/en/stable/client_quickstart.html#make-a-request
async def stream_from_url(url) -> AsyncIterable:
    """
    Streaming of data from URL endpoint.

    :param url: URL endpoint source of data
    :type url: str

    :yield: chunk of data
    :rtype: str
    """
    async with get_global_session().get(url, chunked=True, read_bufsize=S3_CHUNK_SIZE) as resp:
        data = await resp.content.read(S3_CHUNK_SIZE)
        yield data


async def merge_file_from_url(url):
    """
    Merge chunks from data stream from URL. Normally won't use this for large
    files. This function is more helpful in the local test suite rather than
    the mainstream url uploading handler 'transfer_file_from_url'.

    :param url: URL endpoint source of data
    :type url: str

    :return: data aggregated from stream
    :rtype: str
    """
    file_data = b''
    async for data in stream_from_url(url):
        file_data += data
    return file_data


def test_data_stream_from_url(test_url):
    tasks = [ensure_future(merge_file_from_url(test_url))]
    get_event_loop().run_until_complete(wait(tasks))
    print("Data from URL: %s" % [task.result() for task in tasks])
    return True


async def _mpu_transfer_from_url(mpu, url: str) -> List[Dict]:
    """
    Data pipe from an aiohttp URL data stream, to an AWS S3 Multi-part Upload process.

    :param mpu: active Multi-Part Upload handle
    :param url: URL from which to access the (binary) data stream.
    :return: List of Dictionary entries of PartNumbers and ETag's for uploaded MPU Parts
    :rtype: List[Dict]
    """
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
def transfer_file_from_url(
        url: str, file_name: str,
        bucket: str, object_location: str,
        timeout=URL_TRANSFER_TIMEOUT
):
    """Upload a file from a URL  endpoint, to a S3 bucket

    :param url: string URL to file to upload (can be read in binary mode)
    :param bucket: string name of bucket into which to upload the file
    :param file_name: string name of the file to be uploaded
    :param object_location: string root S3 object location name.
    :param timeout: integer URL file transfer timeout (default: 300 seconds)
    
    :return: True if file was uploaded, else False
    """

    object_key = Template('$ROOT$FILENAME').substitute(
        ROOT=object_location,
        FILENAME=file_name
    )

    # Attempt to transfer the file from the URL
    mpu = None
    try:

        # AWS Boto3 session should already be initialized
        s3res = boto3.resource('s3')

        target_s3obj = s3res.Object(bucket, object_key)

        # initiate MultiPartUpload
        mpu = target_s3obj.initiate_multipart_upload()

        transfer_task = ensure_future(_mpu_transfer_from_url(mpu, url))
        get_event_loop().run_until_complete(wait_for(transfer_task, timeout=timeout))
        
        # MPU Parts returned as the result
        parts = transfer_task.result()

        logging.debug(parts)

        # no more data, complete the multipart upload
        part_info = {"Parts": parts}
        mpu_result = mpu.complete(MultipartUpload=part_info)

    except ClientError as ce_error:
        if mpu:
            # clean up failed multipart uploads?
            response = mpu.abort()
            # TODO: should check ListParts for empty list after abort
            print(response)
        raise ce_error
    except RuntimeError as rt_error:
        if mpu:
            # clean up failed multipart uploads?
            response = mpu.abort()
            # TODO: should check ListParts for empty list after abort
            print(response)
        raise rt_error

    return object_key


def test_transfer_file_from_url(test_url, test_file_name, test_bucket, test_kg):
    try:
        test_object_location, _ = with_timestamp(get_object_location)(test_kg)
        object_key = transfer_file_from_url(test_url, test_file_name, test_bucket, test_object_location)
        assert(object_key in kg_files_in_location(test_bucket, test_object_location))
    except ClientError as e:
        logger.error('The upload to S3 has failed!')
        logger.error(e)
        return False
    except AssertionError as e:
        logger.error('The resulting S3 object_key of file transferred from url ' +
                     test_url+' was not found inside of the knowledge graph folder!')
        logger.error(e)
        return False
    return True


"""
Unit Tests
* Run each test function as an assertion if we are debugging the project
"""
if __name__ == '__main__':
    
    TEST_FILE_URL = "https://raw.githubusercontent.com/NCATSTranslator/" + \
                    "Knowledge_Graph_Exchange_Registry/master/LICENSE"
    TEST_FILE_NAME = "MIT_LICENSE"
    TEST_BUCKET = 'kgea-test-bucket'
    TEST_KG_NAME = 'test_kg'
    
    initialize_global_session()
    
    assert(test_data_stream_from_url(test_url=TEST_FILE_URL))
    print("test_data_stream_from_url passed")

    assert(test_transfer_file_from_url(
        test_url=TEST_FILE_URL,
        test_file_name=TEST_FILE_NAME,
        test_bucket=TEST_BUCKET,
        test_kg=TEST_KG_NAME)
    )
    print("test_transfer_file_from_url passed")
    
    close_global_session()
    
    exit(0)
