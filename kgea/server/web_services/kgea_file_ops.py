"""
Implement robust KGE File Set upload process:
o  “layered” back end unit tests of each level of S3 upload process
o  Figure out the minimal S3 access policy that suffices for the KGE Archive (not a huge priority this week but…)
o  File set versioning using time stamps
o  Web server optimization (e.g. NGINX / WSGI / web application parameters)
o  Test the system (both manually, by visual inspection of uploads)
Stress test using SRI SemMedDb: https://github.com/NCATSTranslator/semmeddb-biolink-kg
"""
import io
from sys import stderr
from typing import Dict, Union, List
from functools import wraps
from string import Template
import random
from json import loads
import time
from datetime import datetime

from os.path import abspath, splitext
from io import BytesIO
import tempfile
from pathlib import Path
import tarfile
from s3_tar import S3Tar

import yaml

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

import webbrowser
import requests

import boto3
from botocore.exceptions import ClientError

from kgea.server.config import (
    s3_client,
    get_app_config,
    PROVIDER_METADATA_FILE
)

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Opaquely access the configuration dictionary
_KGEA_APP_CONFIG = get_app_config()


def create_location(bucket, kg_id):
    return s3_client.put_object(Bucket=bucket, Key=get_object_location(kg_id))


def delete_location(bucket, kg_id):
    return s3_client.delete(Bucket=bucket, Key=get_object_location(kg_id))


# https://www.askpython.com/python/examples/generate-random-strings-in-python
def _random_alpha_string(length=8):
    random_string = ''
    for _ in range(length):
        # Considering only upper and lowercase letters
        random_integer = random.randint(97, 97 + 26 - 1)
        flip_bit = random.randint(0, 1)
        # Convert to lowercase if the flip bit is on
        random_integer = random_integer - 32 if flip_bit == 1 else random_integer
        # Keep appending random characters using chr(x)
        random_string += (chr(random_integer))
    return random_string


"""
Test Parameters + Decorator
"""
TEST_BUCKET = 'kgea-test-bucket'
TEST_KG_NAME = 'test_kg'
TEST_FILE_DIR = 'kgea/server/test/data/'
TEST_FILE_NAME = 'somedata.csv'


def prepare_test(func):
    @wraps(func)
    def wrapper():
        TEST_BUCKET = 'kgea-test-bucket'
        TEST_KG_NAME = 'test_kg'
        return func()

    return wrapper


def prepare_test_random_object_location(func):
    @wraps(func)
    def wrapper(object_key=_random_alpha_string()):
        s3_client.put_object(
            Bucket='kgea-test-bucket',
            Key=get_object_location(object_key)
        )
        result = func(test_object_location=get_object_location(object_key))
        # TODO: prevent deletion for a certain period of time
        s3_client.delete_object(
            Bucket='kgea-test-bucket',
            Key=get_object_location(object_key)
        )
        return result

    return wrapper


def get_object_location(kg_id):
    """
    NOTE: Must be kept deterministic. No date times or
    randomness in this method; they may be appended afterwards.
    """
    location = Template('$DIRECTORY_NAME/$KG_NAME/').substitute(
        DIRECTORY_NAME=_KGEA_APP_CONFIG['archive-directory'],
        KG_NAME=kg_id
    )
    return location


def get_default_date_stamp():
    return datetime.now().strftime('%Y-%m-%d')


def with_version(func, version=get_default_date_stamp()):
    def wrapper(kg_id):
        return func(kg_id + '/' + version), version

    return wrapper


def with_subfolder(location: str, subfolder: str):
    if subfolder:
        location += subfolder + '/'
    return location


def location_available(bucket_name, object_key):
    """
    Guarantee that we can write to the location of the object without overriding everything

    :param bucket_name: The bucket
    :param object_key: The object in the bucket
    :return: True if the object is not in the bucket, False if it is already in the bucket
    """
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(bucket_name)
    key = object_key
    objs = list(bucket.objects.filter(Prefix=key))
    if any([w.key == key for w in objs]):
        # exists
        # invert because unavailable
        return False
    else:
        # doesn't exist
        # invert because available
        return True


@prepare_test
def test_is_location_available(test_object_location=get_object_location(_random_alpha_string()),
                               test_bucket=TEST_BUCKET):
    try:
        isRandomLocationAvailable = location_available(bucket_name=test_bucket, object_key=test_object_location)
        return isRandomLocationAvailable
    except AssertionError as e:
        logger.error("location_available(): found a location that should not exist")
        logger.error(e)
        return False


# note: use this decorator only if the child function satisfies `test_object_location` in its arguments
@prepare_test
@prepare_test_random_object_location
def test_is_not_location_available(test_object_location, test_bucket=TEST_BUCKET):
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


def kg_files_in_location(bucket_name, object_location=''):
    bucket_listings = [e['Key']
                       for p in s3_client.get_paginator("list_objects_v2").paginate(Bucket=bucket_name)
                       for e in p['Contents']
                       ]
    # If object_location is the empty string, then each object
    # listed passes (since the empty string is part of every string)
    object_matches = [object_name for object_name in bucket_listings if object_location in object_name]
    return object_matches


# note: use this decorator only if the child function satisfies `test_object_location` in its arguments
@prepare_test
@prepare_test_random_object_location
def test_kg_files_in_location(test_object_location, test_bucket=TEST_BUCKET):
    try:
        kg_file_list = kg_files_in_location(bucket_name=test_bucket, object_location=test_object_location)
        print(kg_file_list)
        assert (len(kg_file_list) > 0)
    except AssertionError as e:
        raise AssertionError(e)
    return True


def get_kg_versions_available(bucket_name, kg_id=None):
    kg_files = kg_files_in_location(bucket_name)

    def kg_id_to_versions(kg_file):
        root_path = str(list(Path(kg_file).parents)[-2])  # get the root directory (not local/`.`)
        stem_path = str(Path(kg_file).name)

        entry_string = str(Path(kg_file))  # normalize delimiters
        for i in [root_path, stem_path, 'node', 'edge']:
            entry_string = entry_string.replace(i, '')

        import os
        kg_info = list(entry_string.split(os.sep))
        while '' in kg_info:
            kg_info.remove('')

        _kg_id = kg_info[0]
        _kg_version = kg_info[1]

        return _kg_id, _kg_version

    versions_per_kg = {}
    version_kg_pairs = set(kg_id_to_versions(kg_file) for kg_file in kg_files if kg_id and kg_file[0] is kg_id or True)

    import itertools
    for key, group in itertools.groupby(version_kg_pairs, lambda x: x[0]):
        versions_per_kg[key] = []
        for thing in group:
            versions_per_kg[key].append(thing[1])

    return versions_per_kg


@prepare_test
@prepare_test_random_object_location
def test_get_kg_versions_available(test_object_location, test_bucket=TEST_BUCKET):
    try:
        kg_version_map = get_kg_versions_available(bucket_name=test_bucket)
        print(kg_version_map)
        assert (kg_version_map is dict and len(kg_version_map) > 0)
    except AssertionError as e:
        raise AssertionError(e)
    return True


# TODO: clarify expiration time - default to 1 day (in seconds)
def create_presigned_url(bucket, object_key, expiration=86400):
    """Generate a pre-signed URL to share an S3 object

    :param bucket: string
    :param object_key: string
    :param expiration: Time in seconds for the pre-signed URL to remain valid
    :return: Presigned URL as string. If error, returns None.
    """

    # Generate a pre-signed URL for the S3 object
    # https://stackoverflow.com/a/52642792
    #
    # This may thrown a Boto related exception - assume that it will be catch by the caller
    response = s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': bucket, 'Key': object_key},
        ExpiresIn=expiration
    )

    # The response contains the pre-signed URL
    return response


@prepare_test
def test_create_presigned_url(test_bucket=TEST_BUCKET, test_kg_id=TEST_KG_NAME):
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


# https://gist.github.com/chipx86/9598b1e4a9a1a7831054
# TODO: disk or memory?
def compress_file_to_archive(in_filename, out_filename):
    class FileStream(object):
        def __init__(self):
            self.buffer = BytesIO()
            self.offset = 0

        def write(self, s):
            self.buffer.write(s)
            self.offset += len(s)

        def tell(self):
            return self.offset

        def close(self):
            self.buffer.close()

        def pop(self):
            s = self.buffer.getvalue()
            self.buffer.close()

            self.buffer = BytesIO()

            return s

    def stream_build_tar(_in_filename, _out_filename, streaming, BLOCK_SIZE=4096):

        tar = tarfile.TarFile.open(_out_filename, 'w|gz', streaming)

        stat = os.stat(_in_filename)

        tar_info = tarfile.TarInfo(Path(_in_filename).name)

        # Note that you can get this information from the storage backend,
        # but it's valid for either to raise a NotImplementedError, so it's
        # important to check.
        #
        # Things like the mode or ownership won't be available.
        tar_info.mtime = stat.st_mtime
        tar_info.size = stat.st_size

        # Note that we don't pass a fileobj, so we don't write any data
        # through addfile. We'll do this ourselves.
        tar.addfile(tar_info)

        yield

        with open(_in_filename, 'rb') as in_fp:
            total_size = 0

            while True:
                s = in_fp.read(BLOCK_SIZE)

                if len(s) > 0:
                    tar.fileobj.write(s)

                    yield

                if len(s) < BLOCK_SIZE:
                    blocks, remainder = divmod(tar_info.size, tarfile.BLOCKSIZE)

                    if remainder > 0:
                        tar.fileobj.write(tarfile.NUL *
                                          (tarfile.BLOCKSIZE - remainder))

                        yield

                        blocks += 1

                    tar.offset += blocks * tarfile.BLOCKSIZE
                    break

        tar.close()

        yield

    streaming_fp = FileStream()

    temp = tempfile.NamedTemporaryFile()
    for i in stream_build_tar(in_filename, temp.name, streaming_fp):
        s = streaming_fp.pop()

        if len(s) > 0:
            print('Writing {} bytes...'.format(len(s)))
            temp.write(s)
            temp.flush()
    print('Wrote tar file to {}'.format(temp.name))
    return temp


def kg_filepath(kg_id, kg_version, root='', subdir='', attachment=''):
    return Template("$ROOT/$KG_ID/$KG_VERSION$SUB_DIR$ATTACHMENT").substitute(
        ROOT=root,
        KG_ID=kg_id,
        KG_VERSION=kg_version,
        SUB_DIR=subdir + '/',
        ATTACHMENT=attachment
    )


def tardir(directory, name) -> str:
    logger.error("Calling tardir(directory='"+directory+"', name='"+name+"')")
    raise RuntimeError("Not yet implemented!")


@prepare_test
def test_tardir():
    try:
        tar_path = tardir(TEST_FILE_DIR, 'TestData')
        assert (len(tarfile.open(tar_path).getmembers()) > 0)
    except FileNotFoundError as e:
        logger.error("Test is malformed!")
        logger.error(e)
        return False
    except AssertionError as e:
        logger.error('The packaging function failed to create a valid tarfile!')
        logger.error(e)
        return False
    return True


def package_file_manifest(tar_path):
    with tarfile.open(tar_path, 'r|gz') as tar:
        manifest = dict()
        for tarinfo in tar:
            print("\t", tarinfo.name, "is", tarinfo.size, "bytes in size and is ", end="")
            if tarinfo.isreg():
                print("a regular file.")
            elif tarinfo.isdir():
                print("a directory.")
            else:
                print("something else.")
            manifest[tarinfo.name] = {
                "raw": tarinfo,
                "name": tarinfo.name,
                "type": tarinfo.type,
                "size": tarinfo.size
            }
        return manifest


@prepare_test
def test_package_manifest(test_bucket=TEST_BUCKET, test_kg=TEST_KG_NAME):
    try:
        with open(abspath(TEST_FILE_DIR + TEST_FILE_NAME), 'rb') as test_file:
            tar_path = tardir(Path(test_file.name).parent, Path(test_file.name).stem)
            manifest = package_file_manifest(tar_path)
            assert (len(manifest) > 0)
    except AssertionError as e:
        logger.error('The manifest failed to be created properly (since we have files in the testfiles directory)')
        logger.error(e)
        return False
    return True


def upload_file(data_file, file_name, bucket, object_location, config=None):
    """Upload a file to an S3 bucket

    :param data_file: File to upload (can be read in binary mode)
    :param file_name: Filename to use
    :param bucket: Bucket to upload to
    :param object_location: root S3 object location name.
    :return: True if file was uploaded, else False
    """
    object_key = Template('$ROOT$FILENAME$EXTENSION').substitute(
        ROOT=object_location,
        FILENAME=Path(file_name).stem,
        EXTENSION=splitext(file_name)[1]
    )

    # Upload the file
    try:
        if config is None:
            s3_client.upload_fileobj(data_file, bucket, object_key)
        else:
            s3_client.upload_fileobj(data_file, bucket, object_key, Config=config)
    except Exception as exc:
        logger.error("kgea file ops: upload_file() exception: " + str(exc))
        raise exc

    return object_key


def upload_file_multipart(data_file, file_name, bucket, object_location, metadata=None):
    """Upload a file to an S3 bucket. Use multipart protocols.
    Multipart transfers occur when the file size exceeds the value of the multipart_threshold attribute
    :param data_file: File to upload
    :param file_name: Name of file to upload
    :param bucket: Bucket to upload to
    :param object_location: S3 object name
    """

    """
    Multipart file upload configuration

    Test Values:
    MP_THRESHOLD = 10
    MP_CONCURRENCY = 5
    """
    MP_THRESHOLD = 10
    MP_CHUNK = 8  # MPU threshold 8 MB at a time for production AWS transfers
    MP_CONCURRENCY = 5

    KB = 1024
    MB = KB * KB
    GB = MB ** 3

    mp_threshold = MP_THRESHOLD * MB
    mp_chunk = MP_CHUNK * MB
    concurrency = MP_CONCURRENCY

    transfer_config = boto3.s3.transfer.TransferConfig(
        multipart_threshold=mp_threshold,
        multipart_chunksize=mp_chunk,
        use_threads=True,
        max_concurrency=concurrency
    )

    return upload_file(data_file, file_name, bucket, object_location, config=transfer_config)


def package_file(name: str, target_file):
    logger.error("Calling package_file(name='"+name+"', name='"+target_file+"')")
    raise RuntimeError("Not yet implemented!")


@prepare_test
def test_upload_file(test_bucket=TEST_BUCKET, test_kg=TEST_KG_NAME):
    try:
        # NOTE: file must be read in binary mode!
        with open(abspath(TEST_FILE_DIR + TEST_FILE_NAME), 'rb') as test_file:
            content_location, _ = with_version(get_object_location)(test_kg)
            packaged_file = package_file(name=test_file.name, target_file=test_file)
            object_key = upload_file(packaged_file, test_file.name, test_bucket, content_location)
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


@prepare_test
def test_upload_file_multipart(test_bucket=TEST_BUCKET, test_kg=TEST_KG_NAME):
    try:

        # NOTE: file must be read in binary mode!
        with open(abspath(TEST_FILE_DIR + TEST_FILE_NAME), 'rb') as test_file:
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


def upload_file_as_archive(data_file, file_name, bucket, object_location, metadata=None):
    """
    Upload function into archive

    * If the archive doesn't exist => create it
    * If the archive exists => compress into the existing file

    :param data_file:
    :param file_name:
    :param bucket:
    :param object_location:
    :param metadata:
    :return:
    """

    archive_name = "{}.tar.gz".format(Path(file_name).stem)
    with compress_file_to_archive(data_file.name, archive_name) as archive:
        return upload_file_multipart(
            archive,
            archive_name,
            bucket,
            object_location,
            metadata
        )


@prepare_test
def test_upload_file_as_archive(test_bucket=TEST_BUCKET, test_kg=TEST_KG_NAME):
    try:

        # NOTE: file must be read in binary mode!
        with open(abspath(TEST_FILE_DIR + TEST_FILE_NAME), 'rb') as test_file:
            content_location, _ = with_version(get_object_location)(test_kg)
            object_key = upload_file_as_archive(test_file, test_file.name, test_bucket, content_location)
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


def upload_file_to_archive(archive_name, data_file, file_name, bucket, object_location):
    # upload the file
    object_key = upload_file_multipart(data_file, file_name, bucket, object_location)

    archive_path = "{}/{}.tar.gz".format(
        Path(object_key).parent,
        archive_name,
    ).replace('\\', '/')

    # setup an S3 job to compress the file
    job = S3Tar(
        bucket,
        archive_path,
        allow_dups=True
    )

    # add the file the running archive
    job.add_file(object_key)

    # execute the job
    job.tar()

    return archive_path


@prepare_test
def test_upload_file_to_archive(test_bucket=TEST_BUCKET, test_kg=TEST_KG_NAME):
    """
    The difference between "upload_file_to_archive" and "upload_file_as_archive":
        * upload_file_to_archive can upload several files into an archive AT ONCE.
        * TODO: upload_file_to_archive can upload several files into an archive OVER TIME.
            * Problem: Gzip compression is non-commutative!
    """
    try:
        # Prepare information used between subtests
        TEST_ARCHIVE_NAME = _random_alpha_string()  # the stem for the filename of the archive
        CONTENT_LOCATION, _ = with_version(get_object_location)(test_kg)

        """
        Test 1: Writing files into new archive
        """
        print('\ttesting 1')
        with open(abspath(TEST_FILE_DIR + TEST_FILE_NAME), 'rb') as test_file:
            """
            Test 1a: Write a file to an archive
            """
            archive_key = upload_file_to_archive(
                TEST_ARCHIVE_NAME,
                test_file,
                test_file.name,
                test_bucket,
                CONTENT_LOCATION
            )

            """
            Test 1b: override file 
            """
            # concatenate random string to the file

        print('\ttesting 1 successful')

        """
        Test 2: Writing a new file into the same archive
        """
        print('\ttesting 2')
        with tempfile.NamedTemporaryFile() as test_file:

            test_file.write(bytes(_random_alpha_string(), "UTF-8"))

            archive_key = upload_file_to_archive(
                TEST_ARCHIVE_NAME,
                test_file,
                test_file.name,
                test_bucket,
                CONTENT_LOCATION
            )

            # ASSERT: Archive exists
            assert (archive_key in kg_files_in_location(test_bucket, CONTENT_LOCATION))

        print('\ttesting 2 successful')

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


@prepare_test
def test_upload_file_timestamp(test_bucket=TEST_BUCKET, test_kg=TEST_KG_NAME):
    """
    Use the "with_version" wrapper to modify the object location
    """
    try:

        test_location, time_created = with_version(get_object_location)(test_kg)
        # NOTE: file must be read in binary mode!
        with open(abspath(TEST_FILE_DIR + TEST_FILE_NAME), 'rb') as test_file:
            object_key = upload_file(test_file, test_file.name, test_bucket, test_location)
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


def infix_string(name, infix, delimiter="."):
    tokens = name.split(delimiter)
    *pre_name, end_name = tokens
    name = ''.join([delimiter.join(pre_name), infix, delimiter, end_name])
    return name


def download_file(bucket, object_key, open_file=False):
    download_url = create_presigned_url(bucket=bucket, object_key=object_key)
    if open_file:
        return download_url, webbrowser.open_new_tab(download_url)
    return download_url


async def compress_download(bucket, object_key, open_file=False):
    archive_path = "{}archive/{}.tar.gz".format(
        object_key,
        Path(object_key).stem,
    ).replace('\\', '/')

    # setup an S3 job to compress the file
    job = S3Tar(
        bucket,
        archive_path,
        allow_dups=True,
    )
    # add the file the running archive
    print(kg_files_in_location(bucket, object_key))
    job.add_files(object_key)
    # execute the job
    job.tar()

    return download_file(bucket, archive_path, open_file)


@prepare_test
# @prepare_test_random_object_location
def test_download_file(test_object_location=None, test_bucket=TEST_BUCKET, test_kg_id=TEST_KG_NAME):
    try:
        with open(abspath(TEST_FILE_DIR + TEST_FILE_NAME), 'rb') as test_file:
            object_key = upload_file(test_file, test_file.name, test_bucket, get_object_location(test_kg_id))
            url = download_file(
                bucket=test_bucket,
                object_key=get_object_location(test_kg_id) + TEST_FILE_NAME,
                open_file=False
            )  # open_file=False to affirm we won't trigger a browser action
            print(url)
            response = requests.get(url)
            assert (response.status_code == 200)
            # TODO: test for equal content from download response
    except FileNotFoundError as e:
        logger.error("Test is malformed!")
        logger.error(e)
        return False
    except AssertionError as e:
        logger.error('URL is not returning a downloadable resource (response code is not 200)')
        logger.error(e)
        return False
    return True


def _load_s3_text_file(bucket_name: str, object_name: str, mode: str = 'text') -> Union[None, bytes, str]:
    """
    Given an S3 object key name, load the specific file.
    The return value defaults to being decoded from utf-8 to a text string.
    Return None the object is inaccessible.
    """
    data_string: Union[None, bytes, str] = None

    try:
        mf = io.BytesIO()
        s3 = boto3.client('s3')
        s3.download_fileobj(
            bucket_name,
            object_name,
            mf
        )
        data_bytes = mf.getvalue()
        mf.close()
        if mode == 'text':
            data_string = data_bytes.decode('utf-8')
    except Exception as e:
        logger.error('ERROR: _load_s3_text_file(): '+str(e))

    return data_string


def get_archive_contents(bucket_name: str) -> Dict[str, Dict[str,  Union[str, List]]]:
    """
    Get contents of KGE Archive from the
    AWS S3 bucket folder names and metadata file contents.

    :param bucket_name: The bucket
    :return: annotated KGE File Set, enumerated from the AWS S3 repository
    """
    all_files = kg_files_in_location(bucket_name=bucket_name)

    contents: Dict[
        str,   # kg_id's of every KGE archived knowledge graph
        Dict[
            str,  # tags 'metadata' and 'versions'
            Union[
                str,   # 'metadata' field value: kg specific text file blob from S3
                Dict[
                    str,  # kg_version's of versioned KGE File Sets for a kg
                    List[str]  # list of data files in a given KGE File Set
                ]
            ]
        ]
    ] = dict()

    for file_path in all_files:

        file_part = file_path.split('/')

        if file_part[0] != _KGEA_APP_CONFIG['archive-directory']:
            # ignore things that don't look like the KGE File Set archive folder
            continue

        kg_id = file_part[1]
        if kg_id not in contents:
            # each Knowledge Graph may have high level 'metadata'
            # obtained from a kg_id specific PROVIDER_METADATA_FILE
            # plus one or more versions of KGE File Set
            contents[kg_id] = dict()  # dictionary of kg's, indexed by kg_id
            contents[kg_id]['versions'] = dict()  # dictionary of versions, indexed by kg_version

        if file_part[2] == PROVIDER_METADATA_FILE:
            # Get the provider 'kg_id' associated metadata file just stored
            # as a blob of text, for content parsing by the function caller
            # Unlike the kg_id versions, there should only be one such file?
            contents[kg_id]['metadata'] = \
                _load_s3_text_file(
                    bucket_name=bucket_name,
                    object_name=file_path
                )
        else:
            # otherwise, assume file_part[2] is a 'version folder'
            kg_version = file_part[2]
            if kg_version not in contents[kg_id]['versions']:
                contents[kg_id]['versions'][kg_version] = list()

            # simple first iteration just records the list of data file paths
            # (other than the PROVIDER_METADATA_FILE)
            # TODO: how should subfolders (i.e. 'nodes' and 'edges') be handled?
            contents[kg_id]['versions'][kg_version].append(file_path)

    return contents


@prepare_test
def test_get_archive_contents(test_bucket=TEST_BUCKET):
    print("\ntest_get_archive_contents() test output:\n", file=stderr)
    contents = get_archive_contents(test_bucket)
    print(str(contents), file=stderr)


"""
Unit Tests
* Run each test function as an assertion if we are debugging the project
"""


def run_test(test_func):
    try:
        start = time.time()
        assert (test_func())
        end = time.time()
        print("{} passed: {} seconds".format(test_func.__name__, end - start))
    except Exception as e:
        logger.error("{} failed!".format(test_func.__name__))
        logger.error(e)


if __name__ == '__main__':

    import sys
    import os

    args = sys.argv[1:]
    if len(args) == 2 and args[0] == '--testFile':
        TEST_FILE_NAME = args[1]
        print(TEST_FILE_NAME, os.path.getsize(abspath(TEST_FILE_DIR + TEST_FILE_NAME)), 'bytes')

    print(
        "Test Preconditions:\n\t{} {}\n\t{} {}\n\t{} {}\n\t{} {}".format(
            "TEST_BUCKET", TEST_BUCKET,
            "TEST_KG_NAME", TEST_KG_NAME,
            "TEST_FILE_DIR", TEST_FILE_DIR,
            "TEST_FILE_NAME", TEST_FILE_NAME
        )
    )

    run_test(test_kg_files_in_location)
    run_test(test_is_location_available)
    run_test(test_is_not_location_available)
    run_test(test_get_kg_versions_available)
    run_test(test_create_presigned_url)

    # run_test(test_tardir)
    # run_test(test_package_manifest)

    # run_test(test_upload_file_multipart)
    # run_test(test_upload_file_as_archive)

    run_test(test_upload_file_to_archive)
    run_test(test_download_file)

    run_test(test_get_archive_contents)

    print("tests complete")
