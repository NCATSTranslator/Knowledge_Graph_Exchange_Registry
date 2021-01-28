import connexion
import six

from openapi_server.models.attribute import Attribute  # noqa: E501
from openapi_server import util
from string import Template
import boto3
from botocore.client import Config

from flask import redirect, send_file

def access(kg_name):  # noqa: E501
    """Get KGE File Sets

     # noqa: E501

    :param kg_name: Name label of KGE File Set whose files are being accessed
    :type kg_name: str

    :rtype: Dict[str, Attribute]
    """

    object_location = Template('$DIRECTORY_NAME/$KG_NAME/content/').substitute(
        DIRECTORY_NAME='kge-data', 
        # TODO
        KG_NAME=kg_name
    # TODO: filetype?
    )+kg_name+".csv"

    # TODO apply bucket configuration here
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

    url = create_presigned_url(bucket="star-ncats-translator", object_name=object_location)
    if url is not None:
        # TODO: authentication?
        return redirect(url)
    else:
        # TODO
        return "Request Failed"
