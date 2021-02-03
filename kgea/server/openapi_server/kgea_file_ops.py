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
import boto3
from botocore.exceptions import ClientError
from os.path import expanduser, abspath

import random, string
from string import Template
from datetime import datetime

import yaml

"""
Test Parameters + Decorator
"""
TEST_BUCKET=None
TEST_KG_NAME=None
def prepare_test(func):
    def wrapper():
        TEST_BUCKET = 'test_bucket'
        TEST_KG_NAME = 'test_kg'
        func()
    return wrapper

def object_location(kg_name, datetime=datetime.day, content=None):
    object_location = Template('$DIRECTORY_NAME/$KG_NAME/$TIMESTAMP/').substitute(
        DIRECTORY_NAME='kge-data',
        KG_NAME=kg_name,
        TIMESTAMP=datetime
    )
    return object_location

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
        response = s3_client.generate_presigned_url('get_object', Params={'Bucket': bucket, 'Key': object_name}, ExpiresIn=expiration)
    except ClientError as e:
        print(e)
        raise ClientError(e)
    
    # The response contains the presigned URL
    return response

@prepare_test
def test_create_presigned_url():
    pass

def kg_files_in_location(bucket_name, object_location):
    bucket_listings = [e['Key'] for p in s3_client.get_paginator("list_objects_v2").paginate(Bucket=bucket_name) for
                        e in p['Contents']]
    object_matches = [object_name for object_name in bucket_listings if object_location in object_name]
    return object_matches

@prepare_test
def test_kg_files_in_location(test_bucket=TEST_BUCKET, test_kg=TEST_KG_NAME):
    try:
        kg_file_list = kg_files_in_location(bucket_name=test_bucket, object_location=object_location(test_kg))
        assert(len(kg_file_list) > 0)
    except AssertionError as e:
        print(e)
        return False
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
    if any([w.key == key for w in objs]):
        # exists
        # invert because unavailable
        return not True
    else:
        # doesn't exist
        # invert because available
        return not False

@prepare_test
def test_location_available(test_bucket=TEST_BUCKET):

    # https://www.askpython.com/python/examples/generate-random-strings-in-python
    def random_alpha_string(length=8):
        random_string = ''
        for _ in range(length):
            # Considering only upper and lowercase letters
            random_integer = random.randint(97, 97 + 26 - 1)
            flip_bit = random.randint(0, 1)
            # Convert to lowercase if the flip bit is on
            random_integer = random_integer - 32 if flip_bit == 1 else random_integer
            # Keep appending random characters using chr(x)
            random_string += (chr(random_integer))
        return random_string

    try:
        # of length 8 by default
        randomLocationName = random_alpha_string()
        isRandomLocationAvailable = location_available(bucket_name=test_bucket, object_key=object_location(randomLocationName))
        assert(not isRandomLocationAvailable)
    except AssertionError as e:
        print("ERROR: found a non-existing location")
        print(e)
        return False

    """
    TODO: Test in the positive:
    * make dir
    * test for existence
    * close/delete dir
     try:
        randomLocationName = random_alpha_string()
        isRandomLocationAvailable = location_available(bucket_name=test_bucket, object_key=object_location(randomLocationName))
        assert(isRandomLocationAvailable)
    except AssertionError as e:
        print("ERROR: created location was not found")
        print(e)
        return False
    """
    return True

def upload_file(data_file, bucket_name, object_location, override=False):
    """Upload a file to an S3 bucket

    :param file_name: File to upload
    :param bucket: Bucket to upload to
    :param object_name: S3 object name. If not specified then file_name is used
    :return: True if file was uploaded, else False
    """
    object_key = object_location + data_file.filename
    
    # Upload the file
    try:
        with data_file.stream as f:
            s3_client.upload_fileobj(f, bucket_name, object_key)
    except ClientError as error_message:
        return None, error_message
    return object_key, ''

@prepare_test
def test_upload_file(test_bucket=TEST_BUCKET, test_kg=TEST_KG_NAME):
    try:
        with open(abspath('test/data'+'geneToProtein.csv'), 'r') as test_file:
            object_key, error_message = upload_file(test_file, test_bucket, object_location(test_kg))
            if object_key is not None:
                # see if this key successfully points to a resource in the bucket
                assert(object_key in kg_files_in_location(test_bucket, object_location(test_kg)))
            elif object_key is None:
                raise ClientError(error_message)
    except FileNotFoundError as e:
        print("ERROR: Test is malformed!")
        print(e)
        return False
    except ClientError as e:
        print('ERROR: The upload to S3 has failed!')
        print(e)
        return False
    except AssertionError as e:
        print('ERROR: The resulting path was not found inside of the knowledge graph folder!')
        print(e)
        return False
    return True

# TODO
def convert_to_yaml(spec):
    yaml_file = lambda spec: yaml.write(spec)
    return yaml_file(spec)

@prepare_test
def test_convert_to_yaml():
    pass

# TODO
def create_smartapi(submitter):
    spec = {}
    yaml_file = convert_to_yaml(spec)
    return yaml_file

def test_create_smartapi():
    pass

# TODO
def add_to_github(api_specification):
    # using https://github.com/NCATS-Tangerine/translator-api-registry
    repo = ''
    return repo

@prepare_test
def test_add_to_github():
    pass

# TODO
def api_registered(kg_name):
    return True

@prepare_test
def test_api_registered():
    pass
