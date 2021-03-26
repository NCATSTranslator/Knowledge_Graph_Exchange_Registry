"""
KGE Interface module to Knowledge Graph eXchange (KGX)
"""
from sys import stderr
from os import getenv
from os.path import abspath, dirname
from enum import Enum

from string import Template

import logging
from typing import Dict, Union, Tuple, Set, List

logger = logging.getLogger(__name__)
DEBUG = getenv('DEV_MODE', default=False)
if DEBUG:
    logger.setLevel(logging.DEBUG)


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
        "kg_id",
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
    
    def __init__(self, **kwargs):
        """
        KgeaFileSet constructor
        
        :param kg_name: name of knowledge graph in entry
        :param submitter: owner of knowledge graph
        """
        self.parameter: Dict = dict()
        for key, value in kwargs:
            
            if key not in self._expected:
                logger.warning("Unexpected KgeaFileSet parameter '"+str(key)+"'... ignored!")
                continue
            
            self.parameter[key] = value

        self.metadata_file: Union[List, None] = None
        self.data_files: Dict[str, List] = dict()

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
        check_kgx_compliance(KgeFileType.KGX_METADATA_FILE, s3_file_url)

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
        check_kgx_compliance(KgeFileType.KGX_DATA_FILE, s3_file_url)

    def get_data_file_set(self) -> Set[Tuple]:
        """
        :return: Set[Tuple] of access metadata for data files in the KGE File Set
        """
        dataset: Set[Tuple] = set()
        [dataset.add(tuple(x)) for x in self.data_files.values()]
        return dataset
    
    def translator_registration(self):
        """
        Register the current file set in the Translator SmartAPI Registry
        :return:
        """
        api_specification = create_smartapi(**self.parameter)
        add_to_github(api_specification)


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
        self._kge_file_set: Dict[str, KgeaFileSet] = dict()
    
    @staticmethod
    def normalize_name(kg_name: str) -> str:
        # TODO: need to review graph name normalization and indexing
        #       against various internal graph use cases, e.g. lookup
        #       and need to be robust to user typos (e.g. extra blank spaces?
        #       invalid characters?). Maybe convert to regex cleanup?
        kg_id = kg_name.lower()  # all lower case
        kg_id = kg_id.replace(' ', '_')  # spaces with underscores
        return kg_id
    
    # TODO: what is the required idempotency of this KG addition relative to submitters (can submitters change?)
    # TODO: how do we deal with versioning of submissions across several days(?)
    def add_kge_file_set(self, kg_id: str, **kwargs) -> KgeaFileSet:
        """
        As needed, adds a new record for a knowledge graph with a given 'name' for a given 'submitter'.
        The name is indexed by normalization to lower case and substitution of underscore for spaces.
        Returns the new or any existing matching KgeaRegistry knowledge graph entry.
        
        :param kg_id: identifier of the knowledge graph file set
        :param kwargs: dictionary of metadata describing a KGE File Set entry
        :return: KgeaFileSet of the graph (existing or added)
        """
        
        # For now, a given graph is only submitted once for a given submitter
        # TODO: should we accept any resubmissions or changes?
        if kg_id not in self._kge_file_set:
            self._kge_file_set[kg_id] = KgeaFileSet(kg_id=kg_id, **kwargs)
        
        return self._kge_file_set[kg_id]
    
    def get_kge_file_set(self, kg_id: str) -> Union[KgeaFileSet, None]:
        """
        Get the knowledge graph provider metadata associated with a given knowledge graph file set identifier.
        :param kg_id: input knowledge graph file set identifier
        :return: KgeaFileSet; None, if unknown
        """
        if kg_id in self._kge_file_set:
            return self._kge_file_set[kg_id]
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


def check_kgx_compliance(file_type: KgeFileType, s3_object_url: str) -> bool:
    """
    Stub implementation of KGX Validation of a
    KGX graph file stored in back end AWS S3

    :param file_type: str
    :param s3_object_url: str
    :return: bool
    """
    logger.debug("Checking if " + str(file_type) + " file " + s3_object_url + " is KGX compliant")
    return not (file_type == KgeFileType.KGX_UNKNOWN)


# TODO
@prepare_test
def test_check_kgx_compliance():
    return True


TRANSLATOR_SMARTAPI_TEMPLATE_FILE_PATH = \
    abspath(dirname(__file__) + '/../../api/kge_smartapi_entry.yaml')


# TODO
# KGE File Set Translator SmartAPI parameters set here are the following string keyword arguments:
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
#
def create_smartapi(**kwargs) -> str:
    with open(TRANSLATOR_SMARTAPI_TEMPLATE_FILE_PATH, 'r') as template_file:
        smart_api_template = template_file.read()
        # Inject KG-specific parameters into template
        smart_api_entry = Template(smart_api_template).substitute(**kwargs)
        return smart_api_entry


_TEST_TRANSLATOR_SMARTAPI_ENTRY = create_smartapi(
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


# TODO
@prepare_test
def test_create_smartapi():
    print("\ntest_create_smartapi() test output:\n", file=stderr)
    print(_TEST_TRANSLATOR_SMARTAPI_ENTRY, file=stderr)
    
    return True


# TODO
def add_to_github(api_specification):
    # Stub implementation
    # using https://github.com/NCATS-Tangerine/translator-api-registry
    pass


# TODO
@prepare_test
def test_add_to_github():
    add_to_github(_TEST_TRANSLATOR_SMARTAPI_ENTRY)
    return True


# TODO
def api_registered(kg_id:str):
    return True


# TODO
@prepare_test
def test_api_registered():
    return True


# TODO
@prepare_test
def test_translator_registration():
    return True


"""
Unit Tests
* Run each test function as an assertion if we are debugging the project
"""
if __name__ == '__main__':
    print("Smart API Registry functions and tests")
    assert (test_create_smartapi())
    assert (test_add_to_github())
    assert (test_api_registered())
    
    print("all registry tests passed")
