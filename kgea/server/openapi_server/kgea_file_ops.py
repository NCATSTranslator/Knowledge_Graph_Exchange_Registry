"""
Implement robust KGE File Set upload process:
o  “layered” back end unit tests of each level of S3 upload process
o  Figure out the minimal S3 access policy that suffices for the KGE Archive (not a huge priority this week but…)
o  File set versioning using time stamps
o  Web server optimization (e.g. NGINX / WSGI / web application parameters)
o  Test the system (both manually, by visual inspection of uploads)
Stress test using SRI SemMedDb: https://github.com/NCATSTranslator/semmeddb-biolink-kg
"""

from .kgea_config import s3_client

def upload_file(data_file, bucket_name, object_location, content_type, override=False):
    """Upload a file to an S3 bucket

    :param file_name: File to upload
    :param bucket: Bucket to upload to
    :param object_name: S3 object name. If not specified then file_name is used
    :return: True if file was uploaded, else False
    """
    object_key = object_location + content_type + '/' + data_file.filename
    
    # Upload the file
    try:
        with data_file.stream as f:
            s3_client.upload_fileobj(f, bucket_name, object_key)
    except ClientError as e:
        # TODO: replace with logger
        print(e)
        return None
    return object_key

def test_upload_file():
    pass

# TODO: clarify expiration time
def create_presigned_url(bucket, object_name, expiration=3600):
    """Generate a presigned URL to share an S3 object

    :param bucket: string
    :param object_name: string
    :param expiration: Time in seconds for the presigned URL to remain valid
    :return: Presigned URL as string. If error, returns None.
    """
    
    # Generate a presigned URL for the S3 object
    # https://stackoverflow.com/a/52642792
    try:
        response = s3_client.generate_presigned_url('get_object',
                                                    Params={'Bucket': bucket,
                                                            'Key': object_name},
                                                    ExpiresIn=expiration)
    except ClientError as e:
        print(e)
        return None
    
    # The response contains the presigned URL
    return response

def test_create_presigned_url():
    pass

def kg_files_in_location(bucket_name, object_location):
    # s3_client = boto3.client('s3', config=Config(signature_version='s3v4'))
    
    # TODO: Warning! Doesn't scale very well, looks somewhat unsafe. What other options do we have to query the bucket?
    bucket_listings = [e['Key'] for p in s3_client.get_paginator("list_objects_v2").paginate(Bucket=bucket_name) for
                        e in p['Contents']]
    object_matches = [object_name for object_name in bucket_listings if object_location in object_name]
    
    return object_matches

def test_kg_files_in_location():
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
    if any([w.key == key for w in objs]):
        # exists
        # invert because unavailable
        return not True
    else:
        # doesn't exist
        # invert because available
        return not False

def test_location_available():
    pass

# TODO
def convert_to_yaml(spec):
    yaml_file = lambda spec: spec
    return yaml_file(spec)

def test_convert_to_yaml():
    pass

# TODO
def create_smartapi(submitter, kg_name):
    spec = {}
    yaml_file = convert_to_yaml(api_specification)
    return spec

def test_create_smartapi():
    pass

# TODO
def add_to_github(api_specification):
    # using https://github.com/NCATS-Tangerine/translator-api-registry
    repo = ''
    return repo

def test_add_to_github():
    pass

# TODO
def api_registered(kg_name):
    return True

def test_api_registered():
    pass
