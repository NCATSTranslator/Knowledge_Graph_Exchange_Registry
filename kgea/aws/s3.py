#!/usr/bin/env python
"""
This CLI script will take  host AWS account id, guest external id and
the name of a host account IAM role, to obtain temporary AWS service
credentials to execute an AWS Secure Token Service-mediated access
to a Simple Storage Service (S3) bucket given as an argument.
"""
import sys

from sys import platform

if platform != "win32":
    from os import fdopen, pipe, fork, close

from typing import List
from pathlib import Path
from pprint import PrettyPrinter

# from multiprocessing import Process, Pipe
# from multiprocessing.connection import Connection
# from asyncio import sleep

from botocore.config import Config

from kgea.aws.assume_role import AssumeRole, aws_config

import logging
logger = logging.getLogger(__name__)

pp = PrettyPrinter(indent=4)


def usage(err_msg: str = ''):
    """

    :param err_msg:
    """
    if err_msg:
        print(err_msg)

    print("Usage:\n")
    print(
        "\tpython -m kgea.aws."+Path(sys.argv[0]).stem +
        " <operation> [<object_key>+|<prefix_filter>]\n\n" +
        "where <operation> is one of upload, list, copy, download, delete, delete-batch and test.\n\n"
        "Note:\tone or more <object_key> strings are only required for 'delete' operation.\n" +
        "\tA <prefix_filter> string is only required for 'delete-batch' operation.\n"
    )
    exit(0)


s3_bucket_name: str = aws_config["s3"]["bucket"]
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


def upload_file(
        bucket_name: str,
        source_file,
        target_object_key: str,
        source_file_name: str = '',
        client=s3_client
):
    """
    Upload a file.
    
    :param bucket_name:
    :param source_file: may be a file path string or a file descriptor open for reading
    :param target_object_key: target S3 object_key to which to upload the file
    :param source_file_name: (optional) source file name. Defaults to last name of source file path or target object key
    :param client:
    :return:
    """
    if isinstance(source_file, str):
        
        if not source_file_name:
            source_file_name = source_file.split("/")[-1]
            
        print(
            f"\n###Uploading file '{source_file_name}' to object " +
            f"'{target_object_key}' in the S3 bucket '{bucket_name}'\n"
        )
        try:
            client.upload_file(source_file, bucket_name, target_object_key)
        except Exception as exc:
            usage("upload_file(): 'client.upload_file' exception: " + str(exc))

    else:
        
        if not source_file_name:
            source_file_name = target_object_key.split("/")[-1]
            
        # assume that an open file descriptor is being passed for reading
        print(
            f"\n###Uploading file '{source_file_name}' to object " +
            f"'{target_object_key}' in the S3 bucket '{bucket_name}'\n"
        )
        try:
            client.upload_fileobj(source_file, bucket_name, target_object_key)
        except Exception as exc:
            usage("upload_file(): 'client.upload_fileobj' exception: " + str(exc))


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
        print("### Returning list of keys with prefix '" + filter_prefix +
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
        print("### Listing contents of the S3 bucket '" + bucket_name + "':")
        for entry in response['Contents']:
            print(entry['Key'], ':', entry['Size'])
    else:
        usage("S3 bucket '" + bucket_name + "' is empty?")


def download_file(
        bucket_name: str,
        source_object_key: str,
        target_file=None,
        target_file_name=None,
        client=s3_client
) -> str:
    """
    Delete an object key (file) in a given bucket.

    :param target_file_name:
    :param client: S3 client to access S3 bucket
    :param bucket_name: the target bucket
    :param source_object_key: source S3 object_key from which to download the file
    :param target_file: file path string or file descriptor (open for (binary) writing) to which to save the file
    :param target_file_name: (optional) target file name. Defaults to last name of target file path or source object key
    :return:
    """
    if not target_file:
        target_file = source_object_key.split("/")[-1]
        
    if isinstance(target_file, str):
        
        if not target_file_name:
            target_file_name = target_file.split("/")[-1]
            
        print(
            f"\n###Downloading file '{target_file_name}' from object " +
            f"'{source_object_key}' in the S3 bucket '{bucket_name}'\n"
        )
        try:
            client.download_file(Bucket=bucket_name, Key=source_object_key, Filename=target_file)
        except Exception as exc:
            usage("download_file(): 'client.download_file' exception: " + str(exc))
    else:
        
        if not target_file_name:
            target_file_name = source_object_key.split("/")[-1]
            
        # assume that an open file descriptor is being
        # passed for writing of the downloaded S3 object
        print(
            f"\n###Downloading file '{target_file_name}' from object " +
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
        try:
            client.download_fileobj(Bucket=bucket_name, Key=source_object_key, Fileobj=target_file)
        except Exception as exc:
            usage("upload_file(): 'client.downloadload_fileobj' exception: " + str(exc))
    
    return target_file


def local_copy(
        source_key: str,
        target_key: str,
        source_bucket: str = s3_bucket_name,
        target_bucket: str = None,
        client=s3_client,
):
    """
    Local direct copy of a key in one bucket to another key in the same or
    another bucket, but all within the same AWS account (as wrapped by 'client').
    
    :param source_key:
    :param target_key:
    :param source_bucket:
    :param target_bucket:
    :param client:
    """
    if not target_bucket:
        target_bucket = source_bucket

    copy_source = {
        'Bucket': source_bucket,
        'Key': source_key
    }
    client.copy(
        CopySource=copy_source,
        Bucket=target_bucket,
        Key=target_key
    )


# So-called 'remote' copy relies on deferential
# target_client configuration (by the caller)
# and uses a locally cached file for the copy operation
# (presumed fast enough on an EC2 instance?)
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
            usage("Remote copy: requires a distinct non-empty target_bucket and target_client")
    
        # ============== Multiprocessor -specific version of code (doesn't work yet) =============
        #
        # # Child process method
        # def retrieve_the_object(conn: Connection):
        #     """
        #     Downloads an S3 object and streams it into the Pipe(),
        #     to the complementary S3 upload parent process?
        #
        #     :param conn: child Pipe connection
        #     """
        #     with fdopen(conn.fileno(), mode='wb') as download_write_fd:
        #         download_file(
        #             bucket_name=source_bucket,
        #             source_object_key=source_key,
        #             target_file=download_write_fd,
        #             client=source_client
        #         )
        #
        #     conn.close()
        #
        # parent_conn: Connection
        # child_conn: Connection
        # parent_conn, child_conn = Pipe(duplex=False)
        #
        # # Child process to download the object from the source bucket
        # # owned by the source account and feed its data into the Pipe
        # p = Process(target=retrieve_the_object, args=(child_conn,))
        # p.start()
        #
        # # Give the child process time to start
        # sleep(1)
        #
        # with fdopen(parent_conn.fileno(), mode='rb') as upload_read_fd:
        #     upload_file(
        #         bucket_name=target_bucket,
        #         source_file=upload_read_fd,
        #         target_object_key=target_key,
        #         client=target_client
        #     )
        # p.join()
        
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
    
            logger.debug(f"The child process is downloading data from the S3 {source_key} object into the pipe")
            
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
            
            logger.debug(f"The parent process is uploading data from the pipe to the S3 {target_key} object")
            
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
    #     "\n### Deleting the test object '" + object_key +
    #     "' in the S3 bucket '" + bucket_name + "'"
    # )
    response = client.delete_object(Bucket=bucket_name, Key=target_object_key)
    deleted = response["DeleteMarker"]
    if deleted:
        print(f"'{target_object_key}' deleted in bucket '{bucket_name}'!")
    else:
        print(f"Could not delete the '{target_object_key}' in bucket '{bucket_name}'?")


# Run the module as a CLI
if __name__ == '__main__':

    s3_operation: str = ''
    
    if len(sys.argv) > 1:

        s3_operation = sys.argv[1]
        
        if s3_operation.lower() == 'help':
            usage()
    
        elif s3_operation.lower() == 'upload':
            if len(sys.argv) >= 3:
                filepath = sys.argv[2]
                object_key = sys.argv[3] if len(sys.argv) >= 4 else filepath
                upload_file(s3_bucket_name, filepath, object_key)
            else:
                usage("\nMissing path to file to upload?")

        elif s3_operation.lower() == 'list':
            list_files(s3_bucket_name)

        elif s3_operation.lower() == 'copy':
            
            if len(sys.argv) >= 4:
                
                source_key = sys.argv[2]
                target_key = sys.argv[3]
                target_s3_bucket_name = s3_bucket_name

                # Default target bucket may also be overridden on the command line
                target_s3_bucket_name = sys.argv[4] if len(sys.argv) >= 5 else target_s3_bucket_name
                
                local_copy(
                    source_key=source_key,
                    target_key=target_key,
                )
            else:
                usage("\nLocal copy() operation needs a 'source' and 'target' key?")

        elif s3_operation.lower() == 'remote-copy':
    
            if len(sys.argv) >= 4:
        
                source_key = sys.argv[2]
                target_key = sys.argv[3]
        
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
                    usage("Remote copy(): 's3_remote' settings in 'config.yaml' missing or incomplete?")
            
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
                target_s3_bucket_name = sys.argv[4] if len(sys.argv) >= 5 else target_s3_bucket_name
        
                if not target_s3_bucket_name:
                    usage("Remote copy(): missing target bucket name?")
                
                remote_copy(
                    source_key=source_key,
                    target_key=target_key,
                    source_bucket=s3_bucket_name,
                    target_bucket=target_s3_bucket_name,
                    source_client=s3_client,
                    target_client=target_client
                )
            else:
                usage("\nRemote copy(): operation needs a 'source' and 'target' key?")

        elif s3_operation.lower() == 'download':
            if len(sys.argv) >= 3:
                object_key = sys.argv[2]
                filename = sys.argv[3] if len(sys.argv) >= 4 else object_key.split("/")[-1]
                download_file(
                    bucket_name=s3_bucket_name,
                    source_object_key=object_key,
                    target_file=filename
                )
            else:
                usage("\nMissing S3 object key for file to download?")
        
        elif s3_operation.lower() == 'delete':
            if len(sys.argv) >= 3:
                object_keys = sys.argv[2:]
                for key in object_keys:
                    print("\t" + key)
                prompt = input("Proceed (Type 'yes')? ")
                if prompt.upper() == "YES":
                    for key in object_keys:
                        delete_object(s3_bucket_name, key)
                else:
                    print("Cancelling deletion of objects...")
            else:
                usage("\nMissing S3 key(s) of object(s) to delete?")

        elif s3_operation.lower() == 'delete-batch':
            if len(sys.argv) >= 3:
                object_keys = get_object_keys(s3_bucket_name, filter_prefix=sys.argv[2])
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
                usage("\nMissing prefix filter for keys of S3 object(s) to delete?")
        else:
            usage("\nUnknown s3_operation: '" + s3_operation + "'")
    else:
        usage()
