"""
Knowledge Graph eXchange (KGX) tool kit validation of
Knowledge Graph Exchange (KGE) File Sets located on AWS S3
"""
import json
from typing import List, Optional
from sys import stderr
from os.path import dirname, abspath
import time

import logging

from jsonschema import (
    ValidationError,
    SchemaError,
    validate as json_validator
)
from kgx.transformer import Transformer
from kgx.validator import Validator

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# KGX Content Metadata Validator is a simply JSON Schema validation operation
CONTENT_METADATA_SCHEMA_FILE = abspath(dirname(__file__) + '/content_metadata.schema.json')
with open(CONTENT_METADATA_SCHEMA_FILE, mode='r', encoding='utf-8') as cms:
    CONTENT_METADATA_SCHEMA = json.load(cms)


# This first iteration only validates the JSON structure and property tags against the JSON schema
# TODO: perhaps also semantically validate Biolink node categories and predicates (using the Biolink Model Toolkit)?
def validate_content_metadata(content_metadata_file) -> List:
    errors: List[str] = list()
    if content_metadata_file:
        # see https://python-jsonschema.readthedocs.io/en/stable/validate/
        try:
            json_validator(content_metadata_file, CONTENT_METADATA_SCHEMA)
        except ValidationError as ve:
            logger.error("validate_content_metadata() - ValidationError: " + str(ve))
            errors.append(str(ve))
        except SchemaError as se:
            logger.error("validate_content_metadata() - SchemaError: " + str(se))
            errors.append(str(se))
        return errors
    else:
        return ["No file name provided - nothing to validate"]


class KgxValidator:
    
    def __init__(self):
        self.kgx_data_validator = Validator()
    
    async def validate_data_file(
            self,
            file_path: str,
            input_format: str = 'tsv',
            input_compression: Optional[str] = None,
            output: Optional[str] = None
    ) -> List:
        """
        Validates KGX compliance of a specified data file.
        
        :param file_path: string specification of a single file path (may be a resolvable URL?)
        :param input_format: currently restricted to 'tsv' (its default?)
        :param input_compression: currently expected to be 'tar.gz' or 'gz'
        :param output: default None
        :return: (possibly empty) List of errors returned
        """
        
        if file_path:
            # The putative KGX file 'source' is currently sitting at the end
            # of an S3 signed URL(!?) for streaming into the validation.
            
            validator = Validator()

            transformer = Transformer(stream=True)

            transformer.transform(
                input_args={'filename': [file_path], 'format': input_format, 'compression': input_compression},
                output_args={'format': 'null'},
                inspector=validator
            )

            errors = validator.get_errors()
            if errors:
                if output:
                    self.kgx_data_validator.write_report(open(output, 'w'))
                else:
                    self.kgx_data_validator.write_report(stderr)

            # as a sanity check, force error data
            # returned into a list of string error messages
            return [str(error) for error in errors]
        
        else:
            return ["Empty file source"]


"""
Test Parameters + Decorator
"""
TEST_BUCKET = 'kgea-test-bucket'
TEST_KG_NAME = 'test_kg'
TEST_FILE_DIR = 'kgea/server/test/data/'
TEST_FILE_NAME = 'somedata.csv'


SAMPLE_META_KNOWLEDGE_GRAPH_FILE = abspath(dirname(__file__) + '/sample_meta_knowledge_graph.json')


def test_contents_metadata_validator():
    print("\ntest_contents_metadata_validator() test output:\n", file=stderr)
    with open(SAMPLE_META_KNOWLEDGE_GRAPH_FILE, mode='r', encoding='utf-8') as smkg:
        mkg_json = json.load(smkg)
    errors: List[str] = validate_content_metadata(mkg_json)
    if errors:
        logger.error("test_contents_metadata_validator() errors: " + str(errors))
    return not errors


def run_test(test_func):
    try:
        start = time.time()
        assert (test_func())
        end = time.time()
        print("{} passed: {} seconds".format(test_func.__name__, end - start))
    except Exception as e:
        logger.error("{} failed!".format(test_func.__name__))
        logger.error(e)


# Unit tests run when module is run as a script
if __name__ == '__main__':
    
    run_test(test_contents_metadata_validator)
    
    print("tests complete")
