"""
Knowledge Graph eXchange (KGX) tool kit validation of
Knowledge Graph Exchange (KGE) File Sets located on AWS S3
"""
import threading
import json
from typing import List, Optional, Dict
from sys import stderr
from os.path import dirname, abspath
import time
import asyncio

import logging

from jsonschema import (
    ValidationError,
    SchemaError,
    validate as json_validator
)
from kgx.transformer import Transformer
from kgx.validator import Validator

from kgea.server.config import get_app_config
from kgea.server.web_services.catalog.Catalog import KgeFileType, KgeFileSet
from kgea.server.web_services.models import KgeFileSetStatusCode

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Opaquely access the configuration dictionary
_KGEA_APP_CONFIG = get_app_config()

# one could perhaps parameterize this in the _KGEA_APP_CONFIG
_NUMBER_OF_KGX_VALIDATION_WORKER_TASKS = _KGEA_APP_CONFIG.setdefault("Number_of_KGX_Validation_Worker_Tasks", 3)
# KGX Content Metadata Validator is a simply JSON Schema validation operation
CONTENT_METADATA_SCHEMA_FILE = abspath(dirname(__file__) + '/content_metadata.schema.json')
with open(CONTENT_METADATA_SCHEMA_FILE, mode='r', encoding='utf-8') as cms:
    CONTENT_METADATA_SCHEMA = json.load(cms)


# This first iteration only validates the JSON structure and property tags against the JSON schema
# TODO: perhaps should also check the existence of
#       Biolink node categories and predicates
#       (using the Biolink Model Toolkit)?
def validate_content_metadata(content_metadata_file) -> List:
    errors: List[str] = list()
    if content_metadata_file:
        # see https://python-jsonschema.readthedocs.io/en/stable/validate/
        try:
            json_validator(content_metadata_file, CONTENT_METADATA_SCHEMA)
            logger.error("validate_content_metadata() - content metadata JSON validation was successful!")
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
    
    def __init__(self, tag: str):
        self.tag = tag
        self.kgx_data_validator = Validator()

    # KGX Validation process management
    _validation_queue: asyncio.Queue = asyncio.Queue()
    _validation_tasks: List = list()

    # The method should be called at the beginning of KgxValidator processing
    @classmethod
    def init_validation_tasks(cls):
        # Create _NO_KGX_VALIDATION_WORKER_TASKS worker
        # tasks to concurrently process the validation_queue.
        for i in range(_NUMBER_OF_KGX_VALIDATION_WORKER_TASKS):
            task = asyncio.create_task(KgxValidator(f"KGX Validation Worker-{i}")())
            cls._validation_tasks.append(task)

    # The method should be called by at the end of KgxValidator processing
    @classmethod
    async def shutdown_validation_processing(cls):
        await cls._validation_queue.join()
        try:
            # Cancel the KGX validation worker tasks.
            for task in cls._validation_tasks:
                task.cancel()
            # Wait until all worker tasks are cancelled.
            await asyncio.gather(*cls._validation_tasks, return_exceptions=True)
        except Exception as exc:
            msg = "KgxValidator() KGX worker task exception: " + str(exc)
            logger.error(msg)

    @classmethod
    def validate(cls, file_set: KgeFileSet):
        """This method posts a KgeFileSet to the KgxValidator for validation.
         
        :param file_set: KgeFileSet.
        
        :return: None
        """
        # First, initialize task queue if not running...
        if not cls._validation_tasks:
            cls.init_validation_tasks()
        
        # ...then, post the file set to the KGX validation task Queue
        cls._validation_queue.put_nowait(file_set)

    #
    async def __call__(self):
        """
        This Callable, undertaking the file validation,
        is intended to be executed inside an asyncio task.
        
        :return:
        """
        while True:
            file_set: KgeFileSet = await self._validation_queue.get()

            ###############################################
            # Collect the KGX data files names and metadata
            ###############################################
            input_files: List[str] = list()
            file_type: Optional[KgeFileType] = None
            input_format: Optional[str] = None
            input_compression: Optional[str] = None
            
            for entry in file_set.data_files.values():
                #
                # ... where each entry is a dictionary contains the following keys:
                #
                # "file_name": str
                
                # "file_type": KgeFileType (from Catalog)
                # "input_format": str
                # "input_compression": str
                # "kgx_compliant": bool
                #
                # "object_key": str
                # "s3_file_url": str
                #
                # TODO: we just take the first values encountered, but
                #       we should probably guard against inconsistent
                #       input format and compression somewhere upstream
                if not file_type:
                    file_type = entry["file_type"]
                if not input_format:
                    input_format = entry["input_format"]
                if not input_compression:
                    input_compression = entry["input_compression"]
                    
                file_name = entry["file_name"]
                object_key = entry["object_key"]
                s3_file_url = entry["s3_file_url"]
                
                print(
                    f"KgxValidator() is found file '{file_name}' '{object_key}' " +
                    f"of type '{file_type}', input format '{input_format}' " +
                    f"and with compression '{input_compression}', ",
                    file=stderr
                )
                
                # The file to be processed should currently be
                # a resource accessible from this S3 authenticated URL?
                input_files.append(s3_file_url)

            ###################################
            # ...then, process them together...
            ###################################
            if file_type == KgeFileType.KGX_DATA_FILE:
                validation_errors: List[str] = list()
                #
                # Run validation of KGX knowledge graph data files here
                #
                # --- Uncomment completely activate the validation?
                #
                # file_set.errors.extend(
                #     await self.validate_file_set(
                #         input_files=input_files,
                #         input_format=input_format,
                #         input_compression=input_compression
                #     )
                # )
                lock = threading.Lock()
                with lock:
                    if not validation_errors:
                        file_set.errors.extend(validation_errors)
                        file_set.status = KgeFileSetStatusCode.VALIDATED
                    else:
                        file_set.status = KgeFileSetStatusCode.ERROR

            elif file_type == KgeFileType.KGE_ARCHIVE:
                # TODO: perhaps need more work to properly dissect and
                #       validate a KGX Data archive? Maybe need to extract it
                #       then get the distinct files for processing? Or perhaps,
                lock = threading.Lock()
                with lock:
                    file_set.errors.append("KGE Archive validation is not yet implemented?")
                    file_set.status = KgeFileSetStatusCode.ERROR
            else:
                err_msg = f"WARNING: Unknown KgeFileType{file_type} ... Ignoring?"
                print(err_msg, file=stderr)
                lock = threading.Lock()
                with lock:
                    file_set.errors.append(err_msg)
                    file_set.status = KgeFileSetStatusCode.ERROR
    
            compliance: str = ' not ' if file_set.errors else ' '
            print(
                f"has finished processing. File set '{str(file_set)}' is" +
                compliance + "KGX compliant", file=stderr
            )

            self._validation_queue.task_done()

    @staticmethod
    async def validate_file_set(
            input_files: List[str],
            input_format: str = 'tsv',
            input_compression: Optional[str] = None
    ) -> List:
        """
        Validates KGX compliance of a specified data file.

        :param input_files: list of file path strings pointing to files to be validated (could be a resolvable URL?)
        :param input_format: currently restricted to 'tsv' (its default?) - should be consistent for all input_files
        :param input_compression: currently expected to be 'tar.gz' or 'gz' - should be consistent for all input_files
        :return: (possibly empty) List of errors returned
        """
        logger.debug(
            "Entering KgxValidator.validate_data_file() with arguments:" +
            "\n\tfile_path:" + str(input_files) +
            "\n\tinput_format:" + str(input_format) +
            "\n\tinput_compression:" + str(input_compression)
        )

        if input_files:
            # The putative KGX 'source' input files are currently sitting
            # at the end of S3 signed URLs for streaming into the validation.

            logger.debug("...initializing Validator...")

            class ProgressMonitor:
                def __call__(self):
                    pass

            validator = Validator(progress_monitor=ProgressMonitor())

            logger.debug("...initializing Transformer...")

            transformer = Transformer(stream=True)

            logger.debug("...initiating transform data flow...")

            transformer.transform(
                input_args={
                    'filename': input_files,
                    'format': input_format,
                    'compression': input_compression
                },
                output_args={
                    # we don't keep the graph in memory...
                    # too RAM costly and not needed later
                    'format': 'null'
                },
                inspector=validator
            )

            logger.debug("...retrieving errors (if any):")

            errors = validator.get_error_messages()
            return errors

        else:
            return ["Missing file name inputs for validation?"]


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


def test_contents_data_validator():
    print("\ntest_contents_data_validator() test output:\n", file=stderr)
    
    with open(SAMPLE_META_KNOWLEDGE_GRAPH_FILE, mode='r', encoding='utf-8') as smkg:
        mkg_json = json.load(smkg)
        
    errors: List[str] = validate_content_metadata(mkg_json)
    
    if errors:
        logger.error("test_contents_data_validator() errors: " + str(errors))
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
    run_test(test_contents_data_validator)

    print("tests complete")
