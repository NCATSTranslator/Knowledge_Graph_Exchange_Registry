"""
KGE Interface module to the operational management of
File Sets within Knowledge Graph eXchange (KGX) application.

Set the RUN_TESTS environment variable to a non-blank value
whenever you wish to run the unit tests in this module...
Set the CLEAN_TESTS environment variable to a non-blank value
to clean up test outputs from RUN_TESTS runs.

The values for the Translator SmartAPI endpoint are hard coded
in the module for now but may change in the future.

TRANSLATOR_SMARTAPI_REPO = "NCATS-Tangerine/translator-api-registry"
KGE_SMARTAPI_DIRECTORY = "translator_knowledge_graph_archive"
"""
import io
import json
from sys import stderr
from os import getenv
from os.path import abspath, dirname
import asyncio
from io import BytesIO
from typing import Dict, Union, Set, List, Any, Optional

# TODO: maybe convert Catalog components to Python Dataclasses?
# from dataclasses import dataclass

from enum import Enum
from string import Template
from json import dumps

import yaml

from kgea.server.web_services.models import (
    KgeFileSetStatus,
    KgeFileSetStatusCode,
    KgeFile
)

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

import logging

from github import Github
from github.GithubException import UnknownObjectException

from kgea.server.config import (
    get_app_config,
    PROVIDER_METADATA_FILE,
    FILE_SET_METADATA_FILE
)

from kgea.server.web_services.kgea_file_ops import (
    get_default_date_stamp,
    get_object_location,
    get_archive_contents,
    with_version,
    load_s3_text_file
)
from .kgea_kgx import KgxValidator, validate_content_metadata
from kgea.server.web_services.kgea_file_ops import upload_file

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

DEV_MODE = getenv('DEV_MODE', default=False)
OVERRIDE = True

RUN_TESTS = getenv('RUN_TESTS', default=False)
CLEAN_TESTS = getenv('CLEAN_TESTS', default=False)


def prepare_test(func):
    def wrapper():
        print("\n" + str(func) + " ----------------\n")
        return func()
    return wrapper


#
# Until we are confident about the KGE File Set publication
# We will post our Translator SmartAPI entries to a local KGE Archive folder
#
# TRANSLATOR_SMARTAPI_REPO = "NCATS-Tangerine/translator-api-registry"
# KGE_SMARTAPI_DIRECTORY = "translator_knowledge_graph_archive"
TRANSLATOR_SMARTAPI_REPO = "NCATSTranslator/Knowledge_Graph_Exchange_Registry"
KGE_SMARTAPI_DIRECTORY = "kgea/server/tests/output"

# Opaquely access the configuration dictionary
_KGEA_APP_CONFIG = get_app_config()

# one could perhaps parameterize this in the KGEA_APP_CONFIG
_NUMBER_OF_KGX_VALIDATION_WORKER_TASKS = _KGEA_APP_CONFIG.setdefault("Number_of_KGX_Validation_Worker_Tasks", 3)


PROVIDER_METADATA_TEMPLATE_FILE_PATH = \
    abspath(dirname(__file__) + '/../../../api/kge_provider_metadata.yaml')
FILE_SET_METADATA_TEMPLATE_FILE_PATH = \
    abspath(dirname(__file__) + '/../../../api/kge_file_set_metadata.yaml')
TRANSLATOR_SMARTAPI_TEMPLATE_FILE_PATH = \
    abspath(dirname(__file__) + '/../../../api/kge_smartapi_entry.yaml')


def _populate_template(filename, **kwargs) -> str:
    """
    Reads in a string template and populates it with provided named parameter values
    """
    with open(filename, 'r') as template_file:
        template = template_file.read()
        # Inject KG-specific parameters into template
        populated_template = Template(template).substitute(**kwargs)
        return populated_template


def format_and_compression(file_name):
    # assume that format and compression is encoded in the file_name
    # as standardized period-delimited parts of the name. This is a
    # hacky first version of this method that only recognizes common
    # KGX file input format and compression.
    part = file_name.split('.')
    if 'tsv' in part:
        input_format = 'tsv'
    else:
        input_format = ''

    if 'tar' in part:
        archive = 'tar'
    else:
        archive = None

    if 'gz' in part:
        compression = ''
        if archive:
            compression = archive + "."
        compression += 'gz'
    else:
        compression = None

    return input_format, compression

class KgeFileType(Enum):
    KGX_UNKNOWN = "unknown file type"
    KGX_CONTENT_METADATA_FILE = "KGX metadata file"
    KGX_DATA_FILE = "KGX data file"
    KGE_ARCHIVE = "KGE data archive"


class KgeFileSet:
    """
    Class wrapping information about a specific released version of
    KGE Archive managed File Set, effectively 'owned' (hence revisable) by a submitter.
    """
    def get_submitter(self):
        return self.submitter

    def get_submitter_email(self):
        return self.submitter_email
    
    def get_version(self):
        return self.kg_version

    def get_date_stamp(self):
        return self.date_stamp
    
    def get_data_file_names(self) -> Set[str]:
        return set(self.data_files.keys())

    def __init__(
            self,
            kg_id: str,
            kg_version: str,
            submitter: str,
            submitter_email: str,
            size: str = 'unknown',
            revisions: str = 'creation',
            date_stamp: str = get_default_date_stamp(),
            validate: bool = True
    ):
        """
        KgeFileSet constructor

        :param kg_id: version identifier of the knowledge graph to which the file set belongs
        :param kg_version: version identifier of the file set
        :param submitter: human readable name of the submitter/owner of the file set
        :param submitter_email: email address of the submitter
        """
        self.kg_id = kg_id
        self.kg_version = kg_version
        self.submitter = submitter
        self.submitter_email = submitter_email

        # KGE File Set archive size, may initially be unknown
        self.size = size
        self.revisions = revisions
        self.date_stamp = date_stamp

        # this attribute will track all metadata files of the given version of KGE File Set
        self.content_metadata: Dict[str, Union[str, bool, List[str]]] = dict()

        # this attribute will track all data files of the given version of KGE File Set
        self.data_files: Dict[str, Dict[str, Union[str, bool, List[str]]]] = dict()

        # ### KGX VALIDATION FRAMEWORK ###

        # The initial design of the system is designed to manage
        # validation tasks locally within each distinct KGE File Set.

        # Aiming for a more economical design with reduced process overheads
        # may suggest use of a single "class level" central Queue
        # for validation across all file sets from all knowledge graphs.
        self.status: KgeFileSetStatusCode = KgeFileSetStatusCode.CREATED

        # no errors to start
        self.errors: List[str] = list()
        
        if validate:

            # KGX Validator singleton for this KGE File Set
            self.validator = KgxValidator()

            # this Queue serves at the communication link
            # between a KGX validation process and the Registry
            self.validation_queue = asyncio.Queue()

            # Create _NO_KGX_VALIDATION_WORKER_TASKS worker
            # tasks to concurrently process the validation_queue.
            self.tasks = []

            # Validation worker tasks set running
            for i in range(_NUMBER_OF_KGX_VALIDATION_WORKER_TASKS):
                task = asyncio.create_task(
                    self.validate(
                        f"KGX Validation Worker-{i} for KG Id '" + self.kg_id + "'"
                    )
                )
                self.tasks.append(task)
        else:
            # File Set read in from the Archive
            # TODO: need to verify that the file set is indeed KGX compliant
            self.status = KgeFileSetStatusCode.LOADED

    # Note: content metadata file is already normalized on S3 to 'content_metadata.yaml'
    def set_content_metadata_file(self, file_name: str, object_key: str, s3_file_url: str):
        """
        Sets the metadata file identification for a KGE File Set
        :param file_name: original name of metadata file.

        :param object_key:
        :param s3_file_url:
        :return: None
        """
        self.content_metadata = {
            "file_name": file_name,
            "object_key": object_key,
            "s3_file_url": s3_file_url,
            "kgx_compliant": False,  # until proven True...
            "errors": []
        }

        content_metadata_file_text = load_s3_text_file(
            bucket_name=_KGEA_APP_CONFIG['bucket'],
            object_name=object_key
        )
        # Must load the JSON into a Python dictionary for validation
        metadata_json = json.loads(content_metadata_file_text)
        errors = validate_content_metadata(metadata_json)

        if not errors:
            self.content_metadata["kgx_compliant"] = True
        else:
            self.content_metadata["errors"] = errors

    def add_data_file(
            self,
            file_name: str,
            file_type: KgeFileType,
            object_key: str,
            s3_file_url: str
    ):
        """
        Adds a (meta-)data file to this current of KGE File Set.

        :param file_name: to add to the KGE File Set
        :param file_type: KgeFileType of file being added to the KGE File Set
        :param object_key: of the file in AWS S3
        :param s3_file_url: current S3 pre-signed data access url

        :return: None
        """

        # Attempt to infer the format and compression of the data file from its filename
        input_format, input_compression = self.format_and_compression(file_name)

        self.data_files[object_key] = {
            "file_name": file_name,
            "object_key": object_key,
            "s3_file_url": s3_file_url,
            "kgx_compliant": False,  # until proven True...
            "input_format": input_format,
            "input_compression": input_compression,
            "errors": []
        }

        # trigger asynchronous KGX metadata file validation process here?
        logger.debug(
            "Checking if " + str(file_type) +
            " data file, with object_key = '" + object_key +
            "' is KGX compliant"
        )

        if file_type == KgeFileType.KGX_DATA_FILE:
            input_format = self.data_files[object_key]["input_format"]
            input_compression = self.data_files[object_key]["input_compression"]

        elif file_type == KgeFileType.KGE_ARCHIVE:
            # This is probably wrong, but...
            input_format = self.data_files[object_key]["input_format"]
            input_compression = self.data_files[object_key]["input_compression"]

        else:
            input_format = input_compression = None

        kge_file_spec = {
            "file_type": file_type,
            "object_key": object_key,
            "s3_file_url": s3_file_url,
            "input_format": input_format,
            "input_compression": input_compression
        }

        # Post KGX data file specifications to validation task Queue
        self.validation_queue.put_nowait(kge_file_spec)

    def add_data_files(self, data_files: Dict[str, Dict[str, Any]]):
        """
        Bulk addition of data files to the KGE File Set may only
        receive an AWS S3 object_key indexed dictionary of file names.
        The files are not further validated for KGX format compliance.
        """
        self.data_files.update(data_files)

    def remove_data_file(self, data_file: str) -> Optional[Dict[str, Any]]:
        details: Optional[Dict[str, Any]] = None
        try:
            # TODO: need to be careful here with data file removal in case
            #       the file in question is still being actively validated?
            details = self.data_files.pop(data_file)
        except KeyError:
            logger.warning(
                "File '"+data_file+"' was  not found in " +
                "KGE File Set version '"+self.kg_version+"'"
            )
        return details

    def load_data_files(self, file_object_keys: List[str]):
        # TODO: is there any other information here to be captured or inferred,
        #       e.g. file compression (from file extension), file type, size, etc.
        for object_key in file_object_keys:
            part = object_key.split('/')
            file_name = part[-1]
            self.data_files[object_key] = {
                "file_name": file_name,
                "object_key": object_key
            }

    ############################################################################
    # KGX Validation Framework #################################################
    ############################################################################
    # TODO: Review this design - may not be optimal in that the KGX Transformer
    #       (and likely, KGX Validation) seems to handle multiple input files,
    #       (in the Transformer) thus collecting those input files first then
    #       sending them together for KGX validation, may make more sense here?
    async def validate(self, name):

        while True:

            # Process one file at a time?
            kge_file_spec = await self.validation_queue.get()

            file_type = kge_file_spec['file_type']
            object_key = kge_file_spec['object_key']
            s3_file_url = kge_file_spec['s3_file_url']
            input_format = kge_file_spec['input_format']
            input_compression = kge_file_spec['input_compression']

            print(
                f"{name} working on file '{object_key}' of " +
                f"type '{file_type}', input format '{input_format}' " +
                f"and with compression '{input_compression}', ",
                file=stderr
            )

            errors: List = list()

            if file_type == KgeFileType.KGX_DATA_FILE:

                # Run validation of KGX knowledge graph data files here
                # errors: List[str] = \
                #     await self.validator.validate_data_file(
                #         file_path=s3_file_url,
                #         input_format=input_format,
                #         input_compression=input_compression
                #     )

                if not errors:
                    self.data_files[object_key]["kgx_compliant"] = True
                else:
                    self.data_files[object_key]["errors"] = errors

            elif file_type == KgeFileType.KGE_ARCHIVE:
                # TODO: not sure how we should properly validate a KGX Data archive?
                self.data_files[object_key]["errors"] = ['KGE Archive validation is not yet implemented?']

            else:
                print(f'{name} WARNING: Unknown KgeFileType{file_type} ... ignoring', file=stderr)

            compliance: str = ' not ' if errors else ' '

            print(
                f"{name} has finished processing file {object_key} ... is" +
                compliance + "KGX compliant", file=stderr
            )

            self.validation_queue.task_done()

    ############################################################################
    # KGE Publication to the Archive ###########################################
    ############################################################################
    def publish(self) -> bool:
        """
        Publish file set in the Archive.

        :return: True if successful; False otherwise
        """
        self.status = KgeFileSetStatusCode.PROCESSING

        if not self.post_process_file_set():
            self.status = KgeFileSetStatusCode.ERROR
            msg = "post_process_file_set(): failed for" + \
                  "' for KGE File Set version '" + self.kg_version + \
                  "' of knowledge graph '" + self.kg_id + "'"
            logger.warning(msg)
            self.errors.append(msg)
            return False

        # Publish a 'file_set.yaml' metadata file to the
        # versioned archive subdirectory containing the KGE File Set
        file_set_metadata_file = self.generate_file_set_metadata_file()
        file_set_metadata_object_key = add_to_s3_archive(
            kg_id=self.kg_id,
            kg_version=self.kg_version,
            text=file_set_metadata_file,
            file_name=FILE_SET_METADATA_FILE
        )

        if file_set_metadata_object_key:
            return True
        else:
            self.status = KgeFileSetStatusCode.ERROR
            msg = "publish_file_set(): metadata '" + FILE_SET_METADATA_FILE + \
                  "' file for KGE File Set version '" + self.kg_version + \
                  "' of knowledge graph '" + self.kg_id + \
                  "' not successfully posted to the Archive?"
            logger.warning(msg)
            self.errors.append(msg)
            return False

    # TODO: need here to fully implement required post-processing of
    #       the completed file set (after files are uploaded by the client)
    def post_process_file_set(self) -> bool:
        """
        Stub file for KGE File Set upload post-processing code.
        """
        return True

    # async def publish_file_set(self, kg_id: str, kg_version: str):
    #
    #     logger.debug(
    #         "Calling Registry.publish_file_set(" +
    #         "kg_version: '"+kg_version+"' of graph kg_id: '"+kg_id+"')"
    #     )
    #
    #     errors: List[str] = list()
    #
    #     if kg_id in self._kge_knowledge_graph_catalog:
    #
    #         knowledge_graph = self._kge_knowledge_graph_catalog[kg_id]
    #
    #         file_set = knowledge_graph.get_file_set(kg_version)
    #
    #         if file_set:
    #             errors = await file_set.publish_file_set()
    #         else:
    #             logger.warning(
    #                 "publish_file_set(): KGE File Set version '" + str(kg_version) +
    #                 "' of knowledge graph '" + kg_id + "' is unrecognized?"
    #             )
    #
    #         if not errors:
    #             # After KGX validation and related post-processing is successfully validated,
    #             # also publish provider metadata externally, to the Translator SmartAPI Registry
    #             translator_registry_entry = knowledge_graph.generate_translator_registry_entry()
    #
    #             successful = add_to_github(kg_id, translator_registry_entry)
    #             if not successful:
    #                 logger.warning("publish_file_set(): Translator Registry entry not posted. " +
    #                                "Is a valid 'github token' properly configured in site config.yaml?")
    #         else:
    #             logger.debug("publish_file_set(): KGX validation errors encountered:\n" + str(errors))
    #
    #     else:
    #         logger.error("publish_file_set(): Unknown file set '" + kg_id + "' ... ignoring publication request")
    #         errors.append("publish_file_set(): Unknown file set '" + kg_id + "' ... ignoring publication request")
    #
    #     return errors

    #
    # Delegating this error checking function to another part of the application.
    #
    # Next, ensure that the set of files for the current version are KGX validated.
    # The content metadata file was checked separately when it was uploaded...
    # (sanity check: self.content_metadata may not be initialized if no metadata file was uploaded?)
    # if self.content_metadata and "errors" in self.content_metadata:
    #     errors.extend(self.content_metadata["errors"])

    # .. from the KGX graph (nodes and edges) data files, asynchronously checked here.
    # errors.extend(await self.confirm_kgx_data_file_set_validation())
    #
    # logger.debug("KGX format validation() completed for KGE File Set version '" + self.kg_version +
    #              "' of KGE Knowledge Graph '" + self.kg_id + "'")
    #
    # return errors

    async def confirm_kgx_data_file_set_validation(self):

        # Blocking call to KGX validator worker Queue processing
        await self.validation_queue.join()
        await self.release_workers()

        # check if any errors were returned by KGX Validation
        errors: List = []
        for data_file in self.data_files.values():
            if not data_file["kgx_compliant"]:
                errors.append(data_file["errors"])

        return errors

    async def release_workers(self):
        try:
            # Cancel the KGX validation worker tasks.
            for task in self.tasks:
                task.cancel()
            # Wait until all worker tasks are cancelled.
            await asyncio.gather(*self.tasks, return_exceptions=True)
        except Exception as exc:
            self.status = KgeFileSetStatusCode.ERROR
            msg = "KgeaFileSet() KGX worker task exception: " + str(exc)
            logger.error(msg)
            self.errors.append(msg)

    def generate_file_set_metadata_file(self) -> str:
        self.size = 'unknown'
        self.revisions = 'Creation'
        return _populate_template(
            filename=FILE_SET_METADATA_TEMPLATE_FILE_PATH,
            kg_id=self.kg_id,
            kg_version=self.kg_version,
            submitter=self.submitter,
            submitter_email=self.submitter_email,
            size=self.size,
            revisions=self.revisions
        )

    def get_status(self) -> Optional[KgeFileSetStatus]:
        # # TODO: need to retrieve metadata by kg_version
        # file_set_location, assigned_version = with_version(func=get_object_location, version=kg_version)(kg_id)
        #
        # # Listings Approach
        # # - Introspect on Bucket
        # # - Create URL per Item Listing
        # # - Send Back URL with Dictionary
        # # OK in case with multiple files (alternative would be, archives?). A bit redundant with just one file.
        # # TODO: convert into redirect approach with cross-origin scripting?
        # kg_files = kg_files_in_location(
        #     bucket_name=_KGEA_APP_CONFIG['bucket'],
        #     object_location=file_set_location
        # )
        # pattern = Template('($FILES_LOCATION[0-9]+\/)').substitute(FILES_LOCATION=file_set_location)
        # kg_listing = [content_location for content_location in kg_files if re.match(pattern, content_location)]
        # kg_urls = dict(
        #     map(lambda kg_file: [Path(kg_file).stem, create_presigned_url(_KGEA_APP_CONFIG['bucket'], kg_file)],
        #         kg_listing))
        # # logger.debug('access urls %s, KGs: %s', kg_urls, kg_listing)
        
        file_set_status = KgeFileSetStatus(self.kg_id, self.kg_version, self.status)
        file_set: List[KgeFile] = list()
        # TODO: populate the file_set information here
        file_set_status.files = file_set

        return file_set_status


class KgeKnowledgeGraph:
    """
    Class wrapping information about a KGE Archive managed Knowledge Graph assembled
    in AWS S3 then published in the Translator SmartAPI Registry for 3rd party client access.
    A knowledge graph has some characteristic source, scope and Translator team owner, and
    contains one or more versioned KgeFileSets.
    """
    
    _expected_provider_metadata = [
        "file_set_location",
        "kg_name",
        "kg_description",

        # "kg_version",  # don't store versions here anymore (rather, in the KGEFileSet)

        "kg_size",
        "translator_component",
        "translator_team",

        # 'submitter'  and 'submitter_email' here refers to the individual
        # who originally registers the KGE Knowledge Graph and associated metadata
        "submitter",
        "submitter_email",

        "license_name",
        "license_url",
        "terms_of_service"
    ]
    
    def __init__(self, **kwargs):
        """
        KgeKnowledgeGraph constructor.
        """
        #     Dict[
        #         str,  # kg_id level properties: 'metadata' and 'versions'
        #         Union[
        #             KgeKnowledgeGraph,  # global 'metadata'  including KG name, owners, licensing, etc.
        #             Dict[  # global 'versions'
        #                 str,       # kg_version's are the keys
        #                 List[str]  # List of S3 object_name paths for files associated with a given version
        #             ]
        #         ]
        #     ]
        # ]
        self.kg_id = kwargs.pop("kg_id", None)
        if not self.kg_id:
            raise RuntimeError("KgeKnowledgeGraph() needs a non-null 'kg_id'!")

        # if provided, the kg_version is simply designates
        # the 'latest' file set of the given Knowledge Graph
        kg_version = kwargs.pop("kg_version", None)
        if kg_version:
            file_set_location = kwargs.pop("file_set_location", None)
            if not file_set_location:
                raise RuntimeError("KgeKnowledgeGraph() explicit 'kg_version' needs a 'file_set_location'?!")

        # load other parameters other than kg_id  and version-specific metadata
        self.parameter: Dict = dict()
        for key, value in kwargs.items():
            if key not in self._expected_provider_metadata:
                logger.warning("Unexpected KgeKnowledgeGraph parameter '"+str(key)+"'... ignored!")
                continue
            self.parameter[key] = value

        # File Set Versions
        self._file_set_versions: Dict[str, KgeFileSet] = dict()

        #
        # Knowledge Graph registration no longer
        # automatically adds a new KGE File Set version
        #
        # Register an explicitly specified submitter-specified KGE File Set version
        # Sanity check: we should probably not overwrite a KgeFileSet version if it already exists?
        # if kg_version and kg_version not in self._file_set_versions:
        #     self._file_set_versions[kg_version] = KgeFileSet(
        #         kg_id=self.kg_id,
        #         kg_version=kg_version,
        #         submitter=kwargs['submitter'],
        #         submitter_email=kwargs['submitter_email']
        #     )
        
        self._provider_metadata_object_key: Optional[str] = None

    def set_provider_metadata_object_key(self, object_key: str):
        self._provider_metadata_object_key = object_key

    def get_provider_metadata_object_key(self):
        return self._provider_metadata_object_key

    def publish_provider_metadata(self):
        logger.debug("Publishing knowledge graph '" + self.kg_id + "' to the Archive")
        provider_metadata_file = self.generate_provider_metadata_file()
        # no kg_version given since the provider metadata is global to Knowledge Graph
        object_key = add_to_s3_archive(
            kg_id=self.kg_id,
            text=provider_metadata_file,
            file_name=PROVIDER_METADATA_FILE
        )
        if not object_key:
            self.set_provider_metadata_object_key(object_key)
        else:
            logger.warning(
                "publish_file_set(): " + PROVIDER_METADATA_FILE +
                " for Knowledge Graph '" + self.kg_id +
                "' not successfully added to KGE Archive storage?"
            )

    def get_name(self) -> str:
        return self.parameter.setdefault("kg_name", self.kg_id)

    def get_file_set(self, kg_version: str) -> Optional[KgeFileSet]:
        """
        :return: KgeFileSet entry tracking for data files in the KGE File Set
        """
        if kg_version not in self._file_set_versions:
            logger.warning("KgeKnowledgeGraph.get_file_set(): KGE File Set version '"
                           + kg_version + "' unknown for Knowledge Graph '" + self.kg_id + "'?")
            return None
        
        return self._file_set_versions[kg_version]

    # KGE File Set Translator SmartAPI parameters (March 2021 release):
    # - kg_id: KGE Archive generated identifier assigned to a given knowledge graph submission (and used as S3 folder)
    # - translator_component - Translator component associated with the knowledge graph (e.g. KP, ARA or SRI)
    # - translator_team - specific Translator team (affiliation) contributing the file set, e.g. Clinical Data Provider
    # - submitter - name of submitter of the KGE file set
    # - submitter_email - contact email of the submitter
    # - kg_name: human readable name of the knowledge graph
    # - kg_description: detailed description of knowledge graph (may be multi-lined with '\n')
    # - license_name - Open Source license name, e.g. MIT, Apache 2.0, etc.
    # - license_url - web site link to project license
    # - terms_of_service - specifically relating to the project, beyond the licensing
    def generate_provider_metadata_file(self) -> str:
        return _populate_template(
            filename=PROVIDER_METADATA_TEMPLATE_FILE_PATH,
            kg_id=self.kg_id, **self.parameter
        )

    def generate_translator_registry_entry(self) -> str:
        return _populate_template(
            filename=TRANSLATOR_SMARTAPI_TEMPLATE_FILE_PATH,
            kg_id=self.kg_id, **self.parameter
        )

    def get_version_names(self) -> List[str]:
        return list(self._file_set_versions.keys())

    def load_file_set_versions(
            self,
            versions: Dict[
                str,  # kg_version's of versioned KGE File Sets for a kg
                Dict[
                    str,  # tags 'metadata' and 'file_object_keys'
                    Union[
                        str,  # 'metadata' field value: 'file set' specific text file blob from S3
                        List[str]  # list of 'file_object_keys' in a given KGE File Set
                    ]
                ]
            ]
    ):
        for kg_version, entry in versions.items():
            file_set: KgeFileSet
            if 'metadata' in entry:
                file_set = self.load_file_set_metadata(entry['metadata'])
            else:
                file_set = KgeFileSet(
                                self.kg_id,
                                kg_version=kg_version,
                                submitter=self.parameter.setdefault('submitter', ''),
                                submitter_email=self.parameter.setdefault('submitter_email', ''),
                                validate=False
                            )
            file_set.load_data_files(entry['file_object_keys'])

    def add_file_set(self, kg_version: str, file_set: KgeFileSet):
        """
        
        :param kg_version:
        :param file_set:
        :return:
        """
        self._file_set_versions[kg_version] = file_set
    
    def load_file_set_metadata(self, metadata_text: str) -> KgeFileSet:
        """
        
        :param metadata_text:
        :return:
        """

        # Assumed to be a YAML string to be parsed into a Python dictionary
        mf = io.StringIO(metadata_text)
        md_raw = yaml.load(mf, Loader=Loader)
        md = dict(md_raw)

        # id: "disney_small_world_graph" ## == kg_id
        if self.kg_id != md.setdefault('id', ''):
            raise RuntimeError(
                "load_archive_entry(): archive folder kg_id '" + self.kg_id +
                " != id in " + FILE_SET_METADATA_FILE + "?"
            )

        # version: "1964-04-22"
        kg_version = md.setdefault('version', 'latest')

        # revisions: >-
        #   ${revisions}
        revisions = md.setdefault('revisions', '')

        # submitter:
        #   name: "${submitter}"
        submitter = md.setdefault('submitter', '')

        #   email: "${submitter_email}"
        submitter_email = md.setdefault('submitter_email', '')

        # size: "10000" # megabytes
        size = md.setdefault('size', '')
        # TODO: should the file set size value be validated here?

        # Probably don't need this field value
        # access: "https://kge.starinformatics.ca/disney_small_world_graph/1964-04-22"
        # access = md.setdefault('access', '')

        # Capture the file set metadata...
        file_set = KgeFileSet(
            self.kg_id,
            kg_version=kg_version,
            submitter=submitter,
            submitter_email=submitter_email,
            size=size,
            revisions=revisions,
            validate=False
        )

        # ...add it to the knowledge graph...
        self.add_file_set(kg_version, file_set)

        # then return it for further processing
        return file_set


class KgeArchiveCatalog:
    """
    Knowledge Graph Exchange (KGE) Temporary Registry for
    tracking compilation and validation of complete KGE File Sets
    """
    _the_catalog = None
    
    def __init__(self):
        # Catalog keys are kg_id's, entries are a Python dictionary of kg_id metadata including
        # name, KGE File Set metadata and a list of versions with associated file sets
        self._kge_knowledge_graph_catalog: Dict[str, KgeKnowledgeGraph] = dict()

        # Initialize catalog with the metadata of all the existing KGE Archive (AWS S3 stored) KGE File Sets
        # archive_contents keys are the kg_id's, entries are the rest of the KGE File Set metadata
        archive_contents: Dict = get_archive_contents(bucket_name=_KGEA_APP_CONFIG['bucket'])
        for kg_id, entry in archive_contents.items():
            self.load_archive_entry(kg_id=kg_id, entry=entry)

    @classmethod
    def initialize(cls):
        if not cls._the_catalog:
            KgeArchiveCatalog._the_catalog = KgeArchiveCatalog()

    @classmethod
    def catalog(cls):
        """
        :return: singleton of KgeArchiveCatalog
        """
        if not cls._the_catalog:
            raise RuntimeError("KGE Archive Catalog is uninitialized?")

        return KgeArchiveCatalog._the_catalog

    def load_archive_entry(
            self,
            kg_id: str,
            entry: Dict[
                str,  # tags 'metadata' and 'versions'
                Union[
                    str,  # 'metadata' field value: kg specific 'provider' text file blob from S3
                    Dict[  # 'versions' field value
                        str,  # kg_version's of versioned KGE File Sets for a kg
                        Dict[
                            str,  # tags 'metadata' and 'files'
                            Union[
                                str,  # 'metadata' field value: 'file set' specific text file blob from S3
                                List[str]  # list of data files in a given KGE File Set
                            ]
                        ]
                    ]
                ]
            ]
    ):
        """
         Parse an KGE Archive entry for metadata
         to load into a KgeFileSet
         for indexing in the KgeArchiveCatalog
        """
        if 'metadata' in entry:
            self.load_provider_metadata(kg_id=kg_id, metadata_text=entry['metadata'])
        else:
            # provider.yaml metadata was not loaded, then, ignore this entry and return...
            logger.warning(
                "load_archive_entry(): no 'metadata' loaded from archive... ignoring knowledge graph '"+kg_id+"'?"
            )
            return

        if 'versions' in entry:
            knowledge_graph: KgeKnowledgeGraph = self.get_knowledge_graph(kg_id)
            knowledge_graph.load_file_set_versions(versions=entry['versions'])

    def load_provider_metadata(self, kg_id, metadata_text: str):
        # Assumed to be a YAML string to be parsed into a Python dictionary
        mf = io.StringIO(metadata_text)
        md_raw = yaml.load(mf, Loader=Loader)
        md = dict(md_raw)

        # id: "disney_small_world_graph" ## == kg_id
        if kg_id != md.setdefault('id', ''):
            raise RuntimeError(
                "load_archive_entry(): archive folder kg_id '" + kg_id +
                " != id in "+PROVIDER_METADATA_FILE+"?"
            )

        # name:  "Disneyland Small World Graph"
        kg_name = md.setdefault('name', 'Unknown')

        # description: >-
        #   Voyage along the Seven Seaways canal and behold a cast of
        #     almost 300 Audio-Animatronics dolls representing children
        #     from every corner of the globe as they sing the classic
        #     anthem to world peace—in their native languages.
        kg_description = md.setdefault('description', '')

        # size: "KGE archive file size TBA"
        kg_size = md.setdefault('size', 'unknown')

        # translator:
        #   component: "KP"
        #   team:
        #   - "Disney Knowledge Provider"
        if 'translator' in md:
            tmd = md['translator']
            translator_component = tmd.setdefault('component', 'unknown')
            translator_team = tmd.setdefault('team', 'unknown')
        else:
            translator_component = translator_team = 'unknown'

        # submitter:
        #   name: "Mickey Mouse"
        #   email: "mickey.mouse@disneyland.disney.go.com"
        if 'submitter' in md:
            smd = md['submitter']
            submitter = smd.setdefault('name', 'unknown')
            submitter_email = smd.setdefault('email', 'unknown')
        else:
            submitter = submitter_email = 'unknown'

        # license:
        #   name: "Artistic 2.0"
        #   url:  "https://opensource.org/licenses/Artistic-2.0"
        if 'license' in md:
            lmd = md['license']
            license_name = lmd.setdefault('name', 'unknown')
            license_url = lmd.setdefault('url', 'unknown')
        else:
            license_name = license_url = 'unknown'

        # termsOfService: "https://disneyland.disney.go.com/en-ca/terms-conditions/"
        terms_of_service = md.setdefault('termsOfService', 'unknown')

        self.add_knowledge_graph(
            kg_id=kg_id,
            kg_name=kg_name,
            kg_description=kg_description,
            kg_size=kg_size,
            translator_component=translator_component,
            translator_team=translator_team,
            submitter=submitter,
            submitter_email=submitter_email,
            license_name=license_name,
            license_url=license_url,
            terms_of_service=terms_of_service
        )

    @staticmethod
    def normalize_name(kg_name: str) -> str:
        # TODO: need to review graph name normalization and indexing
        #       against various internal graph use cases, e.g. lookup
        #       and need to be robust to user typos (e.g. extra blank spaces?
        #       invalid characters?). Maybe convert to regex cleanup?
        kg_id = kg_name.lower()          # all lower case
        kg_id = kg_id.replace(' ', '_')  # spaces with underscores
        return kg_id
    
    # TODO: what is the required idempotency of this KG addition
    #       relative to submitters (can submitters change?)
    def add_knowledge_graph(self, **kwargs) -> KgeKnowledgeGraph:
        """
         As needed, registers a new catalog record for a knowledge graph 'kg_id'
         with a given 'name' for a given 'submitter'.

        :param kwargs: dictionary of metadata describing a KGE File Set entry
        :return: KgeKnowledgeGraph instance of the knowledge graph (existing or added)
        """
        kg_id = kwargs['kg_id']
        if kg_id not in self._kge_knowledge_graph_catalog:
            self._kge_knowledge_graph_catalog[kg_id] = KgeKnowledgeGraph(**kwargs)
        return self._kge_knowledge_graph_catalog[kg_id]
    
    def get_knowledge_graph(self, kg_id: str) -> Union[KgeKnowledgeGraph, None]:
        """
         Get the knowledge graph provider metadata associated with
         a given knowledge graph file set identifier.

        :param kg_id: input knowledge graph file set identifier
        :return: KgeaFileSet; None, if unknown
        """
        if kg_id in self._kge_knowledge_graph_catalog:
            return self._kge_knowledge_graph_catalog[kg_id]
        else:
            return None

    def add_to_kge_file_set(
            self,
            kg_id: str,
            kg_version: str,
            file_type: KgeFileType,
            file_name: str,
            object_key: str,
            s3_file_url: str
    ):
        """
        This method adds the given input file to a local catalog of recently
        updated files, within which files formats are asynchronously validated
        to KGX compliance, and the entire file set assessed for completeness.
        An exception is raise if there is an error.
    
        :param kg_id: identifier of the KGE Archive managed Knowledge Graph of interest
        :param kg_version: version of interest of the KGE File Set associated with the Knowledge Graph
        :param file_type: KgeFileType of the file being added
        :param file_name: name of the file
        :param object_key: AWS S3 object key of the file
        :param s3_file_url: currently active pre-signed url to access the file
        :return: None
        """
        knowledge_graph = self.get_knowledge_graph(kg_id)

        if not knowledge_graph:
            raise RuntimeError("KGE File Set '" + kg_id + "' is unknown?")
        else:
            # Found a matching KGE Knowledge Graph?
            file_set = knowledge_graph.get_file_set(kg_version=kg_version)

            # Add the current (meta-)data file to the KGE File Set
            # associated with this kg_version of the graph.
            if file_type in [KgeFileType.KGX_DATA_FILE, KgeFileType.KGE_ARCHIVE]:
                file_set.add_data_file(
                    file_name=file_name,
                    file_type=file_type,
                    object_key=object_key,
                    s3_file_url=s3_file_url
                )
            
            elif file_type == KgeFileType.KGX_CONTENT_METADATA_FILE:
                file_set.set_content_metadata_file(
                    file_name=file_name,
                    object_key=object_key,
                    s3_file_url=s3_file_url
                )
            else:
                raise RuntimeError("Unknown KGE File Set type?")

    def get_kg_entries(self) -> Dict[str,  Dict[str, Union[str, List[str]]]]:

        # TODO: see KgeFileSetEntry schema in the kgea_archive.yaml
        if not OVERRIDE and DEV_MODE:
            # mock catalog
            catalog = {
                "translator_reference_graph": {
                    "name": "Translator Reference Graph",
                    "versions": ["1.0", "2.0", "2.1"]
                },
                "semantic_medline_database": {
                    "name": "Semantic Medline Database",
                    "versions": ["4.2", "4.3"]
                }
            }
        else:
            # The real content of the catalog
            catalog: Dict[str,  Dict[str, Union[str, List[str]]]] = dict()
            for kg_id, knowledge_graph in self._kge_knowledge_graph_catalog.items():
                catalog[kg_id] = dict()
                catalog[kg_id]['name'] = knowledge_graph.get_name()
                catalog[kg_id]['versions'] = knowledge_graph.get_version_names()

        return catalog

    def register_kge_file_set(
            self,
            kg_id: str,
            kg_version: str,
            submitter: str,
            submitter_email: str
    ):
        pass


# TODO
@prepare_test
def test_check_kgx_compliance():
    return True


# TODO
@prepare_test
def test_get_catalog_entries():
    print("\ntest_get_catalog_entries() test output:\n", file=stderr)
    catalog = KgeArchiveCatalog.catalog().get_kg_entries()
    print(dumps(catalog, indent=4, sort_keys=True), file=stderr)
    return True


_TEST_TSE_PARAMETERS = dict(
    kg_id="disney_small_world_graph",
    kg_name="Disneyland Small World Graph",
    kg_description="""Voyage along the Seven Seaways canal and behold a cast of
    almost 300 Audio-Animatronics dolls representing children
    from every corner of the globe as they sing the classic
    anthem to world peace—in their native languages.""",
    kg_version="1964-04-22",
    translator_component="KP",
    translator_team="Disney Knowledge Provider",
    submitter="Mickey Mouse",
    submitter_email="mickey.mouse@disneyland.disney.go.com",
    license_name="Artistic 2.0",
    license_url="https://opensource.org/licenses/Artistic-2.0",
    terms_of_service="https://disneyland.disney.go.com/en-ca/terms-conditions/"
)
_TEST_TPMF = 'empty'
_TEST_TRE = 'empty'


@prepare_test
def test_create_provider_metadata_file():
    global _TEST_TPMF
    print("\ntest_create_provider_metadata_entry() test output:\n", file=stderr)
    _TEST_TPMF = _populate_template(
        filename=PROVIDER_METADATA_TEMPLATE_FILE_PATH,
        **_TEST_TSE_PARAMETERS
    )
    print(str(_TEST_TPMF), file=stderr)
    return True


@prepare_test
def test_create_translator_registry_entry():
    global _TEST_TRE
    print("\ntest_create_translator_registry_entry() test output:\n", file=stderr)
    _TEST_TRE = _populate_template(
        filename=TRANSLATOR_SMARTAPI_TEMPLATE_FILE_PATH,
        **_TEST_TSE_PARAMETERS
    )
    print(str(_TEST_TRE), file=stderr)
    return True


def add_to_s3_archive(
        kg_id: str,
        text: str,
        file_name: str,
        kg_version: str = ''
) -> str:
    """
    Add a file of specified text content and name,
     to a KGE Archive (possibly versioned) S3 folder.
    :param kg_id: knowledge graph
    :param text: string blob contents of the file.
    :param file_name: of the file.
    :param kg_version: version (optional)
    :return: str object key of the uploaded file
    """
    if kg_version:
        file_set_location, _ = with_version(func=get_object_location, version=kg_version)(kg_id)
    else:
        file_set_location = get_object_location(kg_id)

    uploaded_file_object_key: str = ''
    if text:
        data_bytes = text.encode('utf-8')
        uploaded_file_object_key = upload_file(
            data_file=BytesIO(data_bytes),
            file_name=file_name,
            bucket=_KGEA_APP_CONFIG['bucket'],
            object_location=file_set_location
        )
    else:
        logger.warning("add_to_s3_archive(): Empty text string argument? Can't archive a vacuum!")

    # could be an empty object key
    return uploaded_file_object_key


def get_github_token() -> Optional[str]:
    _github: Optional[Dict] = _KGEA_APP_CONFIG.setdefault('github', None)
    token: Optional[str] = None
    if _github:
        token = _github.setdefault('token', None)
    return token


def add_to_github(
        kg_id: str,
        text: str,
        repo_path: str = TRANSLATOR_SMARTAPI_REPO,
        target_directory: str = KGE_SMARTAPI_DIRECTORY
) -> bool:
    
    status: bool = False
    
    gh_token = get_github_token()
    
    logger.debug("Calling Registry.add_to_github(gh_token: '"+str(gh_token)+"')")
    
    if gh_token and text:
        
        logger.debug(
            "\n\t### api_specification = '''\n" + text[:60] + "...\n'''\n" +
            "\t### repo_path = '" + str(repo_path) + "'\n" +
            "\t### target_directory = '" + str(target_directory) + "'"
        )
    
        if text and repo_path and target_directory:
            
            entry_path = target_directory+"/"+kg_id + ".yaml"
            
            logger.debug("\t### gh_url = '" + str(entry_path) + "'")
            
            g = Github(gh_token)

            # TODO: should I be explicit somewhere here
            #       about the repo branch being used? How?
            repo = g.get_repo(repo_path)

            try:
                content_file = repo.get_contents(entry_path)
            except UnknownObjectException:
                content_file = None
            
            if not content_file:
                repo.create_file(
                    entry_path,
                    "Creating new KGE entry  '" + kg_id + "' in " + repo_path,
                    text,  # API YAML specification as a string
                )
            else:
                repo.update_file(
                    entry_path,
                    "Updating KGE entry  '" + kg_id + "' in " + repo_path,
                    text,  # API YAML specification as a string
                    content_file.sha
                )
            
            status = True

    return status


_TEST_SMARTAPI_REPO = "NCATSTranslator/Knowledge_Graph_Exchange_Registry"
_TEST_KGE_SMARTAPI_TARGET_DIRECTORY = "kgea/server/tests/output"


@prepare_test
def test_add_to_archive() -> bool:
    outcome: str = add_to_s3_archive(
        "kge_test_provider_metadata_file",
        _TEST_TPMF
    )

    return not outcome == ''


@prepare_test
def test_add_to_github():
    outcome: bool = add_to_github(
        "kge_test_translator_registry_entry",
        _TEST_TRE,
        repo_path=_TEST_SMARTAPI_REPO,
        target_directory=_TEST_KGE_SMARTAPI_TARGET_DIRECTORY
    )

    return outcome


# TODO: make sure that you clean up all (external) test artifacts here
def clean_tests(
        kg_id="kge_test_entry",
        repo_path=_TEST_SMARTAPI_REPO,
        target_directory=_TEST_KGE_SMARTAPI_TARGET_DIRECTORY
):
    """
    This method cleans up a 'test' target Github repository.
    
    This method should be run by setting the 'CLEAN_TESTS' environment flag,
    after running the module with the 'RUN_TESTS' environment flag set.
    
    :param kg_id:
    :param repo_path:
    :param target_directory:
    :return:
    """
    
    gh_token = get_github_token()
    
    print(
        "Calling Registry.clean_tests()",
        file=stderr
    )
    
    if gh_token and repo_path and target_directory:
            
        entry_path = target_directory + "/" + kg_id + ".yaml"
        
        g = Github(gh_token)
        repo = g.get_repo(repo_path)
    
        contents = repo.get_contents(entry_path)
        repo.delete_file(contents.path, "Remove test entry = '" + entry_path + "'", contents.sha)


"""
Unit Tests
* Run each test function as an assertion if we are debugging the project
"""
if __name__ == '__main__':
    
    # Set the RUN_TESTS environment variable to a non-blank value
    # whenever you wish to run the unit tests in this module...
    # Set the CLEAN_TESTS environment variable to a non-blank value
    # to clean up test outputs from RUN_TESTS runs.
    
    if RUN_TESTS:
        
        print("KGEA Registry modules functions and tests")
        
        # The generate_translator_registry_entry() and add_to_github() methods both work as coded as of 29 March 2021,
        # thus we comment out this test to avoid repeated commits to the KGE repo. The 'clean_tests()' below
        # is thus not currently needed either, since it simply removes the github artifacts from add_to_github().
        # This code can be uncommented if these features need to be tested again in the future
        assert (test_create_provider_metadata_file())
        assert (test_add_to_archive())
        assert (test_create_translator_registry_entry())
        # assert (test_add_to_github())

        assert (test_get_catalog_entries())
        
        print("all KGE Archive Catalog tests passed")
        
    # if CLEAN_TESTS:
    #     clean_tests()
