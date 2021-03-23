"""
KGE Interface module to Knowledge Graph eXchange (KGX)
"""
from os import getenv
from enum import Enum

import logging
from typing import Dict, Union

logger = logging.getLogger(__name__)
DEBUG = getenv('DEV_MODE', default=False)
if DEBUG:
    logger.setLevel(logging.DEBUG)


def prepare_test(func):
    def wrapper():
        return func()
    
    return wrapper


class KgeFileType(Enum):
    KGX_UNKNOWN = "unknown file type"
    KGX_METADATA_FILE = "KGX metadata file"
    KGX_DATA_FILE = "KGX data file"


def is_kgx_compliant(file_type: KgeFileType, s3_object_url: str) -> bool:
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
def convert_to_yaml(spec):
    yaml_file = lambda spec: spec
    return yaml_file(spec)


# TODO
@prepare_test
def test_convert_to_yaml():
    return True


# TODO
def create_smartapi(submitter, kg_name):
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


# TODO
def translator_registration(submitter, kg_name):
    # TODO: check if the kg_name is already registered?
    api_specification = create_smartapi(submitter, kg_name)
    translator_registry_url = add_to_github(api_specification)


# TODO
@prepare_test
def test_translator_registration():
    return True


class KgeaFileSet:
    """
    Class wrapping information about a KGE file set being
    assembled in AWS S3, for SmartAPI registration and client access
    """
    
    def __init__(self, kg_name: str, submitter: str):
        """
        
        :param kg_name: name of knowledge graph in entry
        :param submitter: owner of knowledge graph
        """
        self.name: str = kg_name
        self.submitter = submitter
        self.files: Dict[str, str] = dict()


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
        self._knowledge_graphs: Dict[str, KgeaFileSet] = dict()
    
    @staticmethod
    def normal_name(kg_name: str) -> str:
        # TODO: need to review graph name normalization and indexing
        #       against various internal graph use cases, e.g. lookup
        kg_name = kg_name.lower()  # all lower case
        kg_name = kg_name.replace(' ', '_')  # spaces with underscores
        return kg_name
    
    # TODO: what is the required idempotency of this KG addition relative to submitters (can submitters change?)
    # TODO: how do we deal with versioning of submissions across several days(?)
    def add_knowledge_graph(self, submitter: str, kg_name: str) -> KgeaFileSet:
        """
        As needed, adds a new record for a knowledge graph with a given 'name' for a given 'submitter'.
        The name is indexed by normalization to lower case and substitution of underscore for spaces.
        Returns the new or any existing KgeaRegistry knowledge graph entry.
        
        :param submitter: 'owner' of the knowledge graph submission
        :param kg_name: of the knowledge graph (normalized to lower case and all spaces converted to underscores
        :return: KgeaFileSet of the graph (existing or added)
        """
        kg_name = self.normal_name(kg_name)
        
        # For now, a given graph is only submitted once for a given submitter
        if kg_name not in self._knowledge_graphs:
            self._knowledge_graphs[kg_name] = KgeaFileSet(kg_name, submitter)
        
        return self._knowledge_graphs[kg_name]
    
    def get_knowledge_graph(self, kg_name: str) -> Union[KgeaFileSet, None]:
        """
        
        :param kg_name:
        :return:
        """
        kg_name = self.normal_name(kg_name)
        if kg_name in self._knowledge_graphs:
            return self._knowledge_graphs[kg_name]
        else:
            return None
    
    # TODO: this is code extracted from the kgea_handlers.py file upload... needs a total rethinking
    def add_to_kge_file_set(
            self,
            submitter: str, kg_name: str, file_type: KgeFileType,
            uploaded_file_object_key: str, s3_file_url: str
    ) -> str:
        """
        This method adds the given input file to a local catalog of recently
        updated files, within which files formats are asynchronously validated
        to KGX compliance, and the entire file set assessed for completeness.
        the response sent back contains a kind of kgx fileset id , if available.
        An exception is raise if there is an error.
    
        :param submitter: Submitter of the Knowledge Graph of focus
        :param kg_name: Knowledge Graph Name
        :param file_type: File type
        :param uploaded_file_object_key: str
        :param s3_file_url: str
        :return: kge_file_set_id: to the local (not SmartAPI) KGE Registry which is a kind of pointer to the KGX file set
        """
        """
        s3_metadata = {file_type: dict({})}
        s3_metadata[file_type][uploaded_file_object_key] = s3_file_url
    
        # Validate the uploaded file
        # TODO: just a stub predicate... not sure if kgx validation
        #       can be done in real time for large files. Upload may time out?
        if is_kgx_compliant(file_type, s3_file_url):
    
            # If we get this far, time to register the KGE file in SmartAPI?
            # TODO: how do we validate that files are valid KGX and complete with their metadata?
            # Maybe need a separate validation process
            translator_registration(submitter, kg_name)
    
        else:
            error_msg: str = "upload_kge_file(uploaded_file_object_key: " + \
                             str(uploaded_file_object_key) + ") is not a KGX compliant file."
            logger.error(error_msg)
            raise RuntimeError(error_msg)"""
        
        # TODO: stub implementation
        kg_name = KgeaRegistry.normal_name(kg_name)
        
        return kg_name


"""
Unit Tests
* Run each test function as an assertion if we are debugging the project
"""
if __name__ == '__main__':
    print("TODO: Smart API Registry functions and tests")
    assert (test_convert_to_yaml())
    assert (test_add_to_github())
    assert (test_api_registered())
    
    print("all registry tests passed")
