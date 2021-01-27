import connexion
import six

from openapi_server import util

import logging
import boto3
from botocore.exceptions import ClientError
import yaml

from string import Template

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
    # TODO: Lift bucket into configuration
    def upload_file(data_file_content, bucket="star-ncats-translator", object_name, override=False):
        # print(data_file_content.filename, dir(data_file_content.name))
        """Upload a file to an S3 bucket

        :param file_name: File to upload
        :param bucket: Bucket to upload to
        :param object_name: S3 object name. If not specified then file_name is used
        :return: True if file was uploaded, else False
        """

        def check_location(object):
            pass

        # # If S3 object_name was not specified, use file_name
        if object_name is None:
            object_name = data_file_content.filename

        # Upload the file
        s3_client = boto3.client('s3')
        try:
            with data_file_content.stream as f:
                s3_client.upload_fileobj(
                    f, 
                    bucket, 
                    Template('$DIRECTORY_NAME/'+object_name).substitute(DIRECTORY_NAME='kge-data'), 
                )
        except ClientError as e:
            return False
        return True

    if upload_file(data_file_content):
        return "Success!"
    else:
        return "Failure!"