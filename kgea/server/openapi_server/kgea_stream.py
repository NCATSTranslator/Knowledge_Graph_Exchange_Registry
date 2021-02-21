import asyncio

# For details of aiohttp usage, See https://docs.aiohttp.org/en/stable/client_quickstart.html#make-a-request
import aiohttp

import boto3

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


# TODO: should I wrap any exceptions within this function?
def transfer_file_from_stream(stream, bucket, kg_name,  session_profile=None):
    """
    Transfer a file from a data stream source
    """

    # Start accessing the data stream
    data, filename = stream()

    if not data:
        # TODO: is this ok or should an exception be thrown?
        return False

    session = boto3.Session(profile_name=session_profile)
    s3res = session.resource('s3')

    # perhaps I need to translate the filename
    object_key = object_location(filename)

    target_s3obj = s3res.Object(bucket, object_key)

    # initiate MultiPartUpload
    mpu = target_s3obj.initiate_multipart_upload()
    part_number = 0
    parts = []

    while data:
        # there is more data, upload it as a part
        part_number += 1
        part = mpu.Part(part_number)
        response = part.upload(Body=data)
        parts.append({
            "PartNumber": part_number,
            "ETag": response["ETag"]
        })

        # get the next data part
        data, _ = stream()

    # no more data, complete the upload
    part_info = {"Parts": parts}
    mpu_result = mpu.complete(MultipartUpload=part_info)

    return True


@prepare_test
def test_transfer_file_from_url(test_url=None, test_bucket=TEST_BUCKET, test_kg_name=TEST_KG_NAME):
    pass


"""
Unit Tests
* Run each test function as an assertion if we are debugging the project
"""
DEBUG = True
if DEBUG:
    assert(test_data_stream_from_url())
    print("test_data_stream_from_url passed")

    # assert(test_transfer_file_from_url())
    # print("test_transfer_file_from_url passed")
