import connexion
import six

from openapi_server import util

from string import Template
from pathlib import Path

import boto3
from botocore.client import Config

from flask import redirect, send_file, make_response


def knowledge_map(kg_name):  # noqa: E501
    """Get supported relationships by source and target

     # noqa: E501

    :param kg_name: Name label of KGE File Set whose knowledge graph content metadata is being reported
    :type kg_name: str

    :rtype: Dict[str, Dict[str, List[str]]]
    """

    object_location = Template('$DIRECTORY_NAME/$KG_NAME/$CONTENT_TYPE/').substitute(
        DIRECTORY_NAME='kge-data', 
        KG_NAME=kg_name,
        CONTENT_TYPE='metadata'
    )

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

    def kg_files_in_location(bucket_name, object_location):
        s3_client = boto3.client('s3', config=Config(region_name='ca-central-1', signature_version='s3v4'))
        
        # TODO: Warning! Doesn't scale very well, looks somewhat unsafe. What other options do we have to query the bucket?
        bucket_listings = [e['Key'] for p in s3_client.get_paginator("list_objects_v2").paginate(Bucket=bucket_name) for e in p['Contents']]
        object_matches = [object_name for object_name in bucket_listings if object_location in object_name]

        return object_matches

    # Redirect Approach
    # TODO: https://boto3.amazonaws.com/v1/documentation/api/1.12.1/guide/s3-example-configuring-buckets.html
    """
    url = create_presigned_url(bucket="star-ncats-translator", object_name=object_location)
    if url is not None:
        # TODO: authentication?
        response = make_response(redirect(url))
        response['Access-Control-Allow-Origin'] = "https://star-ncats-translator.s3.amazonaws.com"
        return response
    else:
        # TODO
        return "Request Failed"
    """

    # Listings Approach
    # - Introspect on Bucket
    # - Create URL per Item Listing
    # - Send Back URL with Dictionary
    # OK in case with multiple files (alternative would be, archives?). A bit redundant with just one file.
    kg_files = kg_files_in_location(bucket_name='star-ncats-translator', object_location=object_location)
    kg_listing = dict(map(lambda kg_file: [ Path(kg_file).stem, create_presigned_url('star-ncats-translator', kg_file) ], kg_files))
    return kg_listing

    # Download Approach
    # DEPRECATED: would involve striping large files locally before sending them over? I don't think so! Unless we can stream it (and even then...)
    # s3_client = boto3.client('s3', config=Config(region_name='ca-central-1', signature_version='s3v4'))
    # with open('FILE_NAME', 'wb') as f:
    #     s3.download_fileobj('BUCKET_NAME', 'OBJECT_NAME', f)

    
