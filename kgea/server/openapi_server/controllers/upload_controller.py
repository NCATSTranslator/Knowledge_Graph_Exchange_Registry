import connexion
import six

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


def register_file_set(body):  # noqa: E501
    """Register web form details specifying a KGE File Set location

     # noqa: E501

    :param submitter: 
    :type submitter: str
    :param kg_name: 
    :type kg_name: str

    :rtype: str
    """
    submitter = body['submitter']
    kg_name = body['kg_name']

    object_location = Template('$DIRECTORY_NAME/$KG_NAME/').substitute(
        DIRECTORY_NAME='kge-data', 
        KG_NAME=kg_name
    )
    
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

    def register_smartapi(submitter, kg_name):
        # using https://github.com/NCATS-Tangerine/translator-api-registry

        def create_smartapi(submitter, kg_name):
            spec = {}
            return spec

        def convert_to_yaml(spec):
            yaml_file = lambda x: spec
            return yaml_file()

        def add_to_github():
            repo = ''
            return repo

        api_specification = create_smartapi(submitter, kg_name)
        yaml_file = convert_to_yaml(api_specification)
        url = add_to_github(yaml_file)

        return api_specification, url

    smart_api_data = register_smartapi(submitter, kg_name)
    
    return {
        url: smart_api_data[0],
        api: smart_api_data[1] 
    }


def upload_file_set(kg_name, data_file_content, data_file_metadata=None):  # noqa: E501
    """Upload web form details specifying a KGE File Set upload process

     # noqa: E501

    :param kg_name: 
    :type kg_name: str
    :param data_file_content: 
    :type data_file_content: str
    :param data_file_metadata: 
    :type data_file_metadata: str

    :rtype: str
    """

    print(kg_name, data_file_content, data_file_metadata)

    object_location = Template('$DIRECTORY_NAME/$KG_NAME/').substitute(
        DIRECTORY_NAME='kge-data', 
        KG_NAME=kg_name
    )

    def upload_file(data_file, bucket_name, object_location, content_type, override=False):
        """Upload a file to an S3 bucket

        :param file_name: File to upload
        :param bucket: Bucket to upload to
        :param object_name: S3 object name. If not specified then file_name is used
        :return: True if file was uploaded, else False
        """

        def registered(kg_name):
            pass

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

        object_key = object_location + content_type + '/' + data_file

        # Upload the file
        s3_client = boto3.client('s3', config=Config(region_name='ca-central-1', signature_version='s3v4'))
        if api_registered(kg_name) and not location_available(bucket_name, object_location) or override:
            try:
                with data_file.stream as f:
                    s3_client.upload_fileobj(f, bucket_name, object_name)
            except ClientError as e:
                print(e)
                return False
            return True
        else:
            return False
    
    def register_smartapi():
        # using https://github.com/NCATS-Tangerine/translator-api-registry
        return True

    maybeUploadContent = upload_file(data_file_content, bucket_name="star-ncats-translator", object_location=object_location, content_type="content") 
    maybeUploadMetaData = None or upload_file(data_file_metadata, bucket_name="star-ncats-translator", object_location=object_location, content_type="metadata")
    
    if maybeUploadContent or maybeUploadMetaData:
        return {
            [data_file_content.filename]: maybeUploadContent,
            [data_file_metadata.filename]: maybeUploadMetaData
        }
    else:
        return "Failure!"