"""
Implement robust KGE File Set upload process:
o  “layered” back end unit tests of each level of S3 upload process
o  Figure out the minimal S3 access policy that suffices for the KGE Archive
o  File set versioning using time stamps
o  Web server optimization (e.g. NGINX / WSGI / web application parameters)
o  Test the system (both manually, by visual inspection of uploads)
Stress test using SRI SemMedDb: https://github.com/NCATSTranslator/semmeddb-biolink-kg
"""

from os import sep as os_separator
from os.path import dirname, abspath, splitext
import io
import traceback
from sys import stderr, exc_info
from tempfile import TemporaryFile
from typing import Dict, Union, List, Optional
import subprocess

import logging

import random
import time

import requests
import smart_open
from datetime import datetime

from pathlib import Path
import tarfile

from validators import ValidationFailure, url as valid_url

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

from botocore.config import Config
from boto3.s3.transfer import TransferConfig

from kgea.aws.assume_role import AssumeRole

from kgea.config import (
    get_app_config,
    PROVIDER_METADATA_FILE,
    FILE_SET_METADATA_FILE
)

logger = logging.getLogger(__name__)

# Opaquely access the configuration dictionary
_KGEA_APP_CONFIG = get_app_config()

# Probably won't change the name of the
# script again, but changed once already...
_KGEA_ARCHIVER_SCRIPT = "kge_archiver.bash"


def print_error_trace(err_msg: str):
    """
    Print Error Exception stack
    """
    logger.error(err_msg)
    exc_type, exc_value, exc_traceback = exc_info()
    traceback.print_exception(exc_type, exc_value, exc_traceback, file=stderr)


#
# Obtain an AWS S3 Client using an Assumed IAM Role
# with default parameters (loaded from config.yaml)
#
the_role = AssumeRole()


def s3_client(
        assumed_role=the_role,
        config=Config(
            signature_version='s3v4',
            region_name=_KGEA_APP_CONFIG['aws']['s3']['region']
        )
):
    """

    :param assumed_role:
    :param config:
    :return:
    """
    return assumed_role.get_client('s3', config=config)


def s3_resource(assumed_role=the_role):
    """

    :param assumed_role:
    :return:
    """
    return assumed_role.get_resource(
        's3',
        region_name=_KGEA_APP_CONFIG['aws']['s3']['region']
    )


def create_location(bucket, kg_id):
    """

    :param bucket:
    :param kg_id:
    :return:
    """
    return s3_client().put_object(Bucket=bucket, Key=get_object_location(kg_id))


def delete_location(bucket, kg_id):
    """

    :param bucket:
    :param kg_id:
    :return:
    """
    return s3_client().delete(Bucket=bucket, Key=get_object_location(kg_id))


# https://www.askpython.com/python/examples/generate-random-strings-in-python
def random_alpha_string(length=8):
    """

    :param length:
    :return:
    """
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


def get_object_location(kg_id):
    """
    NOTE: Must be kept deterministic. No date times or
    randomness in this method; they may be appended afterwards.
    """
    location = f"{_KGEA_APP_CONFIG['aws']['s3']['archive-directory']}/{kg_id}/"
    return location


def get_default_date_stamp():
    """
    Returns the default date stamp as 'now', as an ISO Format string 'YYYY-MM-DD'
    :return:
    """
    return datetime.now().strftime('%Y-%m-%d')


# Don't use date stamp for versioning anymore
def with_version(func, version="1.0"):
    """

    :param func:
    :param version:
    :return:
    """
    def wrapper(kg_id):
        """

        :param kg_id:
        :return:
        """
        return func(kg_id + '/' + version), version

    return wrapper


def with_subfolder(location: str, subfolder: str):
    """

    :param location:
    :param subfolder:
    :return:
    """
    if subfolder:
        location += subfolder + '/'
    return location


def get_object_from_bucket(bucket_name, object_key):
    """

    :param bucket_name:
    :param object_key:
    :return:
    """
    bucket = s3_resource().Bucket(bucket_name)
    return bucket.Object(object_key)


def match_objects_from_bucket(bucket_name, object_key):
    """

    :param bucket_name:
    :param object_key:
    :return:
    """
    bucket = s3_resource().Bucket(bucket_name)
    key = object_key
    objs = list(bucket.objects.filter(Prefix=key))
    return [w.key == key for w in objs]


def object_key_exists(object_key, bucket_name=_KGEA_APP_CONFIG['aws']['s3']['bucket']) -> bool:
    """
    Checks for the existence of the specified object key

    :param bucket_name: The bucket
    :param object_key: Target object key in the bucket
    :return: True if the object is in the bucket, False if it is not in the bucket (False also if empty object key)
    """
    if not object_key:
        return False
    return any(match_objects_from_bucket(bucket_name, object_key))


def location_available(bucket_name, object_key) -> bool:
    """
    Predicate to guarantee that we can write to the
    location of the object without overriding everything.

    :param bucket_name: The bucket
    :param object_key: The object in the bucket
    :return: True if the object is not in the bucket, False if it is already in the bucket
    """
    if object_key_exists(object_key, bucket_name):
        # exists
        # invert because object key location is unavailable
        return False
    else:
        # doesn't exist
        # invert because object key location is available
        return True


def kg_files_in_location(bucket_name, object_location='') -> List[str]:
    """

    :param bucket_name:
    :param object_location:
    :return:
    """
    bucket_listings: List = list()
    # print(s3_client().get_paginator("list_objects_v2").paginate(Bucket=bucket_name))
    for p in s3_client().get_paginator("list_objects_v2").paginate(Bucket=bucket_name):
        if 'Contents' in p:
            for e in p['Contents']:
                bucket_listings.append(e['Key'])
        else:
            return []  # empty bucket?

    # If object_location is the empty string, then each object
    # listed passes (since the empty string is part of every string)
    object_matches = [object_name for object_name in bucket_listings if object_location in object_name]
    return object_matches


def get_fileset_versions_available(bucket_name, kg_id=None):
    """
    A roster of all the versions that all knowledge graphs have been updated to.

    Input:
        - A list of object keys in S3 encoding knowledge graph objects
    Output:
        - A map of knowledge graph names to a list of their versions
    Tasks:
        - Extract the version from the knowledge graph path
        - Reduce the versions by knowledge graph name (a grouping)
        - Filter out crud data (like NoneTypes) to guarantee portability between server and client

    :param bucket_name:
    :param kg_id:
    :return versions_per_kg: dict
    """
    kg_files = kg_files_in_location(bucket_name)

    def kg_id_to_versions(kg_file):
        """

        :param kg_file:
        :return:
        """
        root_path = str(list(Path(kg_file).parents)[-2])  # get the root directory (not local/`.`)
        stem_path = str(Path(kg_file).name)
    
        entry_string = str(Path(kg_file))  # normalize delimiters
        for i in [root_path, stem_path, 'node', 'edge']:
            entry_string = entry_string.replace(i, '')

        kg_info = list(entry_string.split(os_separator))
        while '' in kg_info:
            kg_info.remove('')
    
        _kg_id = kg_info[0]
        _fileset_version = kg_info[1]
    
        return _kg_id, _fileset_version

    versions_per_kg = {}
    version_kg_pairs = set(
        kg_id_to_versions(kg_file) for kg_file in kg_files if kg_id and kg_file[0] is kg_id or True)

    import itertools
    for key, group in itertools.groupby(version_kg_pairs, lambda x: x[0]):
        versions_per_kg[key] = []
        for thing in group:
            versions_per_kg[key].append(thing[1])
    
    return versions_per_kg


# TODO: clarify expiration time - default to 1 day (in seconds)
def create_presigned_url(bucket, object_key, expiration=86400) -> Optional[str]:
    """Generate a pre-signed URL to share an S3 object

    :param bucket: string
    :param object_key: string
    :param expiration: Time in seconds for the pre-signed URL to remain valid
    :return: Presigned URL as string. If error, returns None.
    """

    # Generate a pre-signed URL for the S3 object
    # https://stackoverflow.com/a/52642792
    #
    # This may thrown a Boto related exception - assume that it will be caught by the caller
    #
    try:
        endpoint = s3_client().generate_presigned_url(
            ClientMethod='get_object',
            Params={
                'Bucket': bucket,
                'Key': object_key,
                'ResponseContentDisposition': 'attachment',
            },
            ExpiresIn=expiration
        )
    except Exception as e:
        logger.error("create_presigned_url() error: "+str(e))
        return None

    # The endpoint contains the pre-signed URL
    return endpoint


def kg_filepath(kg_id, fileset_version, root='', subdir='', attachment=''):
    """

    :param kg_id:
    :param fileset_version:
    :param root:
    :param subdir:
    :param attachment:
    :return:
    """
    return f"{root}/{kg_id}/{fileset_version}{subdir + '/'}{attachment}"


# def package_file_manifest(tar_path):
#     """
#
#     :param tar_path:
#     :return:
#     """
#     with tarfile.open(tar_path, 'r|gz') as tar:
#         manifest = dict()
#         for tarinfo in tar:
#             print("\t", tarinfo.name, "is", tarinfo.size, "bytes in size and is ", end="")
#             if tarinfo.isreg():
#                 print("a regular file.")
#             elif tarinfo.isdir():
#                 print("a directory.")
#             else:
#                 print("something else.")
#             manifest[tarinfo.name] = {
#                 "raw": tarinfo,
#                 "name": tarinfo.name,
#                 "type": tarinfo.type,
#                 "size": tarinfo.size
#             }
#         return manifest


def get_pathless_file_size(data_file):
    """
    Takes an open file-like object, gets its end location (in bytes),
    and returns it as a measure of the file size.

    Traditionally, one would use a systems-call to get the size
    of a file (using the `os` module). But `TemporaryFileWrapper`s
    do not feature a location in the filesystem, and so cannot be
    tested with `os` methods, as they require access to a filepath,
    or a file-like object that supports a path, in order to work.

    This function seeks the end of a file-like object, records
    the location, and then seeks back to the beginning so that
    the file behaves as if it was opened for the first time.
    This way you can get a file's size before reading it.

    (Note how we aren't using a `with` block, which would close
    the file after use. So this function leaves the file open,
    as an implicit non-effect. Closing is problematic for
     TemporaryFileWrappers which wouldn't be operable again)

    :param data_file:
    :return size:
    """
    if not data_file.closed:
        data_file.seek(0, 2)
        size = data_file.tell()
        print(size)
        data_file.seek(0, 0)
        return size
    else:
        return 0


def get_object_key(object_location, filename):
    """
    :param object_location: S3 location of the persisted object
    :param filename: filename of the S3 object
    :return: object key of the S3 object
    """
    return f"{object_location}{Path(filename).stem}{splitext(filename)[1]}"


def upload_file(bucket, object_key, source, client=s3_client(), config=None, callback=None):
    """Upload a file to an S3 bucket

    :param bucket: Bucket to upload to
    :param object_key: target S3 object key of the file.
    :param source: file to be uploaded (can be read in binary mode)
    :param client: The s3 client to use. Useful if needing to make a new client for the sake of thread safety.
    :param config: a means of configuring the network call
    :param callback: an object that implements __call__, that runs on each file block uploaded (receiving byte data.)

    :raises RuntimeError if the S3 file object upload call fails
    """
    
    # Upload the file
    try:
        # TODO: how can these upload calls be aborted, especially, if they are multi-part uploads?
        #       Maybe we need to use lower level multi-part upload functions here? What if the file is small?
        if config is None:
            client.upload_fileobj(source, bucket, object_key, Callback=callback)
        else:
            client.upload_fileobj(source, bucket, object_key, Config=config, Callback=callback)
    except Exception as exc:
        logger.warning("kgea_file_ops.upload_file(): " + str(exc))
        # TODO: what sort of post-cancellation processing is needed here?


def upload_file_multipart(
        data_file,
        file_name,
        bucket,
        object_location,
        metadata=None,
        callback=None,
        client=s3_client()
):
    """Upload a file to an S3 bucket. Use multipart protocols.
    Multipart transfers occur when the file size exceeds the value of the multipart_threshold attribute

    :param data_file: File to upload
    :param file_name: Name of file to upload
    :param bucket: Bucket to upload to
    :param object_location: S3 object name
    :param metadata: metadata associated with the file
    :param callback: Callable to track number of bytes being uploaded
    :param client: The s3 client to use. Useful if needing to make a new client for the sake of thread safety.
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
    # GB = MB ** 3

    mp_threshold = MP_THRESHOLD * MB
    mp_chunk = MP_CHUNK * MB
    concurrency = MP_CONCURRENCY

    transfer_config = TransferConfig(
        multipart_threshold=mp_threshold,
        multipart_chunksize=mp_chunk,
        use_threads=True,
        max_concurrency=concurrency
    )
    object_key = get_object_key(object_location, file_name)
    upload_file(
        bucket=bucket,
        object_key=object_key,
        source=data_file,
        client=client,
        config=transfer_config,
        callback=callback
    )
    return object_key


def infix_string(name, infix, delimiter="."):
    """

    :param name:
    :param infix:
    :param delimiter:
    :return:
    """
    tokens = name.split(delimiter)
    *pre_name, end_name = tokens
    name = ''.join([delimiter.join(pre_name), infix, delimiter, end_name])
    return name


async def compress_fileset(
    kg_id,
    version,
    bucket,
    root='kge-data'
) -> str:
    """

    :param kg_id:
    :param version:
    :param bucket:
    :param root:
    :return:
    """
    s3_archive_key = f"s3://{bucket}/{root}/{kg_id}/{version}/archive/{kg_id+'_'+version}.tar.gz"
    logger.info(f"Initiating execution of compress_fileset({s3_archive_key})")
    
    archive_script = f"{dirname(abspath(__file__))}{os_separator}'scripts'{os_separator}{_KGEA_ARCHIVER_SCRIPT}"
    logger.debug(f"Archive Script: ({archive_script})")
    try:
        script_log = TemporaryFile()
        with subprocess.Popen(
            args=[
                archive_script,
                kg_id,
                version
            ],
            stdout=script_log,
            stderr=script_log
        ) as proc:
            proc.wait()
            script_log.flush()
            log_text = script_log.read()
            logger.info(
                f"Finished running {_KGEA_ARCHIVER_SCRIPT}\n\tto build {s3_archive_key}: " +
                f"\n\tReturn Code {proc.returncode}, log:\n\t{log_text}"
            )
            script_log.close()
    except Exception as e:
        logger.error(f"compress_fileset({s3_archive_key}): exception {str(e)}")
    
    logger.info(f"Exiting compress_fileset({s3_archive_key})")
    return s3_archive_key


def decompress_in_place(gzipped_key, location=None):
    """

    :param gzipped_key:
    :param location:
    :return:
    """
    if location is None:
        location = '/'.join(gzipped_key.split('/')[:-1])+'/'
    tarfile_location = f"s3://{_KGEA_APP_CONFIG['aws']['s3']['bucket']}/{gzipped_key}"
    file_entries = []

    # one step decompression - use the tarfile library's ability
    # to open gzip files transparently to avoid gzip+tar step
    with smart_open.open(tarfile_location, 'rb', compression="disable") as fd:
        with tarfile.open(fileobj=fd, mode='r:gz') as tf:
            for entry in tf:  # list each entry one by one
                fileobj = tf.extractfile(entry)
                s3_client().upload_fileobj(  # upload a new obj to s3
                    Fileobj=io.BytesIO(fileobj.read()),
                    Bucket=_KGEA_APP_CONFIG['aws']['s3']['bucket'],  # target bucket, writing to
                    Key=location+entry.name
                )
                file_entries.append({
                    "file_type": "KGX data file",
                    "file_name": entry.name,
                    "file_size": entry.size,
                    # TODO deal with import circularities: reorganize the project
                    "object_key": location+entry.name,
                    "s3_file_url": '',
                })
    return file_entries


def aggregate_files(bucket, target_folder, target_name, file_object_keys, match_function=lambda x: True) -> str:
    """
    Aggregates files matching a match_function.

    :param bucket:
    :param target_folder:
    :param target_name:
    :param file_object_keys:
    :param match_function:
    :return:
    """
    if not file_object_keys:
        return ''
    
    agg_path = f"s3://{bucket}/{target_folder}/{target_name}"
    with smart_open.open(agg_path, 'w', encoding="utf-8", newline="\n") as aggregated_file:
        file_object_keys = filter(match_function, file_object_keys)
        for file_object_key in file_object_keys:
            target_key_uri = f"s3://{_KGEA_APP_CONFIG['aws']['s3']['bucket']}/{file_object_key}"
            with smart_open.open(target_key_uri, 'r', encoding="utf-8", newline="\n") as subfile:
                for line in subfile:
                    aggregated_file.write(line)
                aggregated_file.write("\n")
                
    return agg_path


def load_s3_text_file(bucket_name: str, object_name: str, mode: str = 'text') -> Union[None, bytes, str]:
    """
    Given an S3 object key name, load the specific file.
    The return value defaults to being decoded from utf-8 to a text string.
    Return None the object is inaccessible.
    """
    data_string: Union[None, bytes, str] = None

    try:
        mf = io.BytesIO()
        s3_client().download_fileobj(
            bucket_name,
            object_name,
            mf
        )
        data_bytes = mf.getvalue()
        mf.close()
        if mode == 'text':
            data_string = data_bytes.decode('utf-8')
    except Exception as e:
        logger.error('ERROR: _load_s3_text_file(): ' + str(e))

    return data_string


def get_archive_contents(bucket_name: str) -> \
        Dict[
            str,  # kg_id's of every KGE archived knowledge graph
            Dict[
                str,  # tags 'metadata' and 'versions'
                Union[
                    str,  # 'metadata' field value: kg specific 'provider' text file blob from S3
                    Dict[
                        str,  # fileset_version's of versioned KGE File Sets for a kg
                        Dict[
                            str,  # tags 'metadata' and 'file_object_keys'
                            Union[
                                str,  # 'metadata' field value: 'file set' specific text file blob from S3
                                List[str]  # list of data files in a given KGE File Set
                            ]
                        ]
                    ]
                ]
            ]
        ]:
    """
    Get contents of KGE Archive from the
    AWS S3 bucket folder names and metadata file contents.

    :param bucket_name: The bucket
    :return: multi-level catalog of KGE knowledge graphs and associated versioned file sets from S3 storage
    """
    all_files = kg_files_in_location(bucket_name=bucket_name)

    contents: Dict[
        str,  # kg_id's of every KGE archived knowledge graph
        Dict[
            str,  # tags 'metadata' and 'versions'
            Union[
                str,  # 'metadata' field value: kg specific 'provider' text file blob from S3
                Dict[
                    str,  # fileset_version's of versioned KGE File Sets for a kg
                    Dict[
                        str,  # tags 'metadata' and 'file_object_keys'
                        Union[
                            str,  # 'metadata' field value: 'file set' specific text file blob from S3
                            List[str]  # list of data file object keys in a given KGE File Set
                        ]
                    ]
                ]
            ]
        ]
    ] = dict()

    for file_path in all_files:

        file_part = file_path.split('/')
        if len(file_part) > 0:
            if file_part[0] != _KGEA_APP_CONFIG['aws']['s3']['archive-directory']:
                # ignore things that don't look like the KGE File Set archive folder
                continue
        if file_part[0] != _KGEA_APP_CONFIG['aws']['s3']['archive-directory']:
            # ignore things that don't look like the KGE File Set archive folder
            continue

        kg_id = file_part[1]
        if kg_id not in contents:
            # each Knowledge Graph may have high level 'metadata'
            # obtained from a kg_id specific PROVIDER_METADATA_FILE
            # plus one or more versions of KGE File Set
            contents[kg_id] = dict()  # dictionary of kg's, indexed by kg_id
            contents[kg_id]['versions'] = dict()  # dictionary of versions, indexed by fileset_version

        if file_part[2] == PROVIDER_METADATA_FILE:
            # Get the provider 'kg_id' associated metadata file just stored
            # as a blob of text, for content parsing by the function caller
            # Unlike the kg_id versions, there should only be one such file?
            contents[kg_id]['metadata'] = \
                load_s3_text_file(
                    bucket_name=bucket_name,
                    object_name=file_path
                )
            # we ignore this file in the main versioned file list
            # since it is global to the knowledge graph.  In fact,
            # sometimes, the fileset_version may not yet be properly set!
            continue
            
        else:
            # otherwise, assume file_part[2] is a 'version folder'
            fileset_version = file_part[2]
            if fileset_version not in contents[kg_id]['versions']:
                contents[kg_id]['versions'][fileset_version] = dict()
                contents[kg_id]['versions'][fileset_version]['file_object_keys'] = list()
            
            # if the fileset versioned object key is not empty?
            if len(file_part) >= 4:
                if file_part[3] == FILE_SET_METADATA_FILE:
                    # Get the provider 'kg_id' associated metadata file just stored
                    # as a blob of text, for content parsing by the function caller
                    # Unlike the kg_id versions, there should only be one such file?
                    contents[kg_id]['versions'][fileset_version]['metadata'] = \
                        load_s3_text_file(
                            bucket_name=bucket_name,
                            object_name=file_path
                        )
                    continue

                # simple first iteration just records the list of data file paths
                # (other than the PROVIDER_METADATA_FILE and FILE_SET_METADATA_FILE)
                # TODO: how should subfolders (i.e. 'nodes' and 'edges') be handled?
                contents[kg_id]['versions'][fileset_version]['file_object_keys'].append(file_path)
    return contents


def get_url_file_size(url: str) -> int:
    """
    Takes a URL specified resource, and gets its size (in bytes)

    :param url: resource whose size is being queried
    :return size:
    """
    size: int = 0
    if url:
        try:
            assert (valid_url(url))

            # fetching the header information
            info = requests.head(url)
            content_length = info.headers['Content-Length']
            size: int = int(content_length)
            return size
        except ValidationFailure:
            logger.error(f"get_url_file_size(url: '{str(url)}') is invalid?")
            return -2
        except KeyError:
            logger.error(f"get_url_file_size(url: '{str(url)}') doesnt have a 'Content-Length' value in its header?")
            return -3
        except Exception as exc:
            logger.error(f"get_url_file_size(url:'{str(url)}'): {str(exc)}")
            # TODO: invalidate the size invariant to propagate a call error
            # for now return -1 to encode the error state
            return -1

    return size


def upload_from_link(
        bucket,
        object_key,
        source,
        client=s3_client(),
        callback=None
):
    """
    Transfers a file resource to S3 from a URL location.

    :param bucket: in S3
    :param object_key: of target S3 object
    :param source: url of resource to be uploaded to S3
    :param callback: e.g. progress monitor
    :param client: for S3
    """

    # make sure we're getting a valid url
    assert(valid_url(source))

    # this will use the smart_open http client (given that `source` is a full url)
    """
    Explaining the arguments for smart_open
    * encoding - utf-8 to get rid of encoding errors
    * compression - smart_open opens tar.gz files by default; unnecessary, maybe cause slowdown with big files.
    * transport_params - modifying the headers will let us pick an optimal mimetype for transfer
    
    The block is written in a way that tries to minimize blocking access to the requests and files, instead opting
    to stream the data into `s3` bytewise. It tries to reduce extraneous steps at the library and protocol levels.
    """
    try:
        with smart_open.open(
                source,
                'r',
                compression='disable',
                encoding="utf8",
                transport_params={
                    'headers': {
                        'Accept-Encoding': 'identity',
                        'Content-Type': 'application/octet-stream'
                    }
                }
        ) as fin:
            with smart_open.open(
                    f"s3://{bucket}/{object_key}", 'w',
                    transport_params={'client': client},
                    encoding="utf8"
            ) as fout:
                read_so_far = 0
                while read_so_far < fin.buffer.content_length:
                    line = fin.read(1)
                    encoded = line.encode(fin.encoding)
                    fout.write(line)
                    if callback:
                        # pass increment of bytes
                        callback(len(encoded))
                    read_so_far += 1

    except RuntimeWarning:
        logger.warning("URL transfer cancelled by exception?")
        # TODO: what sort of post-cancellation processing is needed here?


"""
Unit Tests
* Run each test function as an assertion if we are debugging the project
"""


def run_test(test_func):
    """
    Run a test function (timed)
    :param test_func:
    """
    try:
        start = time.time()
        assert (test_func())
        end = time.time()
        print("{} passed: {} seconds".format(test_func.__name__, end - start))
    except Exception as e:
        logger.error("{} failed!".format(test_func.__name__))
        logger.error(e)
