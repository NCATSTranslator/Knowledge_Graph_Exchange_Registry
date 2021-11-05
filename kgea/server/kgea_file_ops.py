"""
Implement robust KGE File Set upload process:
o  “layered” back end unit tests of each level of S3 upload process
o  Figure out the minimal S3 access policy that suffices for the KGE Archive
o  File set versioning using time stamps
o  Web server optimization (e.g. NGINX / WSGI / web application parameters)
o  Test the system (both manually, by visual inspection of uploads)
Stress test using SRI SemMedDb: https://github.com/NCATSTranslator/semmeddb-biolink-kg
"""
from sys import stderr
from typing import Union, List, Tuple, Dict, Optional
from subprocess import Popen, PIPE
from os import getenv
from os.path import sep, splitext, dirname, abspath
import io

from pprint import PrettyPrinter

import random

import re
import itertools

import logging

import requests
from datetime import datetime

from pathlib import Path

from validators import ValidationFailure, url as valid_url

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

from botocore.config import Config
from boto3.s3.transfer import TransferConfig

from kgea.aws.assume_role import AssumeRole, aws_config

from kgea.config import (
    PROVIDER_METADATA_FILE,
    FILE_SET_METADATA_FILE
)

logger = logging.getLogger(__name__)

pp = PrettyPrinter(indent=4, stream=stderr)

# Master flag for local development, usually when code is not run inside an EC2 server
DEV_MODE = getenv('DEV_MODE', default=False)

s3_config = aws_config['s3']
default_s3_region = s3_config['region']
default_s3_bucket = s3_config['bucket']
default_s3_root_key = s3_config['archive-directory']

# TODO: may need to fix script paths below - may not resolve under Microsoft Windows
# if sys.platform is 'win32':
#     archive_script = archive_script.replace('\\', '/').replace('C:', '/mnt/c/')

# Probably will rarely change the name of these
# scripts, but changed once already...
_KGEA_ARCHIVER_SCRIPT = f"{dirname(abspath(__file__))}{sep}scripts{sep}kge_archiver.bash"

_KGEA_URL_TRANSFER_SCRIPT = "kge_direct_url_transfer.bash"


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


def get_default_date_stamp():
    """
    Returns the default date stamp as 'now', as an ISO Format string 'YYYY-MM-DD'
    :return:
    """
    return datetime.now().strftime('%Y-%m-%d')


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
        logger.debug(size)
        data_file.seek(0, 0)
        return size
    else:
        return 0


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
            logger.error(f"get_url_file_size(url: '{str(url)}') doesn't have a 'Content-Length' value in its header?")
            return -3
        except Exception as exc:
            logger.error(f"get_url_file_size(url:'{str(url)}'): {str(exc)}")
            # TODO: invalidate the size invariant to propagate a call error
            # for now return -1 to encode the error state
            return -1

    return size


################################################
# Wrapper for AWS IAM Role for the Application #
################################################

# Obtain an AWS Clients using an Assumed IAM Role
# with default parameters (loaded from config.yaml)
#
the_role = AssumeRole()


############################
# AWS S3 client operations #
############################

def s3_client(
        assumed_role=None,
        config=Config(
            signature_version='s3v4',
            region_name=default_s3_region
        )
):
    """
    :param assumed_role:
    :param config:
    :return: S3 client
    """
    
    if not assumed_role:
        assumed_role = the_role

    return assumed_role.get_client('s3', config=config)


def s3_resource(assumed_role=the_role):
    """
    :param assumed_role:
    :return: S3 resource
    """
    
    if not assumed_role:
        assumed_role = the_role

    return assumed_role.get_resource(
        's3',
        region_name=default_s3_region
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


def get_object_location(kg_id):
    """
    NOTE: Must be kept deterministic. No date times or
    randomness in this method; they may be appended afterwards.
    """
    location = f"{default_s3_root_key}/{kg_id}/"
    return location


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


def match_objects_from_bucket(bucket_name, object_key, assumed_role=None):
    """

    :param bucket_name:
    :param object_key:
    :param assumed_role:
    
    :return:
    """
    bucket = s3_resource(assumed_role=assumed_role).Bucket(bucket_name)
    key = object_key
    objs = list(bucket.objects.filter(Prefix=key))
    return [w.key == key for w in objs]


def object_key_exists(
        object_key,
        bucket_name=default_s3_bucket,
        assumed_role=None
) -> bool:
    """
    Checks for the existence of the specified object key

    :param bucket_name: The bucket
    :param object_key: Target object key in the bucket
    :param assumed_role: (optional) Assumed IAM Role with authority to make this inquiry

    :return: True if the object is in the bucket, False if it is not in the bucket (False also if empty object key)
    """
    if not object_key:
        return False
    return any(
        match_objects_from_bucket(
            bucket_name=bucket_name,
            object_key=object_key,
            assumed_role=assumed_role
        )
    )


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


def object_entries_in_location(bucket, object_location='') -> Dict[str, int]:
    """
    :param bucket:
    :param object_location:
    :return: dictionary of object entries with their size in specified
             object location in a bucket (all bucket entries if object_location is empty)
    """
    bucket_listings: Dict = dict()
    # logger.debug(s3_client().get_paginator("list_objects_v2").paginate(Bucket=bucket_name))
    for p in s3_client().get_paginator("list_objects_v2").paginate(Bucket=bucket):
        if 'Contents' in p:
            for entry in p['Contents']:
                bucket_listings[entry['Key']] = entry['Size']
        else:
            return {}  # empty bucket?

    # If object_location is the empty string, then each object
    # listed passes (since the empty string is part of every string)
    object_matches = {key: bucket_listings[key] for key in bucket_listings if object_location in key}
    
    return object_matches


def object_keys_in_location(bucket, object_location='') -> List[str]:
    """
    :param bucket:
    :param object_location:
    
    :return: all object keys in specified object location of a
             specified bucket (all bucket keys if object_location is empty)
    """
    key_catalog = object_entries_in_location(bucket, object_location=object_location)
    
    return list(key_catalog.keys())


def object_keys_for_fileset_version(
        kg_id: str,
        fileset_version: str,
        bucket=default_s3_bucket,
        match_function=lambda x: True
) -> Tuple[List[str], str]:
    """
    Returns a list of all the files associated with a
    given knowledge graph, for a given file set version.

    :param kg_id: knowledge graph identifier
    :param fileset_version: semantic version ('major.minor') of the file set
    :param bucket: target S3 bucket (default: current config.yaml bucket)
    :param match_function: (optional) lambda filter for list of file object keys returned

    :return: Tuple [ matched list of file object keys, file set version ] found
    """
    target_fileset, fileset_version = with_version(get_object_location, fileset_version)(kg_id)
    
    object_key_list: List[str] = \
        object_keys_in_location(
            bucket=bucket,
            object_location=target_fileset,
        )
    filtered_file_key_list = list(filter(match_function, object_key_list))
    
    return filtered_file_key_list, fileset_version


def object_folder_contents_size(
        kg_id: str,
        fileset_version: str,
        object_subfolder='',
        bucket=default_s3_bucket
) -> int:
    """
    :param kg_id: knowledge graph identifier
    :param fileset_version: semantic version ('major.minor') of the file set
    :param bucket: target S3 bucket (default: current config.yaml bucket)
    :param object_subfolder: subfolder path from root fileset path (default: empty - use fileset root path)

    :return: total size of archived files (in bytes)
    """
    target_fileset, fileset_version = with_version(get_object_location, fileset_version)(kg_id)
    target_folder = f"{target_fileset}{object_subfolder}"
    
    logger.debug(f"object_folder_contents_size({target_folder})")
    
    object_key_catalog: Dict[str, int] = \
        object_entries_in_location(
            bucket=bucket,
            object_location=target_folder,
        )

    total_size = 0
    for size in object_key_catalog.values():
        total_size += int(size)
    
    return total_size


# for an s3 key, match on kg_id
kg_ids_pattern = re.compile(rf"{default_s3_root_key}/([a-zA-Z\d \-]+)/.+")

# for an s3 key, match on kg_id and fileset version
kg_ids_with_versions_pattern = re.compile(rf"{default_s3_root_key}/([\S]+)/(\d+.\d+)/")


def get_fileset_versions_available(bucket_name):
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
    :return versions_per_kg: dict
    """

    all_kge_archive_files = \
        object_entries_in_location(
            bucket=bucket_name,
            object_location=default_s3_root_key
        )

    # create a map of kg_ids and their versions
    kg_ids = set(kg_ids_pattern.match(kg_file).group(1) for kg_file in all_kge_archive_files if
                 kg_ids_pattern.match(kg_file) is not None)  # some kg_ids don't have versions
    
    versions_per_kg = {}
    version_kg_pairs = set(
        (
            kg_ids_with_versions_pattern.match(kg_file).group(1),
            kg_ids_with_versions_pattern.match(kg_file).group(2)
        ) for kg_file in all_kge_archive_files if kg_ids_with_versions_pattern.match(kg_file) is not None)

    pp.pprint({"Knowledge Graphs": kg_ids, "File Set Versions": version_kg_pairs})

    for key, group in itertools.groupby(version_kg_pairs, lambda x: x[0]):
        versions_per_kg[key] = []
        for thing in group:
            versions_per_kg[key].append(thing[1])

    # add kg_ids that became filtered
    for kg_id in kg_ids:
        if kg_id not in versions_per_kg:
            versions_per_kg[kg_id] = []

    return versions_per_kg


# TODO: clarify expiration time - default to 1 day (in seconds)
def create_presigned_url(object_key, bucket=default_s3_bucket, expiration=86400) -> Optional[str]:
    """Generate a pre-signed URL to share an S3 object

    :param object_key: string
    :param bucket: string
    :param expiration: Time in seconds for the pre-signed URL to remain valid
    :return: Presigned URL as string. If error, returns None.
    """

    # Generate a pre-signed URL for the S3 object
    # https://stackoverflow.com/a/52642792
    #
    # This may throw a Boto related exception - assume that it will be caught by the caller
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
        logger.error("create_presigned_url() error: " + str(e))
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
    return f"{root}/{kg_id}/{fileset_version}{subdir}/{attachment}"


# def package_file_manifest(tar_path):
#     """
#
#     :param tar_path:
#     :return:
#     """
#     with tarfile.open(tar_path, 'r|gz') as tar:
#         manifest = dict()
#         for tarinfo in tar:
#             logger.debug("\t", tarinfo.name, "is", tarinfo.size, "bytes in size and is ", end="")
#             if tarinfo.isreg():
#                 logger.debug("a regular file.")
#             elif tarinfo.isdir():
#                 logger.debug("a directory.")
#             else:
#                 logger.debug("something else.")
#             manifest[tarinfo.name] = {
#                 "raw": tarinfo,
#                 "name": tarinfo.name,
#                 "type": tarinfo.type,
#                 "size": tarinfo.size
#             }
#         return manifest


def get_object_key(object_location, filename):
    """
    :param object_location: S3 location of the persisted object
    :param filename: filename of the S3 object
    :return: object key of the S3 object
    """
    return f"{object_location}{Path(filename).stem}{splitext(filename)[1]}"


def upload_file(bucket, object_key, source, client=s3_client(), config=None, callback=None):
    """
    Upload a file to an S3 bucket. Note that this method is
    totally agnostic as to specific (KGX) file format and content.

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


def copy_file(
        source_key,
        target_dir,
        bucket=default_s3_bucket
):
    """
    Copies source_key text file into target_dir

    :param bucket:
    :param source_key:
    :param target_dir:
    :return:
    """
    if not (source_key and target_dir):
        raise RuntimeError("copy_file_to_archive(): missing source_key or target_dir?")

    source_file_name = source_key.split("/")[-1]
    target_key = f"{target_dir}/{source_file_name}"

    logger.debug(f"Copying {source_key} to {target_key}")

    copy_source = {
        'Bucket': bucket,
        'Key': source_key
    }
    s3_client().copy(copy_source, bucket, target_key)

    logger.debug(f"...copy completed!")


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
        logger.error(f"ERROR: _load_s3_text_file('{str(e)}')")

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
    all_object_keys = object_keys_in_location(bucket=bucket_name)

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

    for file_path in all_object_keys:

        file_part = file_path.split('/')

        if not file_part:
            continue

        # ignore things that don't look like the KGE File Set folder
        if file_part[0] != default_s3_root_key:
            continue

        # ignore empty KGE File Set folder
        if len(file_part) == 1 or not file_part[1]:
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


# Curl Bytes Received
_cbr_pattern = re.compile(r"^(?P<num>\d+(\.\d+)?)(?P<mag>[KMGTP])?$", flags=re.IGNORECASE)
_cbr_magnitude = {
    'K': 2**10,
    'M': 2**20,
    'G': 2**30,
    'T': 2**40,
    'P': 2**50,
}


def _cbr(value) -> int:
    """
    Symbolic Curl Bytes Received string, parsed to int
    :param value:
    :return:
    """
    m = _cbr_pattern.match(value)
    if m:
        if m.group('mag'):
            return round(float(m.group('num')) * _cbr_magnitude[m.group('mag').upper()])
        else:
            return round(float(m.group('num')))
    else:
        return -1


def upload_from_link(
        bucket,
        object_key,
        source,
        client=None,  # not used here. EC2 level aws cli used instead
        callback=None
):
    """
    Transfers a file resource to S3 from a URL location. Note that this
    method is totally agnostic as to specific (KGX) file format and content.

    :param bucket: in S3
    :param object_key: of target S3 object
    :param source: url of resource to be uploaded to S3
    :param callback: e.g. progress monitor
    :param client: for S3 - ignored (aws CLI used instead)
    """
    # make sure we're getting a valid url
    assert(valid_url(source))
    
    try:
        
        s3_object_target = f"s3://{bucket}/{object_key}"
        cmd = f"curl -L {source}| aws s3 cp - {s3_object_target}"
        with Popen(
            cmd,
            bufsize=1,
            universal_newlines=True,
            stderr=PIPE,
            shell=True
        ).stderr as proc_stderr:
            previous: int = 0
            callback(0)
            for line in proc_stderr:
                # The 'line' is the full curl progress meter
                field = line.split()
                if not field:
                    continue
                current: int = _cbr(field[3])
                if current < 0:
                    continue
                if previous < current:
                    callback(current-previous)
                    previous = current
        
    except RuntimeWarning:
        logger.warning("URL transfer cancelled by exception?")


###################################
# AWS EC2 & EBS client operations #
###################################

def ec2_client(assumed_role=the_role):
    """
    :param assumed_role:
    :return: EC2 client
    """
    return assumed_role.get_client('ec2')

###################################################################################################
# Dynamic EBS provisioning steps, orchestrated by the KgeArchiver.worker() task which
# direct calls methods using S3 and EC2 clients, plus an (steps 1.3, 1.4 plus 3.1) enhanced
# version of the (step 2.0) kgea/server/web_services/scripts/kge_archiver.bash script.
#
# object_folder_contents_size():
# 0.1 (S3 client) - Calculate EBS storage needs for target activity
# (step 2.0 - archiving.. see below), then proceed to step 1.1
#
# create_ebs_volume():
# 1.1 (EC2 client) - Create a suitably sized EBS volume, via the EC2 client
# 1.2 (EC2 client) - Associate the EBS volume with the EC2 instance running the application
# 1.3 (Popen() run bash script) - Mount the EBS volume inside the EC2 instance
# 1.4 (Popen() run bash script) - Format the EBS volume
#     TODO: might try to configure and use a persistent EBS Snapshot in step 1 to accelerate this step?
#
# compress_fileset():
# 2.0 (Popen() run bash script) - Use the instance as the volume working space for target
#     application activities (i.e. archiving). Likely need to set or change to the
#     current working directory to one hosted on the target EBS volume.
#
# delete_ebs_volume():
# 3.1 (Popen() run bash script) - Cleanly unmount EBS volume after it is no longer needed.
# 3.2 (EC2 client) - Disassociate the EBS volume from the EC2 instance.
# 3.3 (EC2 client) - Delete the instance (to avoid economic cost).
###################################################################################################


def create_ebs_volume(size: int) -> str:
    """
    Allocates and mounts an EBS volume of a given size onto the EC2 instance running the application (if applicable).
    The EBS volume is mounted by default on the (Linux) directory '/data' and formatted as a simple
    
    Note: is a 'no operation' in application 'DEV_MODE' thus  returns an empty string identifier.
    
    :param size: specified size (in gigabytes)
    :return: EBS volume instance identifier
    """
    if DEV_MODE:
        return ''
    else:

        raise RuntimeError("create_ebs_volume(): Not yet implemented!")


def delete_ebs_volume(identifier: str):
    """
    Discards a given volume.
    
    :param identifier: EBS volume instance identifier
    """
    raise RuntimeError("create_ebs_volume(): Not yet implemented!")


# DEPRECATED - Unit tests moved over to kgea 'tests' folder
# """
# Unit Tests
# * Run each test function as an assertion if we are debugging the project
# """
#
#
# def run_test(test_func):
#     """
#     Run a test function (timed)
#     :param test_func:
#     """
#     try:
#         start = time.time()
#         assert (test_func())
#         end = time.time()
#         logger.debug("{} passed: {} seconds".format(test_func.__name__, end - start))
#     except Exception as e:
#         logger.error("{} failed!".format(test_func.__name__))
#         logger.error(e)