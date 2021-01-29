import connexion
import six

from openapi_server import util

import boto3
from botocore.exceptions import ClientError
from botocore.client import Config

import yaml

from string import Template
from pathlib import Path

def get_upload_form():  # noqa: E501
    """Get web form for specifying KGE File Set upload

     # noqa: E501


    :rtype: str
    """
    page = """
    <!DOCTYPE html>
    <html>

    <head>
        <title>Upload New File</title>
    </head>

    <body>
        <h1>Upload Files</h1>

        <form action="/upload" method="post" enctype="multipart/form-data">
            <input type="file" name="data_file_content">
            <input type="file" name="metadata_file_content">
            <input type="submit" value="Upload">
        </form>

    </body>

    </html>
    """
    return page


def upload_file_set(data_file_content):  # noqa: E501
    """Upload web form details specifying a KGE File Set upload process

     # noqa: E501

    :param data_file_content: 
    :type data_file_content: str

    :rtype: str
    """

    object_location = Template('$DIRECTORY_NAME/$KG_NAME/$CONTENT_TYPE/').substitute(
        DIRECTORY_NAME='kge-data', 
        CONTENT_TYPE='content'
        KG_NAME=Path(data_file_content.filename).stem
    )

    # TODO: Lift bucket into configuration
    def upload_file(data_file_content, bucket, object_name, override=False):
        # print(data_file_content.filename, dir(data_file_content.name))
        """Upload a file to an S3 bucket

        :param file_name: File to upload
        :param bucket: Bucket to upload to
        :param object_name: S3 object name. If not specified then file_name is used
        :return: True if file was uploaded, else False
        """

        def location_available(bucket_name, object_key):
            """
            Guarantee that we can write to the location of the object without overriding everything

            :param bucket: The bucket
            :param object: The object in the bucket
            :return: True if the object is not in the bucket, False if it is already in the bucket
            """
            s3 = boto3.resource('s3')
            bucket = s3.Bucket(bucket_name)
            key = object_key
            objs = list(bucket.objects.filter(Prefix=key))
            if any([w.key == path_s3 for w in objs]):
                # exists
                # invert because unavailable
                return not True
            else:
                # doesn't exist
                # invert because available
                return not False

        # # If S3 object_name was not specified, use file_name
        """
        if object_name is None:
            object_name = Template('$DIRECTORY_NAME/$CONTENT_NAME/'+data_file_content.filename).substitute(
                # TODO: Lift bucket folder into configuration
                DIRECTORY_NAME='kge-data', 
                CONTENT_NAME=Path(data_file_content.filename).stem
            )
        """

        # Upload the file
        # TODO: export a single project-wide client
        s3_client = boto3.client('s3', config=Config(region_name='ca-central-1', signature_version='s3v4'))
        if location_available(bucket, object_name) or override:
            try:
                with data_file_content.stream as f:
                    s3_client.upload_fileobj(f, bucket, object_name)
            except ClientError as e:
                print(e)
                return False
            return True
        else:
            return False
    
    # TODO
    def register_smartapi():
        return True

    maybeUploadContent = upload_file(data_file_content, bucket="star-ncats-translator", object_name=object_location+"content/"+data_file_content.filename)
    maybeUploadMetaData = True #or upload_file(data_file_metadata, bucket_name="star-ncats-translator", object_name=object_location+"metadata/"+data_file_metadata.filename)
    maybeRegisterSmartAPI = register_smartapi()
    if maybeUploadContent and maybeUploadMetaData and maybeRegisterSmartAPI:
        # DONE: "Authorization mechanism not provided" Error
        # CANCEL: link to resources? DEEPLINK or API LINK?
            # TODO: Configuration for Hostname?
        # return create_presigned_url(bucket="star-ncats-translator", object_name=object_location+"content/"+data_file_content.filename) 
        return "Success!" #TODO: Success Page
    else:
        # TODO: how to handle failure? Website Redirect?
        return "Failure!" #, (maybeUploadContent, maybeUploadMetaData, maybeRegisterSmartAPI)