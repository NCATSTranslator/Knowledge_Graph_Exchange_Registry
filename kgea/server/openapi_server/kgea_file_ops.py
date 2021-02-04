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

from os.path import expanduser, abspath, splitext
from pathlib import Path

import random, string
from string import Template
from datetime import datetime

import yaml

import webbrowser
import requests

def create_location(bucket, kg_name):
    return s3_client.put_object(Bucket=bucket, Key=object_location(kg_name))
     
def delete_location(bucket, kg_name):
    return s3_client.delete(Bucket=bucket, Key=object_location(kg_name))

# https://www.askpython.com/python/examples/generate-random-strings-in-python
def _random_alpha_string(length=8):
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

"""
Test Parameters + Decorator
"""
TEST_BUCKET = 'kgea-test-bucket'
TEST_KG_NAME = 'test_kg'
def prepare_test(func):
    def wrapper():
        TEST_BUCKET = 'kgea-test-bucket'
        TEST_KG_NAME = 'test_kg'
        return func()
    return wrapper

def prepare_test_random_object_location(func):

    def wrapper(object_key=_random_alpha_string()):
        s3_client.put_object(
            Bucket='kgea-test-bucket',
            Key=object_location(object_key)
        )
        result = func(test_object_location=object_location(object_key))
        # TODO: prevent deletion for a certain period of time
        s3_client.delete_object(
            Bucket='kgea-test-bucket', 
            Key=object_location(object_key)
        )
        return result

    return wrapper

def object_location(kg_name):
    """
    NOTE: Must be kept deterministic. No datetimes or randomness in this method; they may be appended afterwards.
    """
    object_location = Template('$DIRECTORY_NAME/$KG_NAME/').substitute(
        DIRECTORY_NAME='kge-data',
        KG_NAME=kg_name
    )
    return object_location

def withTimestamp(func, datetime=datetime.now().strftime('%Y%j%H%M%s')):
    def wrapper(kg_name):
        return func(kg_name+'/'+datetime), datetime
    return wrapper

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
        return False
    else:
        # doesn't exist
        # invert because available
        return True

@prepare_test
def test_is_location_available(test_object_location=object_location(_random_alpha_string()), test_bucket=TEST_BUCKET):
    try:
        isRandomLocationAvailable = location_available(bucket_name=test_bucket, object_key=test_object_location)
        return isRandomLocationAvailable
    except AssertionError as e:
        print("ERROR: found a location that should not exist")
        print(e)
        return False
    return True

@prepare_test
@prepare_test_random_object_location   # note: use this decorator only if the child function satisfies `test_object_location` in its arguments 
def test_is_not_location_available(test_object_location, test_bucket=TEST_BUCKET):
    """
    Test in the positive:
    * make dir
    * test for existence
    * assert not True (because it already exists)
    * close/delete dir
    """
    try:
        isRandomLocationAvailable = location_available(bucket_name=test_bucket, object_key=test_object_location)
        assert(isRandomLocationAvailable is not True)
    except AssertionError as e:
        print("ERROR: created location was not found")
        print(e)
        return False
    return True

def kg_files_in_location(bucket_name, object_location):
    bucket_listings = [e['Key'] for p in s3_client.get_paginator("list_objects_v2").paginate(Bucket=bucket_name) for
                        e in p['Contents']]
    print(bucket_listings, object_location)
    object_matches = [object_name for object_name in bucket_listings if object_location in object_name]
    return object_matches

@prepare_test
@prepare_test_random_object_location   # note: use this decorator only if the child function satisfies `test_object_location` in its arguments 
def test_kg_files_in_location(test_object_location, test_bucket=TEST_BUCKET):
    try:
        kg_file_list = kg_files_in_location(bucket_name=test_bucket, object_location=test_object_location)
        assert(len(kg_file_list) > 0)
    except AssertionError as e:
        raise AssertionError(e)
    return True



# TODO: clarify expiration time
def create_presigned_url(bucket, object_key, expiration=3600):
    """Generate a presigned URL to share an S3 object

    :param bucket: string
    :param object_key: string
    :param expiration: Time in seconds for the presigned URL to remain valid
    :return: Presigned URL as string. If error, returns None.
    """
    
    # Generate a presigned URL for the S3 object
    # https://stackoverflow.com/a/52642792
    try:
        response = s3_client.generate_presigned_url('get_object', Params={'Bucket': bucket, 'Key': object_key}, ExpiresIn=expiration)
    except ClientError as e:
        raise ClientError(e)
    
    # The response contains the presigned URL
    return response

@prepare_test
def test_create_presigned_url(test_bucket=TEST_BUCKET, test_kg_name=TEST_KG_NAME):
    try:
        # TODO: write tests
        create_presigned_url(bucket=test_bucket, object_key=object_location(TEST_KG_NAME))
    except AssertionError as e:
        print('ERROR:', e)
        return False
    except ClientError as e:
        print('ERROR:', e)
        return False
    return True

def upload_file(data_file, file_name, bucket_name, object_location, override=False):
    """Upload a file to an S3 bucket

    :param file_name: File to upload (can be read in binary mode)
    :param bucket: Bucket to upload to
    :param object_name: S3 object name. If not specified then file_name is used
    :return: True if file was uploaded, else False
    """
    object_key = Template('$ROOT$FILENAME$EXTENSION').substitute(
        ROOT = object_location,
        FILENAME = Path(file_name).stem,
        EXTENSION = splitext(file_name)[1]
    )

    # Upload the file
    try:
        s3_client.upload_fileobj(data_file, bucket_name, object_key)
    except ClientError as error_message:
        raise ClientError(error_message)
    return object_key

@prepare_test
def test_upload_file(test_bucket=TEST_BUCKET, test_kg=TEST_KG_NAME):
    try:
        # NOTE: file must be read in binary mode!
        with open(abspath('test/data/'+'somedata.csv'), 'rb') as test_file:
            object_key = upload_file(test_file, test_file.name, test_bucket, object_location(test_kg))
            assert(object_key in kg_files_in_location(test_bucket, object_location(test_kg)))
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

@prepare_test
def test_upload_file_timestamp(test_bucket=TEST_BUCKET, test_kg=TEST_KG_NAME):
    """
    Use the "withTimestamp" wrapper to modify the object location
    """
    try:
        test_location, time_created = withTimestamp(object_location)(test_kg)
        # NOTE: file must be read in binary mode!
        with open(abspath('test/data/'+'somedata.csv'), 'rb') as test_file:
            object_key = upload_file(test_file, test_file.name, test_bucket, test_location)
            assert(object_key in kg_files_in_location(test_bucket, test_location))
            assert(time_created in object_key)
    except FileNotFoundError as e:
        print("ERROR: Test is malformed!")
        print(e)
        return False
    except ClientError as e:
        print('ERROR: The upload to S3 has failed!')
        print(e)
        return False
    except AssertionError as e:
        print('ERROR: The resulting path was not found inside of the knowledge graph folder, OR the timestamp isn\'t in the path!')
        print(e)
        return False
    return True

def download_file(bucket, object_key, openFile=False):
    download_url = create_presigned_url(bucket=bucket, object_key=object_key)
    if openFile:
        return download_url, webbrowser.open_new_tab(download_url)
    return download_url
    

@prepare_test
# @prepare_test_random_object_location
def test_download_file(test_object_location=None, test_bucket=TEST_BUCKET, test_kg_name=TEST_KG_NAME):
    try:
        with open(abspath('test/data/'+'somedata.csv'), 'rb') as test_file:
            object_key = upload_file(test_file, test_file.name, test_bucket, object_location(test_kg_name))
            url = download_file(bucket=test_bucket, object_key=object_location(test_kg_name)+'somedata.csv', openFile=False)  # openFile=False to affirm we won't trigger a browser action
            response = requests.get(url)
            assert(response.status_code is 200)
            # TODO: test for equal content from download response
    except FileNotFoundError as e:
        print("ERROR: Test is malformed!")
        print(e)
        return False
    except AssertionError as e:
        print('ERROR: URL is not returning a downloadable resource (response code is not 200)')
        print(e)
        return False
    return True

# TODO
def convert_to_yaml(spec):
    yaml_file = lambda spec: yaml.write(spec)
    return yaml_file(spec)

# TODO
@prepare_test
def test_convert_to_yaml():
    return True


# TODO
def create_smartapi(submitter):
    spec = {}
    yaml_file = convert_to_yaml(spec)
    return yaml_file

# TODO
@prepare_test
def test_create_smartapi():
    return True

# TODO
def add_to_github(api_specification):
    # using https://github.com/NCATS-Tangerine/translator-api-registry
    repo = ''
    return repo

# TODO
@prepare_test
def test_add_to_github():
    return True

# TODO
def api_registered(kg_name):
    return True

# TODO
@prepare_test
def test_api_registered():
    return True

"""
Unit Tests
* Run each test function as an assertion if we are debugging the project
"""
DEBUG = False
if DEBUG:
    assert(test_kg_files_in_location()) 
    print("test_kg_files_in_location passed")

    assert(test_is_location_available())
    print("test_is_location_available passed")

    assert(test_is_not_location_available())
    print("test_is_not_location_available passed")

    assert(test_create_presigned_url())
    print("test_create_presigned_url passed")

    assert(test_upload_file())
    print("test_upload_file passed")

    assert(test_upload_file_timestamp())
    print("test_upload_file_timestamp passed")

    assert(test_download_file())
    print("test_download_file passed")

    print("TODO: Smart API Registry functions and tests")
    assert(test_convert_to_yaml())
    assert(test_add_to_github())
    assert(test_api_registered()) 
    
    print("all file ops tests passed")