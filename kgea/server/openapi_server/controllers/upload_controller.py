import connexion
import six

import boto3
from botocore.exceptions import ClientError
from botocore.client import Config

import yaml

from string import Template
from pathlib import Path

from Flask import abort

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
            API Files: <input type="file" name="data_file_content"><br>
            API Metadata: <input type="file" name="data_file_metadata"><br>
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

    # TODO
    def create_smartapi(submitter, kg_name):
        spec = {}

         def convert_to_yaml(spec):
            yaml_file = lambda spec: spec
            return yaml_file(spec)

        yaml_file = convert_to_yaml(api_specification)

        return spec

    # TODO
    def add_to_github(api_specification):
        # using https://github.com/NCATS-Tangerine/translator-api-registry
        repo = ''
        return repo

    api_specification = create_smartapi(submitter, kg_name)
    url = add_to_github(api_specification)

    if api_specification and url:
        return dict({
            "url": url,
            "api": api_specification
        })
    else:
        abort(400)

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
        object_key = object_location + content_type + '/' + data_file.filename
        
        # Upload the file
        s3_client = boto3.client('s3', config=Config(region_name='ca-central-1', signature_version='s3v4'))
        try:
            with data_file.stream as f:
                s3_client.upload_fileobj(f, bucket_name, object_key)
        except ClientError as e:
            # TODO: replace with logger
            print(e)
            return None
        return object_key

    # TODO
    def api_registered(kg_name):
        return True 

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

    # if api_registered(kg_name) and not location_available(bucket_name, object_location) or override:
    maybeUploadContent = upload_file(data_file_content, bucket_name="star-ncats-translator", object_location=object_location, content_type="content") 
    maybeUploadMetaData = None or upload_file(data_file_metadata, bucket_name="star-ncats-translator", object_location=object_location, content_type="metadata")
    
    def create_presigned_url(bucket, object_name, expiration=3600):
        """Generate a presigned URL to share an S3 object

        :param bucket: string
        :param object_name: string
        :param expiration: Time in seconds for the presigned URL to remain valid
        :return: Presigned URL as string. If error, returns None.
        """

        # Generate a presigned URL for the S3 object
        # TODO: https://stackoverflow.com/a/52642792
        s3_client = boto3.client('s3', config=Config(region_name='ca-central-1', signature_version='s3v4'))
        try:
            response = s3_client.generate_presigned_url('get_object',
                                                        Params={'Bucket': bucket,
                                                                'Key': object_name},
                                                        ExpiresIn=expiration)
        except ClientError as e:
            logging.error(e)
            return None

        # The response contains the presigned URL
        return response



    if maybeUploadContent or maybeUploadMetaData:
        response = { "content": dict({}), "metadata": dict({}) }

        content_name = Path(maybeUploadContent).stem
        content_url = create_presigned_url(bucket="star-ncats-translator", object_name=maybeUploadContent)
        if response["content"][content_name] is None:
            abort(400)
        else:
            response["content"][content_name] = content_url

        if maybeUploadMetaData:
            metadata_name = Path(maybeUploadMetaData).stem
            metadata_url = create_presigned_url(bucket="star-ncats-translator", object_name=maybeUploadMetaData)
            if response["metadata"][metadata_name] is not None:
                response["metadata"][metadata_name] = metadata_url
            # don't care if not there since optional

        return response
    else:
        abort(400)