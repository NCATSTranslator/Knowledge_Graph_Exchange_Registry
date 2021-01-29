import connexion
import six

from openapi_server import util


def get_upload_form():  # noqa: E501
    """Get web form for specifying KGE File Set upload

     # noqa: E501


    :rtype: str
    """
    return 'do some magic!'


def register_file_set(submitter, kg_name):  # noqa: E501
    """Register web form details specifying a KGE File Set location

     # noqa: E501

    :param submitter: 
    :type submitter: str
    :param kg_name: 
    :type kg_name: str

    :rtype: str
    """
    return 'do some magic!'


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

    object_location = Template('$DIRECTORY_NAME/$KG_NAME/$CONTENT_TYPE/').substitute(
        DIRECTORY_NAME='kge-data', 
        CONTENT_TYPE='content'
        KG_NAME=Path(data_file_content.filename).stem
    )

    def upload_file(data_file_content, bucket, object_name, override=False):
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

        # Upload the file
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