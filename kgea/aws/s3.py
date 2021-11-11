#!/usr/bin/env python
"""
This CLI script will take  host AWS account id, guest external id and
the name of a host account IAM role, to obtain temporary AWS service
credentials to execute an AWS Secure Token Service-mediated access
to a Simple Storage Service (S3) bucket given as an argument.
"""
from sys import platform, argv, stdout
from os import makedirs, getcwd, remove
from os.path import isdir, getsize
import threading

if platform != "win32":
    from os import fdopen, pipe, fork, close

from typing import List
from pathlib import Path

from botocore.config import Config

from kgea.aws import Help
from kgea.aws.assume_role import AssumeRole, aws_config

import logging
logger = logging.getLogger(__name__)
#logger.setLevel(logging.DEBUG)

HELP = "help"
UPLOAD = "upload"
BATCH_UPLOAD = "batch-upload"
DOWNLOAD = "download"
BATCH_DOWNLOAD = "batch-download"
LIST = "list"
COPY = "copy"
REMOTE_COPY = "remote-copy"
DELETE = "delete"
BATCH_DELETE = "batch-delete"
BATCH_COPY = "batch-copy"


helpdoc = Help(
    default_usage=f"\tpython -m kgea.aws.'{Path(argv[0]).stem}' <operation> [<object_key>+|<prefix_filter>]\n\n" +
                  "where <operation> is one of upload, batch-upload, list, copy, "
                  "download, batch-download, delete, batch-delete and test.\n"
)


s3_bucket_name: str = aws_config["s3"]["bucket"]
s3_directory: str = aws_config["s3"]["archive-directory"]
s3_region_name: str = aws_config["s3"]["region"]

assumed_role = AssumeRole()

s3_client = \
    assumed_role.get_client(
        's3',
        config=Config(
            signature_version='s3v4',
            region_name=s3_region_name
        )
    )


def get_remote_s3_client():
    """
    :return: result from AssumeRole.get_client() call using "s3_remote" config.yaml parameters
    """
    if "s3_remote" not in aws_config:
        raise RuntimeError("Remote account 's3_remote' configuration parameters are not provided in the config.yaml?")
    
    remote_host_account: str = aws_config["s3_remote"]["host_account"]
    remote_guest_external_id: str = aws_config["s3_remote"]["guest_external_id"]
    remote_iam_role_name: str = aws_config["s3_remote"]["iam_role_name"]
    remote_s3_region_name: str = aws_config["s3_remote"]["region"]
    
    remote_assumed_role = AssumeRole(
        host_account=remote_host_account,
        guest_external_id=remote_guest_external_id,
        iam_role_name=remote_iam_role_name
    )
    
    remote_s3_client = \
        remote_assumed_role.get_client(
            's3',
            config=Config(
                signature_version='s3v4',
                region_name=remote_s3_region_name
            )
        )
    
    return remote_s3_client


if "s3_remote" in aws_config:
    remote_s3_bucket_name: str = aws_config["s3_remote"]["bucket"]
    remote_s3_directory: str = aws_config["s3_remote"]["archive-directory"]


class ProgressPercentage(object):
    """
    Progress monitor for downloading and uploading of files
    """
    def __init__(self, action, filename):
        self._action = action
        self._filename = filename
        self._size = float(getsize(filename))
        self._seen_so_far = 0
        self._lock = threading.Lock()

    def __call__(self, bytes_amount):
        # To simplify, assume this is hooked up to a single filename
        with self._lock:
            self._seen_so_far += bytes_amount
            percentage = (self._seen_so_far / self._size) * 100
            stdout.write(
                "\r%s  %s / %s  (%.2f%%)" % (
                    self._filename, self._seen_so_far, self._size,
                    percentage))
            stdout.flush()


def upload_file(
        bucket_name: str,
        source_file,
        target_object_key: str,
        source_file_name: str = '',
        client=s3_client,
        debug=False
):
    """
    Upload a file.
    
    :param bucket_name:
    :param source_file: may be a file path string or a file descriptor open for reading
    :param target_object_key: target S3 object_key to which to upload the file
    :param source_file_name: (optional) source file name. Defaults to last name of source file path or target object key
    :param client: S3 client to access S3 bucket (defaults to globally defined S3 client)
    :param debug: (optional) if 'True' then the only show logger debug for actions, but don't run the core code
    :return:
    """
    if isinstance(source_file, str):
        
        if not source_file_name:
            source_file_name = source_file.split("/")[-1]
            
        logger.debug(
            f"###Uploading file '{source_file_name}' to object " +
            f"'{target_object_key}' in the S3 bucket '{bucket_name}'\n"
        )
        if not debug:
            try:
                client.upload_file(
                    source_file,
                    bucket_name,
                    target_object_key,
                    Callback=ProgressPercentage("Upload", source_file_name)
                )
            except Exception as exc:
                helpdoc.usage(
                    err_msg="upload_file(): 'client.upload_file' exception: " + str(exc)
                )

    else:
        
        if not source_file_name:
            source_file_name = target_object_key.split("/")[-1]
            
        # assume that an open file descriptor is being passed for reading
        logger.debug(
            f"###Uploading file '{source_file_name}' to object " +
            f"'{target_object_key}' in the S3 bucket '{bucket_name}'\n"
        )
        if not debug:
            try:
                client.upload_fileobj(
                    source_file,
                    bucket_name,
                    target_object_key,
                    Callback=ProgressPercentage("Upload", source_file_name)
                )
            except Exception as exc:
                helpdoc.usage(err_msg="upload_file(): 'client.upload_fileobj' exception: " + str(exc))


def get_object_keys(
        bucket_name: str,
        filter_prefix='',
        client=s3_client
) -> List[str]:
    """
    Check for the new file in the bucket listing.
    :param client:
    :param bucket_name:
    :param filter_prefix:
    :return:
    """
    response = client.list_objects_v2(Bucket=bucket_name, Prefix=filter_prefix)

    if 'Contents' in response:
        logger.debug("### Returning list of keys with prefix '" + filter_prefix +
                     "'from the S3 bucket '" + bucket_name + "'")
        return [item['Key'] for item in response['Contents']]
    else:
        print("S3 bucket '" + bucket_name + "' is empty?")
        return []


def list_files(
        bucket_name: str,
        client=s3_client
):
    """
    Check for the new file in the bucket listing.
    :param client:
    :param bucket_name:
    :return:
    """
    response = client.list_objects_v2(Bucket=bucket_name)
    
    if 'Contents' in response:
        logger.debug("### Listing contents of the S3 bucket '" + bucket_name + "':")
        for entry in response['Contents']:
            print(entry['Key'], ':', entry['Size'])
    else:
        helpdoc.usage(err_msg="S3 bucket '" + bucket_name + "' is empty?")


def download_file(
        bucket_name: str,
        source_object_key: str,
        target_file=None,
        target_file_name=None,
        client=s3_client,
        debug=False
) -> str:
    """
    Delete an object key (file) in a given bucket.

    :param target_file_name:
    :param bucket_name: the target bucket
    :param source_object_key: source S3 object_key from which to download the file
    :param target_file: file path string or file descriptor (open for (binary) writing) to which to save the file
    :param target_file_name: (optional) target file name. Defaults to last name of target file path or source object key
    :param client: S3 client to access S3 bucket (defaults to globally defined S3 client)
    :param debug: (optional) if 'True' then the only show logger debug for actions, but don't run the core code
    :return:
    """
    if not target_file:
        target_file = source_object_key.split("/")[-1]
    
    if isinstance(target_file, str):
        
        if not target_file_name:
            target_file_name = target_file.split("/")[-1]
            
        logger.debug(
            f"###Downloading file '{target_file_name}' from object " +
            f"'{source_object_key}' in the S3 bucket '{bucket_name}'\n"
        )
        if not debug:
            try:
                client.download_file(
                    Bucket=bucket_name,
                    Key=source_object_key,
                    Filename=target_file,
                    Callback=None  # ProgressPercentage("Download", target_file_name)
                )
            except Exception as exc:
                helpdoc.usage(err_msg="download_file(): 'client.download_file' exception: " + str(exc))
    else:
        
        if not target_file_name:
            target_file_name = source_object_key.split("/")[-1]
            
        # assume that an open file descriptor is being
        # passed for writing of the downloaded S3 object
        logger.debug(
            f"###Downloading file '{target_file_name}' from object " +
            f"'{source_object_key}' in the S3 bucket '{bucket_name}'\n"
        )
        #
        # These default transfer configuration parameters may be ok for most transfers or may need to be tweaked
        # for S3 object 'remote_copy' which uses multiprocessor Pipe Connections (not sure...)
        #
        # boto3.s3.transfer.TransferConfig(
        #     multipart_threshold=8388608,
        #     max_concurrency=10,
        #     multipart_chunksize=8388608,
        #     num_download_attempts=5,
        #     max_io_queue=100,
        #     io_chunksize=262144,
        #     use_threads=True
        #     )[source]
        #
        if not debug:
            try:
                client.download_fileobj(
                    Bucket=bucket_name,
                    Key=source_object_key,
                    Fileobj=target_file,
                    Callback=None  # ProgressPercentage("Download", target_file_name)
                )
            except Exception as exc:
                helpdoc.usage(err_msg="upload_file(): 'client.downloadload_fileobj' exception: " + str(exc))
    
    return target_file


def copy(
        source_key: str,
        target_key: str,
        source_bucket=s3_bucket_name,
        target_bucket: str = '',
        source_client=s3_client,
        target_client=None
):
    """
    Local direct copy of a key in one bucket to another key in the same or
    another bucket, but all within the same AWS account (as wrapped by 'client').

    :param source_key:
    :param target_key:
    :param source_bucket:
    :param target_bucket:
    :param source_client:
    :param target_client:
    """
    if not target_bucket:
        target_bucket = source_bucket
        
    if not target_client:
        target_client = source_client

    copy_source = {
        'Bucket': source_bucket,
        'Key': source_key
    }
    
    target_client.copy(
        CopySource=copy_source,
        SourceClient=source_client,
        Bucket=target_bucket,
        Key=target_key
    )


def remote_copy(
        source_key: str,
        target_key: str,
        target_bucket: str,
        target_client,
        source_bucket=s3_bucket_name,
        source_client=s3_client,
):
    """
    Copy an object from a source bucket and account to a second bucket and account, where access
    to the account is defined in the target client configuration by the caller of the function.

    :param source_key:
    :param target_key:
    :param source_bucket:
    :param target_bucket:
    :param source_client:
    :param target_client:
    """
    logger.debug("Entering remote_copy")
    
    if platform == "win32":
        raise NotImplementedError("remote_copy() is not yet implemented for Microsoft Windows!")
    
    else:  # *nix operating system should support this version of remote_copy?
        
        if not (target_bucket and target_client):
            helpdoc.usage(err_msg="Remote copy: requires a distinct non-empty target_bucket and target_client")
        
        # ===================== UNIX-specific version of code =============================
        # Create a pipe: the returned file descriptors upload_read_fd and download_write_fd
        # can be used for reading and writing respectively.
        upload_read_fd, download_write_fd = pipe()
    
        # We create a child process and using these file descriptors, the parent process will
        # write data and child process will read the data written by the parent process
    
        # Create a child process
        pid = fork()
    
        # pid greater than 0 represents the parent process
        if pid > 0:
    
            # This is the parent process... the 'upload_read_fd' is not needed
            close(upload_read_fd)
    
            logger.debug(f"The child process is downloading data from the S3 '{source_key}' object into the pipe")
            
            with fdopen(download_write_fd, mode='wb') as target_fileobj:
                download_file(
                    bucket_name=source_bucket,
                    source_object_key=source_key,
                    target_file=target_fileobj,
                    client=source_client
                )
    
        else:
            # This is the child process... the 'download_write_fd' not needed
            close(download_write_fd)
    
            # Child process is reading the data stream of the S3 object downloaded
            # by the parent process and uploading it up to another S3 bucket
            
            logger.debug(f"The parent process is uploading data from the pipe to the S3 '{target_key}' object")
            
            with fdopen(upload_read_fd, mode='rb') as source_fileobj:
                upload_file(
                    bucket_name=target_bucket,
                    source_file=source_fileobj,
                    target_object_key=target_key,
                    client=target_client
                )
                
    logger.debug("Exiting remote_copy")
    

def delete_object(
        bucket_name: str,
        target_object_key: str,
        client=s3_client
):
    """
    Delete an object key (file) in a given bucket.
    
    :param client:
    :param bucket_name:
    :param target_object_key:
    :return:
    """
    # print(
    #     "### Deleting the test object '" + object_key +
    #     "' in the S3 bucket '" + bucket_name + "'"
    # )
    response = client.delete_object(Bucket=bucket_name, Key=target_object_key)
    deleted = response["DeleteMarker"]
    if deleted:
        print(f"'{target_object_key}' deleted in bucket '{bucket_name}'!")
    else:
        print(f"Could not delete the '{target_object_key}' in bucket '{bucket_name}'?")


def batch_copy_object(
        source_object_key,
        source_folder,
        target_folder,
        target_bucket=None,
        target_client=s3_client,
        debug=False
):
    """
    Move a single object from one S3 location to another.
    
    :param source_object_key: Object key to move.
    :param source_folder: Source S3 object key folder location from which to move data
    :param target_folder: Target S3 object key folder location to which to move data
    :param target_bucket: (Optional) different target bucket location of target folder
    :param target_client: (Optional) different target client account
    :param debug: (optional) if 'True' then the only show logger debug for actions, but don't run the core code
    """
    target_client_name = "Local" if target_client == s3_client else "Remote"

    # Step 1 - resolve filename, source_key and target key
    filename = source_object_key.split("/")[-1]
    target_object_key = source_object_key.replace(source_folder,target_folder)
    
    # Step 2 - Download source object to disk file

    download_file(
        bucket_name=s3_bucket_name,
        source_object_key=source_object_key,
        target_file=filename,
        debug=debug
    )
    # Step 3 - Upload disk file to as comparable key to target folder
    upload_file(
        bucket_name=target_bucket,
        source_file=filename,  # identical to source_file_name since locally cached
        target_object_key=target_object_key,
        client=target_client,
        debug=debug
    )
    # Step 4 - Delete locally cached copy of the file
    if not debug:
        remove(filename)

    print(f" ...Done!")

# Run the module as a CLI
if __name__ == '__main__':

    s3_operation: str = ''
    
    if len(argv) > 1:

        s3_operation = argv[1]
        
        if s3_operation.lower() == HELP:
            helpdoc.usage()
    
        elif s3_operation.lower() == UPLOAD:
            if len(argv) >= 3:
                filepath = argv[2]
                object_key = argv[3] if len(argv) >= 4 else filepath
                upload_file(s3_bucket_name, filepath, object_key)
            else:
                helpdoc.usage(
                    err_msg="Missing the path of the file to upload?",
                    command=UPLOAD,
                    args={
                        "<file path>": "local source directory containing the data files to upload",
                        "[<target object key>]?": "(optional) target object key to which the file is being uploaded"
                    }
                )

        elif s3_operation.lower() == BATCH_UPLOAD:
            
            if len(argv) >= 3:
                
                print(f"{BATCH_UPLOAD} arguments: {argv}")
                
                # The minimum file spec is a directory containing all of the files of interest
                # The operation is NOT recursive into any subdirectories - they are ignored
                source_dir = Path(getcwd(), argv[2])
                
                # ... for uploading to a specified object key root location (folder) in the
                # default target S3 bucket: e.g. something like "kge-data/kg_id/fileset_version"
                # or "kge-data/kg_id/fileset_version/archive" for the archive folders (must be a specific destination)
                # Default: the default S3 directory defined in the config.yaml...
                object_key_base = argv[3] if len(argv) >= 4 else s3_directory
                
                print(
                    f"\tUploading the following local files to S3 bucket " +
                    f"{s3_bucket_name} location '{object_key_base}': "
                )
                for filepath in source_dir.iterdir():
                    if not isdir(filepath):
                        print(f"\t{str(filepath)}")
                prompt = input("Proceed (Type 'yes')? ")
                if prompt.upper() == "YES":
                    print(f"To target S3 bucket '{s3_bucket_name}':")
                    for filepath in source_dir.iterdir():
                        if not isdir(filepath):
                            object_key = f"{object_key_base}/{filepath.name}"
                            print(f"Uploading {filepath} to {str(object_key)}...", end='')
                            upload_file(
                               bucket_name=s3_bucket_name,
                               source_file=str(filepath),  # need to coerce to string, 'cuz it's a Path object
                               target_object_key=object_key
                            )
                            print("Done!")
                else:
                    print("Cancelling uploading of files...")
            else:
                helpdoc.usage(
                    err_msg="Missing at least a local source directory containing the data files to upload?",
                    command=BATCH_UPLOAD,
                    args={
                        "<source directory>": "local source directory containing the data files to upload",
                        "[<target object key base>]?": "(optional) object key root location in the target S3 bucket"
                    }
                )

        elif s3_operation.lower() == LIST:
            list_files(s3_bucket_name)

        elif s3_operation.lower() == COPY:
            
            if len(argv) >= 4:
                
                source_key = argv[2]
                target_key = argv[3]
                target_s3_bucket_name = s3_bucket_name

                # Default target bucket may also be overridden on the command line
                target_s3_bucket_name = argv[4] if len(argv) >= 5 else target_s3_bucket_name
                
                if not target_s3_bucket_name:
                    helpdoc.usage(
                        err_msg="Local copy(): missing the target s3 bucket name?",
                        command=COPY,
                        args={
                            "<source key>": "key of source object from which to copy",
                            "<target key>": "key of target object to which to copy",
                            "[<target bucket>]?": "(optional) target bucket name (default: source bucket)"
                        }
                    )
                    
                copy(
                    source_key=source_key,
                    target_key=target_key,
                )
            else:
                helpdoc.usage(
                    err_msg="Local copy(): missing a 'source' and/or 'target' key?",
                    command=COPY,
                    args={
                        "<source key>": "key of source object from which to copy",
                        "<target key>": "key of target object to which to copy",
                        "[<target bucket>]?": "(optional) target bucket name (default: source bucket)"
                    }
                )

        elif s3_operation.lower() == REMOTE_COPY:
    
            if len(argv) >= 4:
        
                source_key = argv[2]
                target_key = argv[3]
        
                #
                # The 'target' client and possibly, the target bucket
                # (if not given as the 3rd CLI arguments after the 'copy' command)
                # are configured here using "s3_remote" settings as provided
                # from the application's config.yaml file.
                #
                target_client = None
                target_s3_bucket_name = None
            
                if "s3_remote" not in aws_config or \
                    not all(
                        [
                            tag in aws_config["s3_remote"]
                            for tag in [
                                'guest_external_id',
                                'host_account',
                                'iam_role_name',
                                'archive-directory',
                                'bucket',
                                'region'
                            ]
                        ]):
                    
                    helpdoc.usage(
                        err_msg="Remote copy(): 's3_remote' settings in 'config.yaml' are missing or incomplete?"
                    )
            
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
                    
                    assert target_client
                    
                    target_s3_bucket_name = aws_config["s3_remote"]["bucket"]
        
                # Default remote target bucket name may also be overridden on the command line
                target_s3_bucket_name = argv[4] if len(argv) >= 5 else target_s3_bucket_name
        
                if not target_s3_bucket_name:
                    helpdoc.usage(
                        err_msg="Remote copy(): missing the target s3 bucket name?",
                        command=REMOTE_COPY,
                        args={
                            "<source key>": "key of source object from which to copy",
                            "<target key>": "key of target object to which to copy",
                            "[<target bucket>]?": "(optional) target bucket name (default: source bucket)"
                        }
                    )
                
                remote_copy(
                    source_key=source_key,
                    target_key=target_key,
                    source_bucket=s3_bucket_name,
                    target_bucket=target_s3_bucket_name,
                    source_client=s3_client,
                    target_client=target_client
                )
            else:
                helpdoc.usage(
                    err_msg="Remote copy(): missing a 'source' and/or 'target' key?",
                    command=REMOTE_COPY,
                    args={
                        "<source key>": "key of source object from which to copy",
                        "<target key>": "key of target object to which to copy",
                        "[<target bucket>]?": "(optional) target bucket name (default: source bucket)"
                    }
                )

        elif s3_operation.lower() == DOWNLOAD:
            if len(argv) >= 3:
                object_key = argv[2]
                filename = argv[3] if len(argv) >= 4 else object_key.split("/")[-1]
                download_file(
                    bucket_name=s3_bucket_name,
                    source_object_key=object_key,
                    target_file=filename
                )
            else:
                helpdoc.usage(
                    err_msg="Missing S3 object key for file to download?",
                    command=DOWNLOAD,
                    args={
                        "<object key>": "key of object to download",
                        "[<filename>]?":
                            "(optional) explicit file name to give the downloadable" +
                            " S3 object. Infer from object key if not provided."
                    }
                )

        elif s3_operation.lower() == BATCH_DOWNLOAD:
            
            if len(argv) >= 3:
                
                object_keys = get_object_keys(s3_bucket_name, filter_prefix=argv[2])
                target_directory = argv[3] if len(argv) >= 4 else "."
                
                print(f"\nFrom bucket '{s3_bucket_name}' into directory '{target_directory}', downloading key(s):\n")
                for object_key in object_keys:
                    print("\t"+object_key)
                prompt = input("Proceed (Type 'yes')? ")
                if prompt.upper() == "YES":
                    if not (target_directory == "." or isdir(target_directory)):
                        makedirs(target_directory)
                    print(f"From source S3 bucket {s3_bucket_name}:")
                    for object_key in object_keys:
                        filepath = f"{target_directory}/{object_key.split('/')[-1]}"
                        print(f"\tDownloading '{object_key}' to '{filepath}'...", end='')
                        download_file(
                            bucket_name=s3_bucket_name,
                            source_object_key=object_key,
                            target_file=filepath
                        )
                        print("Done!")
            else:
                helpdoc.usage(
                    err_msg="Missing prefix filter for keys of S3 object(s) to download?",
                    command=BATCH_DOWNLOAD,
                    args={
                        "<filter>": "filter of object keys of objects to download from the target bucket",
                        "[<target directory>]?": "(optional) target directory for downloaded files (default: current)"
                    }
                )

        elif s3_operation.lower() == DELETE:
            if len(argv) >= 3:
                object_keys = argv[2:]
                for key in object_keys:
                    print("\t" + key)
                prompt = input("Proceed (Type 'yes')? ")
                if prompt.upper() == "YES":
                    for key in object_keys:
                        delete_object(s3_bucket_name, key)
                else:
                    print("Cancelling deletion of objects...")
            else:
                helpdoc.usage(
                    err_msg="Missing S3 key(s) of object(s) to delete?",
                    command=DELETE,
                    args={
                        "<filter>+": "list of explicit object keys to delete"
                    }
                )

        elif s3_operation.lower() == BATCH_DELETE:
            if len(argv) >= 3:
                object_keys = get_object_keys(s3_bucket_name, filter_prefix=argv[2])
                print("Deleting key(s): ")
                for key in object_keys:
                    print("\t"+key)
                prompt = input("Proceed (Type 'yes')? ")
                if prompt.upper() == "YES":
                    for key in object_keys:
                        delete_object(s3_bucket_name, key)
                else:
                    print("Cancelling deletion of objects...")
            else:
                helpdoc.usage(
                    err_msg="Missing prefix filter for keys of S3 object(s) to delete?",
                    command=BATCH_DELETE,
                    args={
                        "<filter>": "object key string (prefix) filter"
                    }
                )
        elif s3_operation.lower() == BATCH_COPY:
            if len(argv) >= 4:
                source = argv[2]
                target = argv[3]
                target_bucket = argv[4] if len(argv) >= 5 else s3_bucket_name
                is_remote_target = argv[5].lower() == "true" if len(argv) >= 6 else False
                object_keys = get_object_keys(s3_bucket_name, filter_prefix=source)
                print(
                    f"\nFrom the folder '{source}'\n" +
                    f"in source bucket '{s3_bucket_name}' of the 'Local' client,\nmoving the following objects:\n"
                )
                for key in object_keys:
                    if key[-1] != "/":
                        print("\t"+key)
                target_client_name = "Remote" if is_remote_target else "Local"
                print(f"\n...over to folder '{target}'\nin the target bucket " +
                      f"'{target_bucket}' of the '{target_client_name}' client.\n")
                prompt = input("Proceed (Type 'yes')? ")
                if prompt.upper() == "YES":
                    target_client = get_remote_s3_client() if is_remote_target else s3_client
                    print(
                        f"Copying objects from '{source}' folder in bucket '{s3_bucket_name}' of 'Local' client\n" +
                        f"\tto '{target}' folder in target bucket '{target_bucket}' of '{target_client_name}' client"
                    )
                    for source_object_key in object_keys:
                        batch_copy_object(
                            source_object_key=source_object_key,
                            source_folder=source,
                            target_folder=target,
                            target_bucket=target_bucket,
                            target_client=target_client,
                            #debug=True
                        )
                else:
                    print("Cancelling batch copy of objects...")
            else:
                helpdoc.usage(
                    err_msg="Missing source or target object key folder for move",
                    command=BATCH_COPY,
                    args={
                        "<source folder>": "full source S3 object key folder location from which to copy data",
                        "<target folder>": "full target S3 object key folder location to which to copy data",
                        "[<target bucket>]":
                            "(optional) name of target bucket for target folder, if not equivalent to source bucket",
                        "[<remote client>]":
                            "(optional, case insensitive) string value 'true' is boolean flag that specifies use of " +
                            "\n\t\t\tthe config.yaml 's3_remote' parameter-configured client as the target of the copy"
    
                    }
                )
        else:
            helpdoc.usage(err_msg=f"Unknown s3_operation: '{s3_operation}'")
    else:
        helpdoc.usage()
