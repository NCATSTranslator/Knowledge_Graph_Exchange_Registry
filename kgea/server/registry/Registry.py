"""
KGE Interface module to the operational management of
File Sets within Knowledge Graph eXchange (KGX) application.
Note that this management is short term and doesn't read
back the contents of the remote storage system (i.e. AWS S3)
but just keeps an in memory copy of the (meta-)data being
received from clients to the application, each time the
application is started up.

Set the RUN_TESTS environment variable to a non-blank value
whenever you wish to run the unit tests in this module...
Set the CLEAN_TESTS environment variable to a non-blank value
to clean up test outputs from RUN_TESTS runs.

The values for the Translator SmartAPI endpoint
are hard coded in the module for now but may change in the future.
This should be reviewed when needed...

TRANSLATOR_SMARTAPI_REPO = "NCATS-Tangerine/translator-api-registry"
KGE_SMARTAPI_DIRECTORY = "translator_knowledge_graph_archive"
"""
from typing import Dict, Union, Tuple, Set, List
from enum import Enum
from string import Template

from sys import stderr
from os import getenv
from os.path import abspath, dirname

import threading, queue

import logging

from github import Github

from kgea.server.config import get_app_config

logger = logging.getLogger(__name__)
DEBUG = getenv('DEV_MODE', default=False)
if DEBUG:
    logger.setLevel(logging.DEBUG)

DEBUG = getenv('DEV_MODE', default=False)


RUN_TESTS = getenv('RUN_TESTS', default=False)
CLEAN_TESTS = getenv('CLEAN_TESTS', default=False)


TRANSLATOR_SMARTAPI_REPO = "NCATS-Tangerine/translator-api-registry"
KGE_SMARTAPI_DIRECTORY = "translator_knowledge_graph_archive"

# Opaquely access the configuration dictionary
KGEA_APP_CONFIG = get_app_config()


def prepare_test(func):
    def wrapper():
        print("\n" + str(func) + " ----------------\n")
        return func()
    return wrapper


class KgeFileType(Enum):
    KGX_UNKNOWN = "unknown file type"
    KGX_METADATA_FILE = "KGX metadata file"
    KGX_DATA_FILE = "KGX data file"


class KgeaFileSet:
    """
    Class wrapping information about a KGE file set being
    assembled in AWS S3, for SmartAPI registration and client access
    """
    
    _expected = [
        "file_set_location",
        "kg_name",
        "kg_description",
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

        self.metadata_file: Union[List, None] = None
        self.data_files: Dict[str, List] = dict()
        
        # this Queue serves at the communication link
        # between a KGX validation process and the Registry
        self.validation_queue = queue.Queue()

        # turn-on the KGX Validation thread
        threading.Thread(target=self.validator, daemon=True).start()

    def validator(self):
        while True:
            kge_file_spec = self.validation_queue.get()
            
            file_type = kge_file_spec['file_type']
            s3_object_url = kge_file_spec['s3_object_url']
            
            print(f'Working on {kge_file_spec}', file=stderr)
        
            # Run KGX validation here
            if kge_file_spec['file_type'] == KgeFileType.KGX_DATA_FILE:
                pass
            elif kge_file_spec['file_type'] == KgeFileType.KGX_METADATA_FILE:
                pass
            else:
                print(f'WARNING: Unknown KgeFileType{file_type} ... ignoring', file=stderr)
        
            print(f'Finished {kge_file_spec}', file=stderr)
            self.validation_queue.task_done()

    def check_kgx_compliance(self, file_type: KgeFileType, s3_object_url: str):
        """
        Stub implementation of KGX Validation of a
        KGX graph file stored in back end AWS S3

        :param file_type: str
        :param s3_object_url: str
        :return: bool
        """
        logger.debug("Checking if " + str(file_type) + " file " + s3_object_url + " is KGX compliant")
    
        kge_file_spec = {"file_type": file_type, "s3_object_url": s3_object_url}
        
        # delegate validation of this file
        # to the KGX process reading this Queue
        self.validation_queue.put(kge_file_spec)
            
    def set_metadata_file(self, file_name: str, object_key: str, s3_file_url: str):
        """
        Sets the metadata file identification for a KGE File Set
        :param file_name: original name of metadata file
        :param object_key:
        :param s3_file_url:
        :return: None
        """
        self.metadata_file = [file_name, object_key, s3_file_url]
        
        # trigger asynchronous KGX metadata file validation process here?
        self.check_kgx_compliance(KgeFileType.KGX_METADATA_FILE, s3_file_url)

    def get_metadata_file(self) -> Union[Tuple, None]:
        """
        :return: a Tuple of metadata about the KGE File Set metadata file, if available; None otherwise
        """
        if self.metadata_file:
            return tuple(self.metadata_file)
        else:
            return None

    # TODO: review what additional metadata is required to properly manage KGE data files
    def add_data_file(self, file_name: str, object_key: str, s3_file_url: str):
        """
        
        :param file_name: to add to the KGE File Set
        :param object_key: of the file in AWS S3
        :param s3_file_url: current S3 pre-signed data access url
        :return: None
        """
        self.data_files[object_key] = [file_name, object_key, s3_file_url]
        
        # trigger asynchronous KGX metadata file validation process here?
        self.check_kgx_compliance(KgeFileType.KGX_DATA_FILE, s3_file_url)

    def get_data_file_set(self) -> Set[Tuple]:
        """
        :return: Set[Tuple] of access metadata for data files in the KGE File Set
        """
        dataset: Set[Tuple] = set()
        [dataset.add(tuple(x)) for x in self.data_files.values()]
        return dataset

    def confirm_file_set_validation(self):
        # Blocking call to KGX validator worker Queue processing
        self.validation_queue.join()
    
    def translator_registration(self):
        """
        Register the current file set in the Translator SmartAPI Registry
        :return:
        """
        api_specification = create_smartapi(**self.parameter)
        add_to_github(self.kg_id, api_specification)


class KgeaRegistry:
    """
    Knowledge Graph Exchange (KGE) Temporary Registry for
    tracking compilation and validation of complete KGE File Sets
    """
    _initialized = False
    
    @classmethod
    def registry(cls):
        """
        :return: singleton of KgeaRegistry
        """
        if not cls._initialized:
            KgeaRegistry._registry = KgeaRegistry()
            cls._initialized = True
        return KgeaRegistry._registry
    
    def __init__(self):
        # This particular local 'registry' only has 'application runtime' scope
        # and is mainly used during the assembly and initial publication of
        # KGE File Sets. The AWS S3 repository of file sets is persistent
        # in between application sessions... so is the authority on the
        # full catalog of available KGE File Sets, at any point in time.
        self._kge_file_set_registry: Dict[str, KgeaFileSet] = dict()
    
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
    def register_kge_file_set(self, kg_id: str, **kwargs) -> KgeaFileSet:
        """
        As needed, registers a new record for a knowledge graph with a given 'name' for a given 'submitter'.
        The name is indexed by normalization to lower case and substitution of underscore for spaces.
        Returns the new or any existing matching KgeaRegistry knowledge graph entry.
        
        :param kg_id: identifier of the knowledge graph file set
        :param kwargs: dictionary of metadata describing a KGE File Set entry
        :return: KgeaFileSet of the graph (existing or added)
        """
        
        # For now, a given graph is only submitted once for a given submitter
        # TODO: should we accept any resubmissions or changes?
        if kg_id not in self._kge_file_set_registry:
            self._kge_file_set_registry[kg_id] = KgeaFileSet(kg_id, **kwargs)
        
        return self._kge_file_set_registry[kg_id]
    
    def get_kge_file_set(self, kg_id: str) -> Union[KgeaFileSet, None]:
        """
        Get the knowledge graph provider metadata associated with a given knowledge graph file set identifier.
        :param kg_id: input knowledge graph file set identifier
        :return: KgeaFileSet; None, if unknown
        """
        if kg_id in self._kge_file_set_registry:
            return self._kge_file_set_registry[kg_id]
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
            elif file_type == KgeFileType.KGX_METADATA_FILE:
                file_set.set_metadata_file(
                    file_name=file_name,
                    object_key=object_key,
                    s3_file_url=s3_file_url
                )
            else:
                raise RuntimeError("Unknown KGE File Set type?")

    def publish_file_set(self, kg_id):
        # TODO: need to fully implement post-processing of the completed
        #       file set (with all files, as uploaded by the client)
        logger.debug("Calling Registry.publish_file_set(kg_id: '"+kg_id+"')")

        if kg_id in self._kge_file_set_registry:
            kge_file_set = self._kge_file_set_registry[kg_id]
            
            # Ensure that the all the files are KGX validated first(?)
            kge_file_set.confirm_file_set_validation()
            
            logger.debug("File set validation() complete for file set '" + kg_id + "')")
            
            # Don't publish to the Translator SmartAPI Registry until you
            # are confident of KGX validation and related post-processing
            # kge_file_set.translator_registration()
        else:
            logger.error("publish_file_set(): Unknown file set '" + kg_id + "' ... ignoring publication request")


# TODO
@prepare_test
def test_check_kgx_compliance():
    return True


TRANSLATOR_SMARTAPI_TEMPLATE_FILE_PATH = \
    abspath(dirname(__file__) + '/../../api/kge_smartapi_entry.yaml')


# KGE File Set Translator SmartAPI parameters (March 2021 release) set here are the following string keyword arguments:
# - kg_id: KGE Archive generated identifier assigned to a given knowledge graph submission (and used as S3 folder)
# - kg_name: human readable name of the knowledge graph
# - kg_description: detailed description of knowledge graph (may be multi-lined with '\n')
# - submitter - name of submitter of the KGE file set
# - submitter_email - contact email of the submitter
# - license_name - Open Source license name, e.g. MIT, Apache 2.0, etc.
# - license_url - web site link to project license
# - terms_of_service - specifically relating to the project, beyond the licensing
# - translator_component - Translator component associated with the knowledge graph (e.g. KP, ARA or SRI)
# - translator_team - specific Translator team (affiliation) contributing the file set, e.g. Clinical Data Provider
def create_smartapi(**kwargs) -> str:
    with open(TRANSLATOR_SMARTAPI_TEMPLATE_FILE_PATH, 'r') as template_file:
        smart_api_template = template_file.read()
        # Inject KG-specific parameters into template
        smart_api_entry = Template(smart_api_template).substitute(**kwargs)
        return smart_api_entry


_TEST_TSE_PARAMETERS = dict(
    kg_id="disney_small_world_graph",
    kg_name="Disneyland Small World Graph",
    kg_description="""Voyage along the Seven Seaways canal and behold a cast of
    almost 300 Audio-Animatronics dolls representing children
    from every corner of the globe as they sing the classic
    anthem to world peace—in their native languages.""",
    translator_component="KP",
    translator_team="Disney Knowledge Provider",
    submitter="Mickey Mouse",
    submitter_email="mickey.mouse@disneyland.disney.go.com",
    license_name="Artistic 2.0",
    license_url="https://opensource.org/licenses/Artistic-2.0",
    terms_of_service="https://disneyland.disney.go.com/en-ca/terms-conditions/"
)
_TEST_TSE = 'empty'


@prepare_test
def test_create_smartapi():
    global _TEST_TSE
    print("\ntest_create_smartapi() test output:\n", file=stderr)
    _TEST_TSE = create_smartapi(**_TEST_TSE_PARAMETERS)
    print(str(_TEST_TSE), file=stderr)
    return True


def add_to_github(
        kg_id: str,
        api_specification: str,
        repo: str = TRANSLATOR_SMARTAPI_REPO,
        target_directory: str = KGE_SMARTAPI_DIRECTORY
) -> bool:
    
    outcome: bool = False
    
    gh_token = KGEA_APP_CONFIG['github']['token']
    
    logger.debug(
        "Calling Registry.add_to_github(\n"
        "\t### gh_token = '"+str(gh_token)+"'\n"
    )
    
    if gh_token:
        
        logger.debug(
            "\t### api_specification = '''\n" + str(api_specification)[:60] + "...\n'''\n" +
            "\t### repo_path = '" + str(repo) + "'\n" +
            "\t### target_directory = '" + str(target_directory) + "'"
        )
    
        if api_specification and repo and target_directory:
            
            entry_path = target_directory+"/"+kg_id + ".yaml"
            
            logger.debug("\t### gh_url = '" + str(entry_path) + "'")
            
            g = Github(gh_token)
            repo = g.get_repo(repo)
            
            repo.create_file(
                entry_path,
                "Posting KGE entry  '" + kg_id + "' to Translator SmartAPI Registry.",
                api_specification,  # API YAML specification as a string
            )
            
            outcome = True

    logger.debug(")\n")
    return outcome


_TEST_SMARTAPI_REPO = "NCATSTranslator/Knowledge_Graph_Exchange_Registry"
_TEST_KGE_SMARTAPI_TARGET_DIRECTORY = "kgea/server/tests/output"


@prepare_test
def test_add_to_github():
    
    outcome: bool = add_to_github(
        "kge_test_entry",
        _TEST_TSE,
        repo=_TEST_SMARTAPI_REPO,
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
    
    gh_token = KGEA_APP_CONFIG['github']['token']
    
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
        
        # The create_smartapi() and add_to_github() methods both seem to work, as coded as of 29 March 2021,
        # thus we comment out this test to avoid repeated commits to the KGE repo. The 'clean_tests()' below
        # is thus not currently needed either, since it simply removes the github artifacts from add_to_github().
        # This code can be uncommented if these features need to be tested again in the future
        # assert (test_create_smartapi())
        # assert (test_add_to_github())
        
        print("all registry tests passed")
        
    # if CLEAN_TESTS:
    #     clean_tests()
