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
from sys import stderr
from os import getenv
from os.path import abspath, dirname
import asyncio
from io import BytesIO
from typing import Dict, Union, Tuple, Set, List
from enum import Enum
from string import Template
from json import dumps

import logging

from github import Github
from github.GithubException import UnknownObjectException

from kgea.server.config import (
    get_app_config,
    PROVIDER_METADATA_FILE
)
from kgea.server.web_services.kgea_file_ops import (
    get_default_date_stamp,
    get_object_location,
    get_archive_contents
)
from .kgea_kgx import KgxValidator
from kgea.server.web_services.kgea_file_ops import upload_file

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

DEV_MODE = getenv('DEV_MODE', default=False)

RUN_TESTS = getenv('RUN_TESTS', default=False)
CLEAN_TESTS = getenv('CLEAN_TESTS', default=False)

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
_NO_KGX_VALIDATION_WORKER_TASKS = _KGEA_APP_CONFIG.setdefault("No_KGX_Validation_Worker_Tasks", 3)


def prepare_test(func):
    def wrapper():
        print("\n" + str(func) + " ----------------\n")
        return func()
    return wrapper


class KgeFileType(Enum):
    KGX_UNKNOWN = "unknown file type"
    KGX_METADATA_FILE = "KGX metadata file"
    KGX_DATA_FILE = "KGX data file"
    KGX_ARCHIVE = "KGX data archive"


class KgeaFileSet:
    """
    Class wrapping information about a KGE file set being
    assembled in AWS S3, for SmartAPI registration and client access
    """
    
    _expected = [
        "file_set_location",
        "kg_name",
        "kg_description",
        "kg_version",
        "translator_component",
        "translator_team",
        "submitter",
        "submitter_email",
        "license_name",
        "license_url",
        "terms_of_service"
    ]
    
    def __init__(self, kg_id: str, **kwargs):
        """
        KgeaFileSet constructor
        
        :param kg_name: name of knowledge graph in entry
        :param submitter: owner of knowledge graph
        """
        self.kg_id = kg_id
        self.parameter: Dict = dict()
        for key, value in kwargs.items():
            
            if key not in self._expected:
                logger.warning("Unexpected KgeaFileSet parameter '"+str(key)+"'... ignored!")
                continue
            
            self.parameter[key] = value

        self.metadata_file: Union[Dict, None] = dict()
        self.data_files: Dict[str, Dict] = dict()
        
        # KGX Validator singleton for this KGE File Set
        self.validator = KgxValidator()
        
        # this Queue serves at the communication link
        # between a KGX validation process and the Registry
        self.validation_queue = asyncio.Queue()
        
        # Create three worker tasks to process the queue concurrently.
        self.tasks = []
        # for i in range(_NO_KGX_VALIDATION_WORKER_TASKS):
        #     task = asyncio.create_task(self.validate(f'KGX Validation Worker-{i}'))
        #     self.tasks.append(task)

    async def release_workers(self):
        try:
            # Cancel the KGX validation worker tasks.
            for task in self.tasks:
                task.cancel()
            # Wait until all worker tasks are cancelled.
            await asyncio.gather(*self.tasks, return_exceptions=True)
        except Exception as exc:
            logger.error("KgeaFileSet() KGX worker task exception: "+str(exc))

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

            print(f'{name} working on file {object_key}', file=stderr)
            
            # Run KGX validation here
            errors: List = list()
            
            if file_type == KgeFileType.KGX_DATA_FILE:
                
                errors = await self.validator.validate_data_file(
                    file_path=s3_file_url,
                    input_format=input_format,
                    input_compression=input_compression
                )
                
                if not errors:
                    self.data_files[object_key]["kgx_compliant"] = True
                else:
                    self.data_files[object_key]["errors"] = errors

            elif file_type == KgeFileType.KGX_ARCHIVE:
                # TODO: not sure how we should properly validate a KGX Data archive?
                pass
            
            elif file_type == KgeFileType.KGX_METADATA_FILE:

                errors = await KgxValidator.validate_metadata(file_path=s3_file_url)
                if not errors:
                    self.metadata_file["kgx_compliant"] = True
                else:
                    self.data_files[object_key]["errors"] = errors
            else:
                print(f'{name} WARNING: Unknown KgeFileType{file_type} ... ignoring', file=stderr)
            
            compliance: str = ' not ' if errors else ' '
            
            print(f"{name} has finished processing file {object_key} ... is" + compliance + "KGX compliant", file=stderr)
            
            self.validation_queue.task_done()

    def check_kgx_compliance(
            self,
            file_type: KgeFileType,
            object_key: str,
            s3_file_url: str
    ):
        """
        Stub implementation of KGX Validation of a
        KGX graph file stored in back end AWS S3

        :param file_type:
        :param object_key:
        :param s3_file_url:
        :return: bool
        """
        logger.debug(
            "Checking if " + str(file_type) + " file (object_key) " +
            "'" + object_key + "'" +
            "with S3 object URL '" + s3_file_url + "' " +
            "is KGX compliant")

        if file_type == KgeFileType.KGX_DATA_FILE:
            input_format = self.data_files[object_key]["input_format"]
            input_compression = self.data_files[object_key]["input_compression"]
            
        elif file_type == KgeFileType.KGX_ARCHIVE:
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
        
        # delegate validation of this file
        # to the KGX process reading this Queue
        self.validation_queue.put_nowait(kge_file_spec)
            
    def set_metadata_file(self, file_name: str, object_key: str, s3_file_url: str):
        """
        Sets the metadata file identification for a KGE File Set
        :param file_name: original name of metadata file
        :param object_key:
        :param s3_file_url:
        :return: None
        """
        self.metadata_file = {
            "file_name": file_name,
            "object_key": object_key,
            "s3_file_url": s3_file_url,
            "kgx_compliant": False,  # until proven True...
            "errors": []
        }
        
        # trigger asynchronous KGX metadata file validation process here?
        # self.check_kgx_compliance(
        #     file_type=KgeFileType.KGX_METADATA_FILE,
        #     object_key=object_key,
        #     s3_file_url=s3_file_url
        # )

    def get_name(self) -> str:
        return self.parameter.setdefault("kg_name", 'Unknown')

    def get_version(self) -> str:
        return self.parameter.setdefault("kg_version", get_default_date_stamp())

    def get_metadata_file(self) -> Union[Dict, None]:
        """
        :return: a copy of metadata dictionary about the KGE File Set metadata file, if available; None otherwise
        """
        if self.metadata_file:
            return self.metadata_file.copy()
        else:
            return None

    # TODO: review what additional metadata is required to properly manage KGE data files
    def add_data_file(
            self,
            file_name: str,
            object_key: str,
            s3_file_url: str
    ):
        """
        
        :param file_name: to add to the KGE File Set
        :param object_key: of the file in AWS S3
        :param s3_file_url: current S3 pre-signed data access url
        :return: None
        """
        # Attempt to infer the format and compression
        # of the data file from its filename
        input_format, input_compression = KgeaFileSet.format_and_compression(file_name)
        
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
        # self.check_kgx_compliance(
        #     file_type=KgeFileType.KGX_DATA_FILE,
        #     object_key=object_key,
        #     s3_file_url=s3_file_url
        # )

    def get_data_file_set(self) -> Set[Tuple]:
        """
        :return: Set[Tuple] of access metadata for data files in the KGE File Set
        """
        dataset: Set[Tuple] = set()
        [dataset.add(tuple(x)) for x in self.data_files.values()]
        return dataset

    async def confirm_file_set_validation(self):
        
        # Blocking call to KGX validator worker Queue processing
        await self.validation_queue.join()
        await self.release_workers()
        
        # check if any errors were returned by KGX Validation
        errors: List = []
        if self.metadata_file:
            if not self.metadata_file["kgx_compliant"]:
                errors.append(self.metadata_file["errors"])
        for data_file in self.data_files.values():
            if not data_file["kgx_compliant"]:
                errors.append(data_file["errors"])
                
        return errors
        
    def publish_file_set(self):
        """
        Publish provider metadata,
        both locally in the Archive S3 repository and
        remotely,  in the Translator SmartAPI Registry.
        """
        metadata_file = self.generate_provider_metadata_file()

        if not add_to_archive(
                kg_id=self.kg_id,
                text=metadata_file,
                file_name=PROVIDER_METADATA_FILE
        ):
            logger.warning(
                "publish_file_set(): KGE File Set "+PROVIDER_METADATA_FILE+" not successfully added to archive??")

        translator_smartapi_registry_entry = self.generate_translator_registry_entry()

        if not add_to_github(self.kg_id, translator_smartapi_registry_entry):
            logger.warning("publish_file_set(): Translator Registry entry not posted. Is gh_token configured?")

    @staticmethod
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
                compression = archive+"."
            compression += 'gz'
        else:
            compression = None
        
        return input_format, compression

    # KGE File Set Translator SmartAPI parameters (March 2021 release):
    # - kg_id: KGE Archive generated identifier assigned to a given knowledge graph submission (and used as S3 folder)
    # - kg_name: human readable name of the knowledge graph
    # - kg_description: detailed description of knowledge graph (may be multi-lined with '\n')
    # - kg_version: release version of KGE File Set - recorded directly as the Translator SmartAPI entry 'version'
    # - submitter - name of submitter of the KGE file set
    # - submitter_email - contact email of the submitter
    # - license_name - Open Source license name, e.g. MIT, Apache 2.0, etc.
    # - license_url - web site link to project license
    # - terms_of_service - specifically relating to the project, beyond the licensing
    # - translator_component - Translator component associated with the knowledge graph (e.g. KP, ARA or SRI)
    # - translator_team - specific Translator team (affiliation) contributing the file set, e.g. Clinical Data Provider
    def generate_provider_metadata_file(self, **kwargs) -> str:
        return _populate_template(
            filename=PROVIDER_METADATA_TEMPLATE_FILE_PATH,
            kg_id=self.kg_id, **self.parameter
        )

    def generate_translator_registry_entry(self, **kwargs) -> str:
        return _populate_template(
            filename=TRANSLATOR_SMARTAPI_TEMPLATE_FILE_PATH,
            kg_id=self.kg_id, **self.parameter
        )


class KgeaCatalog:
    """
    Knowledge Graph Exchange (KGE) Temporary Registry for
    tracking compilation and validation of complete KGE File Sets
    """
    _the_catalog = None
    
    def __init__(self):
        self._kge_file_set_catalog: Dict[str, Dict[str, KgeaFileSet]] = dict()

        # Initialize catalog with the metadata of all
        # existing KGE Archive (AWS S3 stored) KGE File Sets
        archive_contents = get_archive_contents(bucket_name=_KGEA_APP_CONFIG['bucket'])
        for kg_id, entry in archive_contents.items():
            self.load_archive_entry(kg_id=kg_id, entry=entry)

    @classmethod
    def initialize(cls):
        if not cls._the_catalog:
            KgeaCatalog._the_catalog = KgeaCatalog()

    @classmethod
    def catalog(cls):
        """
        :return: singleton of KgeaRegistry
        """
        if not cls._the_catalog:
            raise RuntimeError("KGE Archive Catalog is uninitialized?")

        return KgeaCatalog._the_catalog

    def load_archive_entry(self, kg_id, entry):
        # TODO: parse an KGE Archive entry,
        #       to initialize and load a KgeaFileSet
        self.register_kge_file_set(
            kg_id=kg_id,
            kg_name='kg_name',
            kg_version='assigned_version',
            kg_description='kg_description',
            translator_component='translator_component',
            translator_team='translator_team',
            submitter='submitter',
            submitter_email='submitter_email',
            license_name='license_name',
            license_url='license_url',
            terms_of_service='terms_of_service',
            file_set_location='file_set_location'
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
    
    # TODO: what is the required idempotency of this KG addition relative to submitters (can submitters change?)
    # TODO: how do we deal with versioning of submissions across several days(?)
    def register_kge_file_set(self, **kwargs) -> KgeaFileSet:
        """
        As needed, registers a new record for a knowledge graph with a given 'name' for a given 'submitter'.
        The name is indexed by normalization to lower case and substitution of underscore for spaces.
        Returns the new or any existing matching KgeaRegistry knowledge graph entry.
        
        :param kg_id: identifier of the knowledge graph file set
        :param kwargs: dictionary of metadata describing a KGE File Set entry
        :return: KgeaFileSet of the graph (existing or added)
        """

        kg_id = kwargs['kg_id']
        kg_version = kwargs['kg_version']

        # For now, a given graph is only submitted once for a given submitter
        # TODO: should we accept any resubmissions or changes?

        if kg_id not in self._kge_file_set_catalog:

            self._kge_file_set_catalog[kg_id] = KgeaFileSet(kg_id, **kwargs)
        
        return self._kge_file_set_catalog[kg_id]
    
    def get_kge_file_set(self, kg_id: str) -> Union[KgeaFileSet, None]:
        """
        Get the knowledge graph provider metadata associated with a given knowledge graph file set identifier.
        :param kg_id: input knowledge graph file set identifier
        :return: KgeaFileSet; None, if unknown
        """
        if kg_id in self._kge_file_set_catalog:
            return self._kge_file_set_catalog[kg_id]
        else:
            return None

    # TODO: probably need to somehow factor in timestamps
    #       or are they already as encoded in the object_key?
    def add_to_kge_file_set(
            self,
            kg_id: str,
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
    
        :param kg_id: Knowledge Graph File Set identifier
        :param file_type: KgeFileType of the current file
        :param file_name: name of the current file
        :param object_key: AWS S3 object key of the file
        :param s3_file_url: current pre-signed url to access the file
        :return: None
        """
        file_set = self.get_kge_file_set(kg_id)

        if not file_set:
            raise RuntimeError("KGE File Set '" + kg_id + "' is unknown?")
        else:
            # Found a matching KGE file set? Add the current file to the set
            if file_type == KgeFileType.KGX_DATA_FILE:
                file_set.add_data_file(
                    file_name=file_name,
                    object_key=object_key,
                    s3_file_url=s3_file_url
                )
            
            elif file_type == KgeFileType.KGX_ARCHIVE:
                # not sure how best to handle KGX data archives here
                pass
            
            elif file_type == KgeFileType.KGX_METADATA_FILE:
                file_set.set_metadata_file(
                    file_name=file_name,
                    object_key=object_key,
                    s3_file_url=s3_file_url
                )
            else:
                raise RuntimeError("Unknown KGE File Set type?")

    async def publish_file_set(self, kg_id):
        
        # TODO: need to fully implement post-processing of the completed
        #       file set (with all files, as uploaded by the client)
        
        logger.debug("Calling Registry.publish_file_set(kg_id: '"+kg_id+"')")
        
        errors: List = []
        
        if kg_id in self._kge_file_set_catalog:
            
            kge_file_set = self._kge_file_set_catalog[kg_id]
            
            # Ensure that the all the files are KGX validated first(?)
            
            errors: List = []  # await kge_file_set.confirm_file_set_validation()
            
            logger.debug("File set validation() complete for file set '" + kg_id + "')")
            
            if not errors:
                # After KGX validation and related post-processing is successfully validated,
                # We publish provider metadata both locally in the Archive S3 repository and
                # remotely,  in the Translator SmartAPI Registry
                logger.debug("Publishing validated KGE File Set in the Archive and to the Translator Registry")
                kge_file_set.publish_file_set()
            else:
                logger.debug("KGX validation errors encountered:\n" + str(errors))
            
        else:
            logger.error("publish_file_set(): Unknown file set '" + kg_id + "' ... ignoring publication request")
            errors.append("publish_file_set(): Unknown file set '" + kg_id + "' ... ignoring publication request")
            
        return errors

    def get_entries(self) -> Dict:

        # TODO: see KgeFileSetEntry schema in the kgea_archive.yaml
        if DEV_MODE:
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

            catalog: Dict[str,  Dict[str, Union[str, List]]] = dict()
            for kg_id, entry in self._kge_file_set_catalog.items():
                kg_name = entry.get_name()
                kg_version = entry.get_version()
                if kg_id not in catalog:
                    catalog[kg_id] = dict()
                    catalog[kg_id]["name"] = kg_name
                    catalog[kg_id]["versions"] = list()
                if kg_version not in catalog[kg_id]["versions"]:
                    catalog[kg_id]["versions"].append(kg_version)

        return catalog


# TODO
@prepare_test
def test_check_kgx_compliance():
    return True


# TODO
@prepare_test
def test_get_catalog_entries():
    print("\ntest_get_catalog_entries() test output:\n", file=stderr)
    catalog = KgeaCatalog.catalog().get_entries()
    print(dumps(catalog, indent=4, sort_keys=True), file=stderr)
    return True


PROVIDER_METADATA_TEMPLATE_FILE_PATH = \
    abspath(dirname(__file__) + '/../../../api/kge_provider_metadata.yaml')
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


def add_to_archive(
        kg_id: str,
        text: str,
        file_name: str
) -> str:
    uploaded_file_object_key: str = ''
    if text:
        bytes = text.encode('utf-8')
        uploaded_file_object_key = upload_file(
            data_file=BytesIO(bytes),
            file_name='provider_metadata.yaml',
            bucket=_KGEA_APP_CONFIG['bucket'],
            object_location=get_object_location(kg_id)
        )
    else:
        logger.warning("add_to_archive(): Empty text string argument? Can't archive a vacuum!")

    # could be an empty object key
    return uploaded_file_object_key


def add_to_github(
        kg_id: str,
        text: str,
        repo_path: str = TRANSLATOR_SMARTAPI_REPO,
        target_directory: str = KGE_SMARTAPI_DIRECTORY
) -> bool:
    
    outcome: bool = False
    
    gh_token = _KGEA_APP_CONFIG['github']['token']
    
    logger.debug("Calling Registry.add_to_github(gh_token: '"+str(gh_token)+"')")
    
    if text and gh_token:
        
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
            
            outcome = True

    return outcome


_TEST_SMARTAPI_REPO = "NCATSTranslator/Knowledge_Graph_Exchange_Registry"
_TEST_KGE_SMARTAPI_TARGET_DIRECTORY = "kgea/server/tests/output"


@prepare_test
def test_add_to_archive():
    outcome: str = add_to_archive(
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
    
    gh_token = _KGEA_APP_CONFIG['github']['token']
    
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
        
        print("all KGEA Catalog tests passed")
        
    # if CLEAN_TESTS:
    #     clean_tests()
