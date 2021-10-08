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
from os.path import dirname, abspath

from typing import Dict, Union, Set, List, Any, Optional, Tuple
from enum import Enum
from string import Template, punctuation
from datetime import date, datetime

# TODO: maybe convert Catalog components to Python Dataclasses?
# from dataclasses import dataclass

import re

import threading
from asyncio import (
    create_task,
    gather,
    sleep,
    Queue,
    Task,
    QueueFull,
    run
)

from io import BytesIO, StringIO
import tempfile

import json
from jsonschema import (
    ValidationError,
    SchemaError,
    validate as json_validator
)

import yaml
try:
    from yaml import CLoader as Loader, CDumper as Dumper
    from yaml.scanner import ScannerError
except ImportError:
    from yaml import Loader, Dumper
    from yaml.scanner import ScannerError

from github import Github
from github.GithubException import UnknownObjectException, BadCredentialsException

import smart_open

from kgx.utils.kgx_utils import GraphEntityType
from kgx.transformer import Transformer
from kgx.validator import Validator

from kgea.config import (
    get_app_config,
    PROVIDER_METADATA_FILE,
    FILE_SET_METADATA_FILE, CONTENT_METADATA_FILE
)

from kgea.server.web_services.models import (
    KgeMetadata,
    KgeFileSetStatusCode,
    KgeFile,
    KgeProviderMetadata,
    KgeFileSetMetadata
)

from kgea.server.web_services.kgea_file_ops import (
    default_s3_bucket,
    print_error_trace,
    get_default_date_stamp,
    get_object_location,
    get_archive_contents,
    get_object_key,
    with_version,
    load_s3_text_file,
    compress_fileset,
    aggregate_files,
    copy_file,
    upload_file,
    random_alpha_string,
    object_key_exists,
    extract_data_archive
)

from kgea.server.web_services.sha_utils import sha1_manifest

import logging
logger = logging.getLogger(__name__)

DEV_MODE = getenv('DEV_MODE', default=False)
OVERRIDE = True

RUN_TESTS = getenv('RUN_TESTS', default=False)
CLEAN_TESTS = getenv('CLEAN_TESTS', default=False)


def prepare_test(func):
    """

    :param func:
    :return:
    """
    
    def wrapper():
        """

        :return:  function called
        """
        print("\n" + str(func) + " ----------------\n")
        return func()
    
    return wrapper


# Opaquely access the configuration dictionary
_KGEA_APP_CONFIG = get_app_config()
site_hostname = _KGEA_APP_CONFIG['site_hostname']

Number_of_Archiver_Tasks = \
    _KGEA_APP_CONFIG['Number_of_Archiver_Tasks'] if 'Number_of_Archiver_Tasks' in _KGEA_APP_CONFIG else 3

Number_of_Validator_Tasks = \
    _KGEA_APP_CONFIG['Number_of_Validator_Tasks'] if 'Number_of_Validator_Tasks' in _KGEA_APP_CONFIG else 3

# TODO: operational parameter dependent configuration
MAX_WAIT = 100  # number of iterations until we stop pushing onto the queue. -1 for unlimited waits
MAX_QUEUE = 0  # amount of queueing until we stop pushing onto the queue. 0 for unlimited queue items

#
# Until we are confident about the KGE File Set publication
# We will post our Translator SmartAPI entries to a local KGE Archive folder
#
# TRANSLATOR_SMARTAPI_REPO = "NCATS-Tangerine/translator-api-registry"
# KGE_SMARTAPI_DIRECTORY = "translator_knowledge_graph_archive"

# TODO: Deployment-dependent constants
TRANSLATOR_SMARTAPI_REPO = "NCATSTranslator/Knowledge_Graph_Exchange_Registry"
KGE_SMARTAPI_DIRECTORY = "kgea/server/tests/output"
BIOLINK_GITHUB_REPO = 'biolink/biolink-model'

PROVIDER_METADATA_TEMPLATE_FILE_PATH = \
    abspath(dirname(__file__) + '/../../../api/kge_provider_metadata.yaml')
FILE_SET_METADATA_TEMPLATE_FILE_PATH = \
    abspath(dirname(__file__) + '/../../../api/kge_fileset_metadata.yaml')
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


def format_and_compression(file_name) -> Tuple[str, Optional[str]]:
    """
    Assumes that format and compression is encoded in the file_name
    as standardized period-delimited parts of the name. This is a
    hacky first version of this method that only recognizes common
    KGX file input format and compression.
    
    :param file_name:
    :return: Tuple of input_format, compression
    """
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


class KgeFileType(bytes, Enum):
    """
    KGE File types Enumerated
    """
    KGX_UNKNOWN = (0, "unknown", "unknown file type")
    KGX_CONTENT_METADATA_FILE = (1, "metadata", "KGX metadata file")
    KGX_DATA_FILE = (2, "data", "KGX data file")
    KGE_NODES = (3, "nodes", "KGX node data file")
    KGE_EDGES = (4, "edges", "KGX edge data file")
    KGE_ARCHIVE = (5, "archive", "KGE data archive")

    def __new__(cls, value, label: str, name: str):
        obj = bytes.__new__(cls, [value])
        obj._value_ = value
        obj.label = label
        obj._name_ = name
        return obj

    @classmethod
    def lookup(cls, label):
        """
        Look up the Enum by label
        :param label:
        """
        pass


class KgeFileSet:
    """
    Class wrapping information about a specific released version of
    KGE Archive managed File Set, effectively 'owned' (hence revisable) by a submitter.
    """
    def __init__(
            self,
            kg_id: str,
            biolink_model_release: str,
            fileset_version: str,
            submitter_name: str,
            submitter_email: str,
            size: int = -1,
            revisions: str = 'creation',
            date_stamp: str = get_default_date_stamp(),
            archive_record: bool = False
    ):
        """
        KgeFileSet constructor

        :param kg_id:
        :param biolink_model_release:
        :param fileset_version:
        :param submitter_name:
        :param submitter_email:
        :param size:
        :param revisions:
        :param date_stamp:
        :param archive_record: True if KgeFileSet record was read in from the Archive, not created in this session
        """

        self.kg_id = kg_id
        self.biolink_model_release = biolink_model_release
        self.fileset_version = fileset_version
        self.submitter_name = submitter_name
        self.submitter_email = submitter_email

        # KGE File Set archive size, may initially be unknown
        self.size = size
        self.revisions = revisions
        self.date_stamp = date_stamp

        # this attribute will track the content metadata file of the given version of KGE File Set
        self.content_metadata: Dict[str, Union[str, bool, List[str]]] = dict()

        # this attribute will track all data files of the given version of KGE File Set
        self.data_files: Dict[str, Dict[str, Any]] = dict()

        # no errors to start
        self.errors: List[str] = list()

        self.status: KgeFileSetStatusCode

        if archive_record:
            # File Set read in from the Archive
            # TODO: how need verify that an archived KGE File Set is truly KGX compliant?
            # self.status = KgeFileSetStatusCode.LOADED
            self.status = KgeFileSetStatusCode.VALIDATED
        else:
            self.status = KgeFileSetStatusCode.CREATED

    def __str__(self):
        return f"File set version '{self.fileset_version}' of graph '{self.kg_id}': {self.data_files}"
    
    def is_validated(self) -> bool:
        """
        Predicate to test if a KGE File Set is fully validated.
        
        :return: True if fileset has given status
        """
        return self.status == KgeFileSetStatusCode.VALIDATED
    
    def report_error(self, msg):
        """
        :param msg: single string message or list of string messages
        :return:
        """
        if isinstance(msg, str):
            msg = [msg]
        logger.error("\n".join(msg))
        lock = threading.Lock()
        with lock:
            self.errors.extend(msg)
            self.status = KgeFileSetStatusCode.ERROR

    def get_fileset_status(self):
        """
        :return: KgeFileSetStatusCode of the KGE File Set
        """
        return self.status

    def get_kg_id(self):
        """
        :return: the knowledge graph identifier string
        """
        return self.kg_id

    def get_biolink_model_release(self):
        """

        :return: Biolink Model release Semantic Version (major.minor.patch)
        """
        return self.biolink_model_release

    def get_fileset_version(self):
        """
        :return: File set version as Semantic Version (major.minor)
        """
        return self.fileset_version

    def get_date_stamp(self):
        """
        Date stamp of file set as ISO format ("YYYY-MM-DD")
        :return:
        """
        return self.date_stamp

    def id(self):
        """
        :return: Versioned file set identifier.
        """
        return self.kg_id + "." + self.fileset_version

    def get_submitter_name(self):
        """
        Submitter of the file set version.
        :return:
        """
        return self.submitter_name

    def get_submitter_email(self):
        """
        Email for the submitter of the file set.
        :return:
        """
        return self.submitter_email

    def get_data_file_object_keys(self) -> Set[str]:
        """
        :return: S3 object keys of file set data files.
        """
        return set(self.data_files.keys())

    def get_data_file_names(self) -> Set[str]:
        """
        :return: String root file names of the files in the file set.
        """
        return set([x["file_name"] for x in self.data_files.values()])

    def get_nodes(self):
        """
        :return:
        """
        node_files_keys = list(filter(
            lambda x: 'nodes/' in x or 'nodes.tsv' in x, self.get_data_file_object_keys()
        ))
        return node_files_keys

    def get_edges(self):
        """

        :return:
        """
        edge_files_keys = list(filter(
            lambda x: 'edges/' in x or 'edges.tsv' in x, self.get_data_file_object_keys()
        ))
        return edge_files_keys

    def get_archive_file_keys(self):
        """
        :return: S3 object keys
        """
        archive_files_keys = list(filter(
            lambda x: '.tar.gz' in x, self.get_data_file_object_keys()
        ))
        return archive_files_keys
    
    def get_property_of_data_file_key(self, object_key: str, attribute: str):
        """
        :param object_key:
        :param attribute:
        
        :return: the value of the property of the file identified by the object key; empty string otherwise
        """
        if object_key in self.data_files and attribute in self.data_files[object_key]:
            return self.data_files[object_key][attribute]
        else:
            return ''

    def contains_file_of_type(self, filetype) -> bool:
        """
        Predicate to test whether or not a KGE fileset contains an input data file of a given type.
        
        :param filetype:
        :return:
        """
        if filetype is KgeFileType.KGE_ARCHIVE:
            return len(self.get_archive_file_keys()) > 0
        elif filetype is KgeFileType.KGE_NODES:
            return len(self.get_nodes()) > 0
        elif filetype is KgeFileType.KGE_EDGES:
            return len(self.get_edges()) > 0
        else:
            return False

    # Note: content metadata file name is already normalized on S3 to 'content_metadata.json'
    def set_content_metadata_file(self, file_name: str, file_size: int, object_key: str, s3_file_url: str):
        """
        Sets the metadata file identification for a KGE File Set
        :param file_name: original name of metadata file.
        :param file_size: size of metadata file (as number of bytes).
        :param object_key:
        :param s3_file_url:
        :return: None
        """
        self.content_metadata = {
            "file_name": file_name,
            "file_size": file_size,
            "object_key": object_key,
            "s3_file_url": s3_file_url,
            "kgx_compliant": False,  # until proven True...
            "errors": []
        }

        # Add size of the metadata file to file set aggregate size
        self.add_file_size(file_size)

        content_metadata_file_text = load_s3_text_file(
            bucket_name=default_s3_bucket,
            object_name=object_key
        )
        # Must load the JSON into a Python dictionary for validation
        metadata_json = json.loads(content_metadata_file_text)

        # OK to do the KGX content metadata JSON validation right away here,
        # since it is much simpler and quicker than general KGX data validation
        errors = validate_content_metadata(metadata_json)

        if not errors:
            self.content_metadata["kgx_compliant"] = True
        else:
            self.content_metadata["errors"] = errors

    def add_data_file(
            self,
            file_type: KgeFileType,
            file_name: str,
            file_size: int,
            object_key: str,
            s3_file_url: str
    ):
        """
        Adds a (meta-)data file to this current of KGE File Set.

        :param file_type: KgeFileType of file being added to the KGE File Set
        :param file_name: to add to the KGE File Set
        :param file_size: number of bytes in the file
        :param object_key: of the file in AWS S3
        :param s3_file_url: current S3 pre-signed data access url

        :return: None
        """

        # Attempt to infer the format and compression of the data file from its filename
        input_format, input_compression = format_and_compression(file_name)

        # TODO: the originally generated data_file record details here,
        #       from initial file registration are more extensive than
        #       a file record later loaded from the Archive. We may need
        #       to review this and somehow record more details in the archive?
        self.data_files[object_key] = {
            "object_key": object_key,
            "file_type": file_type,
            "file_name": file_name,
            "file_size": file_size,
            "input_format": input_format,
            "input_compression": input_compression,
            "s3_file_url": s3_file_url,
            "kgx_compliant": False,  # until proven True...
            "errors": []
        }

        # Add size of this file to file set aggregate size
        self.add_file_size(file_size)

        # We now defer general node/edge graph data validation
        # to the file set self.post_process_file_set() stage

    def add_data_files(self, data_files: Dict[str, Dict[str, Any]]):
        """
        Bulk addition of data files to the KGE File Set may only
        receive an AWS S3 object_key indexed dictionary of file names.
        The files are not further validated for KGX format compliance.
        """
        self.data_files.update(data_files)

    def remove_data_file(self, object_key: str) -> Optional[Dict[str, Any]]:
        """
        Remove a specified data file from the Archive S3 repository.
        :param object_key: of the file to be removed
        :return: details of the removed file
        """
        details: Optional[Dict[str, Any]] = None
        try:
            # TODO: need to be careful here with data file removal in case
            #       the file in question is still being actively validated?
            entry = self.data_files.pop(object_key)
            print(entry)
            # Remove size of this file from file set aggregate size
            self.size = self.size - int(entry['file_size'])

        except KeyError:
            logger.warning(
                "File with object key '" + object_key + "' was not found in " +
                "KGE File Set version '" + self.fileset_version + "'"
            )
        return details

    def load_data_files(self, file_object_keys: List[str]):
        """
        Uploads data files using file object keys.
        :param file_object_keys: a list of object keys of the files to be uploaded.
        :return:
        """
        # TODO: see if there any other information here to be captured or inferred,
        #       e.g. file compression (from file extension), file type, size, etc.
        for object_key in file_object_keys:
            part = object_key.split('/')
            file_name = part[-1]
            self.data_files[object_key] = {
                "file_name": file_name,
                "object_key": object_key,
                # "file_type": file_type,
                # "input_format": input_format,
                # "input_compression": input_compression,
                # "size": -1,  # how can I measure this here?
                # "s3_file_url": s3_file_url,
                # TODO: this could be hazardous to assume True here?
                #       It would be better to track KGX compliance
                #       status somewhere in persisted Archive metadata.
                "kgx_compliant": True,
                # "errors": []
            }

    ##########################################
    # KGE FileSet Publication to the Archive #
    ##########################################
    async def publish(self):
        """
        After a file_set is uploaded, publish file set in the Archive
        after post-processing the file set including generation of the
        file set 'tar.gz' archive for for KGX validation then downloading.
        
        Also sets the file set KgeFileSetStatusCode.

        :return: True if successful; False otherwise
        """
        # Signal that the KGE File Set is in a post-processing state
        self.status = KgeFileSetStatusCode.PROCESSING

        try:
            # Publish a 'file_set.yaml' metadata file to the
            # versioned archive subdirectory containing the KGE File Set
            fileset_metadata_file = self.generate_fileset_metadata_file()
            fileset_metadata_object_key = add_to_s3_repository(
                kg_id=self.kg_id,
                text=fileset_metadata_file,
                file_name=FILE_SET_METADATA_FILE,
                fileset_version=self.fileset_version
            )
            if fileset_metadata_object_key:
                logger.info(f"KgeFileSet.publish(): successfully created object key {fileset_metadata_object_key}")
            else:
                msg = f"publish(): metadata '{FILE_SET_METADATA_FILE}" + \
                      f"' file for KGE File Set version '{self.fileset_version}" + \
                      f"' of knowledge graph '{self.kg_id}" + \
                      "' not successfully posted to the Archive?"
                self.report_error(msg)
                return
            
        except Exception as exception:
            msg = f"publish(): {self.kg_id} {self.fileset_version} {str(exception)}"
            self.report_error(msg)
            return

        try:
            archiver: KgeArchiver = KgeArchiver.get_archiver()
            archiver.create_workers(1)  # add worker capacity
            
            # Assemble a standard KGX Fileset tar.gz archive, with computed SHA1 hash sum
            await archiver.process(self)
        
        except TimeoutError:
            msg = "publish(): archiver.process() signalled TimeoutError"
            self.report_error(msg)
        
        except Exception as error:
            msg = f"publish(): {str(error)}"
            self.report_error(msg)
            
    async def confirm_kgx_data_file_set_validation(self):
        """
        Confirms KGX validation of a file set.
        :return:
        """
        # check if any errors were returned by KGX Validation
        errors: List = []
        for data_file in self.data_files.values():
            lock = threading.Lock()
            with lock:
                if not data_file["kgx_compliant"]:
                    msg = data_file["errors"]
                    if isinstance(msg, str):
                        msg = [msg]
                    errors.extend(msg)

        if not self.content_metadata["kgx_compliant"]:
            errors.append(self.content_metadata["errors"])

        if errors:
            self.report_error(errors)

        return errors

    def generate_fileset_metadata_file(self) -> str:
        """
        Generates the fileset metadata file using a template.
        :return: Populated fileset metadata YAML contents (as a string)
        """
        self.revisions = 'Creation'
        # TODO: Maybe also add in the inventory of files here?
        files = ""
        for entry in self.data_files.values():
            files += "- " + entry["file_name"]+"\n"
        try:
            fileset_metadata_yaml = _populate_template(
                host=site_hostname,
                filename=FILE_SET_METADATA_TEMPLATE_FILE_PATH,
                kg_id=self.kg_id,
                biolink_model_release=self.biolink_model_release,
                fileset_version=self.fileset_version,
                date_stamp=self.date_stamp,
                submitter_name=self.submitter_name,
                submitter_email=self.submitter_email,
                size=self.size,
                revisions=self.revisions,
                files=files
            )
        except Exception as exception:
            logger.error(
                f"generate_fileset_metadata_file(): {self.kg_id} {self.fileset_version} {str(exception)}"
            )
            raise exception

        return fileset_metadata_yaml

    def get_metadata(self) -> KgeFileSetMetadata:
        """
        :return: KGE File Set metadata (output) object of this KgeFileSet.
        """
        fileset_metadata: KgeFileSetMetadata = \
            KgeFileSetMetadata(
                biolink_model_release=self.biolink_model_release,
                fileset_version=self.fileset_version,
                date_stamp=date.fromisoformat(self.date_stamp),
                submitter_name=self.submitter_name,
                submitter_email=self.submitter_email,
                status=self.status,
                size=self.size/1024**2  # aggregated file size in megabytes
            )

        file_set: List[KgeFile] = [
            KgeFile(
                original_name=name,
                # TODO: populate with more complete file_set information here
                # assigned_name="nodes.tsv",
                # file_type="Nodes",  # can use KgeFileType(3) indexed enum
                # file_size=100,  # megabytes
                # kgx_compliance_status="Validated",
                # errors=list()
            )
            for name in self.get_data_file_names()
        ]
        fileset_metadata.files = file_set

        # load the content_metadata JSON file contents here
        fileset_metadata.content = None

        return fileset_metadata

    def add_file_size(self, file_size: int):
        """
        Add new file_size to aggregate total of file sizes for the file set.
        :param file_size:
        :return:
        """
        self.size += file_size


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

        # "fileset_version",  # don't store versions here anymore (rather, in the KGEFileSet)

        "kg_size",
        "translator_component",
        "translator_team",

        # 'submitter_name'  and 'submitter_email' here refers to the individual
        # who originally registers the KGE Knowledge Graph and associated metadata
        "submitter_name",
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
        #                 str,       # fileset_version's are the keys
        #                 List[str]  # List of S3 object_name paths for files associated with a given version
        #             ]
        #         ]
        #     ]
        # ]
        self.kg_id = kwargs.pop("kg_id", None)
        if not self.kg_id:
            raise RuntimeError("KgeKnowledgeGraph() needs a non-null 'kg_id'!")

        # if provided, the fileset_version is simply designates
        # the 'latest' file set of the given Knowledge Graph
        fileset_version = kwargs.pop("fileset_version", None)
        if fileset_version:
            file_set_location = kwargs.pop("file_set_location", None)
            if not file_set_location:
                raise RuntimeError("KgeKnowledgeGraph() explicit 'fileset_version' needs a 'file_set_location'?!")

        # load other parameters other than kg_id  and version-specific metadata
        self.parameter: Dict = dict()
        for key, value in kwargs.items():
            if key not in self._expected_provider_metadata:
                logger.warning("Unexpected KgeKnowledgeGraph parameter '"+str(key)+"'... ignored!")
                continue
            self.parameter[key] = self.sanitize(key, value)

        # File Set Versions - none added upon KG creation
        self._file_set_versions: Dict[str, KgeFileSet] = dict()
        self._provider_metadata_object_key: Optional[str] = None

    _name_filter_table = None

    _spregex = re.compile(r'\s+')

    _indent = " "*4

    @staticmethod
    def sanitize(key, value):
        """
        This function fixes the text of specific values of the
        Knowledge Graph metadata to be YAML friendly

        :param key: yaml key field
        :param value: text value to be fixed (if necessary)
        :return:
        """
        if key == "kg_description":
            # Sanity check: remove carriage returns
            value = value.replace("\r", "")
            value = value.replace("\n", "\n"+" "*4)
            # Fix both ends
            value = value.strip()
            value = " "*4 + value
        return value

    @classmethod
    def _name_filter(cls):
        if not cls._name_filter_table:
            delete_dict = {sp_character: '' for sp_character in punctuation}
            # make exception for hyphen and period: keep/convert to hyphen
            delete_dict['-'] = '-'
            delete_dict['.'] = '-'
            cls._name_filter_table = str.maketrans(delete_dict)
        return cls._name_filter_table

    @classmethod
    def normalize_name(cls, kg_name: str) -> str:
        """
        Normalize a user name to knowledge graph identifier name

        :param kg_name: user provided knowledge name
        :return: normalized knowledge graph identifier name

        """
        # TODO: need to review graph name normalization and indexing
        #       against various internal graph use cases, e.g. lookup
        #       and need to be robust to user typos (e.g. extra blank spaces?
        #       invalid characters?). Maybe convert to regex cleanup?
        # all lower case
        kg_id = kg_name.lower()

        # filter out all punctuation characters
        kg_id = kg_id.translate(cls._name_filter())

        # just clean up the occasional double space typo
        # (won't fully clean up a series of spaces)
        kg_id = cls._spregex.sub("-", kg_id)

        return kg_id

    def set_provider_metadata_object_key(self, object_key: Optional[str] = None):
        """

        :param object_key:
        :return:
        """
        self._provider_metadata_object_key = object_key

    def get_provider_metadata_object_key(self):
        """

        :return:
        """
        return self._provider_metadata_object_key

    def publish_provider_metadata(self):
        """

        :return:
        """
        logger.info("Publishing knowledge graph '" + self.kg_id + "' to the Archive")
        provider_metadata_file = self.generate_provider_metadata_file()
        # no fileset_version given since the provider metadata is global to Knowledge Graph
        object_key = add_to_s3_repository(
            kg_id=self.kg_id,
            text=provider_metadata_file,
            file_name=PROVIDER_METADATA_FILE
        )
        if object_key:
            self.set_provider_metadata_object_key(object_key)
        else:
            self.set_provider_metadata_object_key()
            logger.warning(
                "publish_file_set(): " + PROVIDER_METADATA_FILE +
                " for Knowledge Graph '" + self.kg_id +
                "' not successfully added to KGE Archive storage?"
            )
        return self.get_provider_metadata_object_key()

    def get_name(self) -> str:
        """

        :return:
        """
        return self.parameter.setdefault("kg_name", self.kg_id)

    def get_file_set(self, fileset_version: str) -> Optional[KgeFileSet]:
        """
        :return: KgeFileSet entry tracking for data files in the KGE File Set
        """
        if fileset_version not in self._file_set_versions:
            logger.warning("KgeKnowledgeGraph.get_file_set(): KGE File Set version '"
                           + fileset_version + "' unknown for Knowledge Graph '" + self.kg_id + "'?")
            return None

        return self._file_set_versions[fileset_version]

    # KGE File Set Translator SmartAPI parameters (March 2021 release):
    # - kg_id: KGE Archive generated identifier assigned to a given knowledge graph submission (and used as S3 folder)
    # - translator_component - Translator component associated with the knowledge graph (e.g. KP, ARA or SRI)
    # - translator_team - specific Translator team (affiliation) contributing the file set, e.g. Clinical Data Provider
    # - submitter_name - name of submitter of the KGE file set
    # - submitter_email - contact email of the submitter
    # - kg_name: human readable name of the knowledge graph
    # - kg_description: detailed description of knowledge graph (may be multi-lined with '\n')
    # - license_name - Open Source license name, e.g. MIT, Apache 2.0, etc.
    # - license_url - web site link to project license
    # - terms_of_service - specifically relating to the project, beyond the licensing
    def generate_provider_metadata_file(self) -> str:
        """

        :return:
        """
        return _populate_template(
            filename=PROVIDER_METADATA_TEMPLATE_FILE_PATH,
            host=site_hostname, kg_id=self.kg_id, **self.parameter
        )

    def generate_translator_registry_entry(self) -> str:
        """

        :return:
        """
        return _populate_template(
            filename=TRANSLATOR_SMARTAPI_TEMPLATE_FILE_PATH,
            host=site_hostname, kg_id=self.kg_id, **self.parameter
        )

    def get_version_names(self) -> List[str]:
        """

        :return:
        """
        return list(self._file_set_versions.keys())

    def load_file_set_versions(
            self,
            versions: Dict[
                str,  # fileset_version's of versioned KGE File Sets for a kg
                Dict[
                    str,  # tags 'metadata' and 'file_object_keys'
                    Union[
                        str,  # 'metadata' field value: 'file set' specific text file blob from S3
                        List[str]  # list of 'file_object_keys' in a given KGE File Set
                    ]
                ]
            ]
    ):
        """

        :param versions:
        :return:
        """
        for fileset_version, entry in versions.items():
            file_set: KgeFileSet
            if 'metadata' in entry:
                file_set = self.load_fileset_metadata(entry['metadata'])
            else:
                file_set = KgeFileSet(
                                self.kg_id,
                                biolink_model_release='',
                                fileset_version=fileset_version,
                                date_stamp=get_default_date_stamp(),
                                submitter_name=self.parameter.setdefault('submitter_name', ''),
                                submitter_email=self.parameter.setdefault('submitter_email', ''),
                                archive_record=True
                            )
            file_set.load_data_files(entry['file_object_keys'])

    def add_file_set(self, fileset_version: str, file_set: KgeFileSet):
        """

        :param fileset_version:
        :param file_set:
        :return:
        """
        self._file_set_versions[fileset_version] = file_set

    def load_fileset_metadata(self, metadata_text: str) -> KgeFileSet:
        """

        :param metadata_text:
        :return:
        """

        # Assumed to be a YAML string to be parsed into a Python dictionary
        mf = StringIO(metadata_text)
        md_raw = yaml.load(mf, Loader=Loader)
        md = dict(md_raw)

        # id: "disney_small_world_graph" ## == kg_id
        if self.kg_id != md.setdefault('id', ''):
            raise RuntimeError(
                "load_archive_entry(): archive folder kg_id '" + self.kg_id +
                " != id in " + FILE_SET_METADATA_FILE + "?"
            )

        # biolink_model_release: "2.0.2"
        biolink_model_release = md.setdefault('biolink_model_release', 'latest')

        # fileset_version: "1.0"
        fileset_version = md.setdefault('fileset_version', 'latest')

        # date_stamp: "1964-04-22"
        date_stamp = md.setdefault('date_stamp', get_default_date_stamp())

        # revisions: >-
        #   ${revisions}
        revisions = md.setdefault('revisions', '')

        submitter: Dict = md.setdefault('submitter', {})
        if submitter:
            # submitter_name:
            #   name: "${submitter_name}"
            submitter_name = submitter.setdefault('name', '')

            #   email: "${submitter_email}"
            submitter_email = submitter.setdefault('email', '')
        else:
            submitter_name = submitter_email = ""

        # size: "10000" # megabytes
        size = md.setdefault('size', -1)

        # Probably don't need this field value
        # access: "https://kge.starinformatics.ca/disney_small_world_graph/1964-04-22"
        # access = md.setdefault('access', '')

        # Capture the file set metadata...
        file_set = KgeFileSet(
            self.kg_id,
            biolink_model_release=biolink_model_release,
            fileset_version=fileset_version,
            date_stamp=date_stamp,
            submitter_name=submitter_name,
            submitter_email=submitter_email,
            size=size,
            revisions=revisions,
            archive_record=True
        )

        # ...add it to the knowledge graph...
        self.add_file_set(fileset_version, file_set)

        # then return it for further processing
        return file_set

    # # Listings Approach for getting KGE File Metadata  - DEPRECATED FROM THE GENERAL CATALOG?
    # # - Introspect on Bucket
    # # - Create URL per Item Listing
    # # - Send Back URL with Dictionary
    # # OK in case with multiple files (alternative would be, archives?). A bit redundant with just one file.
    # # TODO: convert into redirect approach with cross-origin scripting?
    # file_set_location, _ = with_version(func=get_object_location, version=self.fileset_version)(self.kg_id)
    # kg_files = object_keys_in_location(
    #     bucket_name=default_s3_bucket,
    #     object_location=file_set_location
    # )
    # pattern = Template('($FILES_LOCATION[0-9]+\/)').substitute(FILES_LOCATION=file_set_location)
    # kg_listing = [content_location for content_location in kg_files if re.match(pattern, content_location)]
    # kg_urls = dict(
    #     map(
    #         lambda kg_file: [
    #             Path(kg_file).stem,
    #             create_presigned_url(default_s3_bucket, kg_file)
    #         ],
    #         kg_listing))
    # # logger.info('access urls %s, KGs: %s', kg_urls, kg_listing)
    def get_metadata(self, fileset_version: str) -> KgeMetadata:
        """

        :param fileset_version:
        :return:
        """
        provider_metadata: KgeProviderMetadata = \
            KgeProviderMetadata(
                kg_id=self.kg_id,
                kg_name=self.get_name(),
                kg_description=self.parameter["kg_description"],
                translator_component=self.parameter["translator_component"],
                translator_team=self.parameter["translator_team"],
                submitter_name=self.parameter["submitter_name"],
                submitter_email=self.parameter["submitter_email"],
                license_name=self.parameter["license_name"],
                license_url=self.parameter["license_url"],
                terms_of_service=self.parameter["terms_of_service"]
            )

        fileset_metadata: Optional[KgeFileSetMetadata] = None

        fileset: Optional[KgeFileSet] = self.get_file_set(fileset_version)
        if fileset:
            fileset_metadata = fileset.get_metadata()
        else:
            logger.warning("KGE File Set version '"+fileset_version+"' does not exist for graph '"+self.kg_id+"'")

        metadata = KgeMetadata(provider=provider_metadata, fileset=fileset_metadata)

        return metadata


class KnowledgeGraphCatalog:
    """
    Knowledge Graph Exchange (KGE) In Memory Catalog to manage compilation,
     validation and user access of releases of KGX File Sets of Knowledge Graphs
    """
    _the_catalog = None

    def __init__(self):
        # Catalog keys are kg_id's, entries are a Python dictionary of kg_id metadata including
        # name, KGE File Set metadata and a list of versions with associated file sets
        self._kge_knowledge_graph_catalog: Dict[str, KgeKnowledgeGraph] = dict()

        # Initialize catalog with the metadata of all the existing KGE Archive (AWS S3 stored) KGE File Sets
        # archive_contents keys are the kg_id's, entries are the rest of the KGE File Set metadata
        archive_contents: Dict = get_archive_contents(bucket_name=default_s3_bucket)
        for kg_id, entry in archive_contents.items():
            if self.is_complete_kg(kg_id, entry):
                self.load_archive_entry(kg_id=kg_id, entry=entry)

    @staticmethod
    def is_complete_kg(kg_id, entry) -> bool:
        """
        Verifies that an S3 KG entry (and all its file sets) are valid
        and complete for use by the front end application.

        :param kg_id:
        :param entry:
        :return:
        """
        if not (kg_id and entry):
            return False
    
        return True
    
    @classmethod
    def catalog(cls):
        """
        :return: singleton of KnowledgeGraphCatalog
        """
        if not cls._the_catalog:
            KnowledgeGraphCatalog._the_catalog = KnowledgeGraphCatalog()

        return KnowledgeGraphCatalog._the_catalog

    def load_archive_entry(
            self,
            kg_id: str,
            entry: Dict[
                str,  # tags 'metadata' and 'versions'
                Union[
                    str,  # 'metadata' field value: kg specific 'provider' text file blob from S3
                    Dict[  # 'versions' field value
                        str,  # fileset_version's of versioned KGE File Sets for a kg
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
         for indexing in the KnowledgeGraphCatalog
        """
        if not (
            'metadata' in entry and
            self.load_provider_metadata(kg_id=kg_id, metadata_text=entry['metadata'])
        ):
            # provider.yaml metadata was not loaded, then, ignore this entry and return...
            logger.warning(
                "load_archive_entry(): no 'metadata' loaded from archive... ignoring knowledge graph '"+kg_id+"'?"
            )
            return

        if 'versions' in entry:
            knowledge_graph: KgeKnowledgeGraph = self.get_knowledge_graph(kg_id)
            knowledge_graph.load_file_set_versions(versions=entry['versions'])

    def load_provider_metadata(self, kg_id, metadata_text: str) -> bool:
        """
        Metadata assumed to be a YAML string to be parsed into a Python dictionary
        :param kg_id:
        :param metadata_text:
        :return:
        """
        if not metadata_text:
            return False
        
        mf = StringIO(metadata_text)
        try:
            md_raw = yaml.load(mf, Loader=Loader)
        except (ScannerError, TypeError):
            logger.warning("Ignoring improperly formed provider metadata YAML file: "+metadata_text)
            return False
        
        md = dict(md_raw)

        # id: "disney_small_world_graph" ## == kg_id
        if kg_id != md.setdefault('id', ''):
            logger.warning(
                "load_archive_entry(): archive folder kg_id '" + kg_id +
                " != id in "+PROVIDER_METADATA_FILE+"?"
            )
            return False

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
            submitter_name = smd.setdefault('name', 'unknown')
            submitter_email = smd.setdefault('email', 'unknown')
        else:
            submitter_name = submitter_email = 'unknown'

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
            submitter_name=submitter_name,
            submitter_email=submitter_email,
            license_name=license_name,
            license_url=license_url,
            terms_of_service=terms_of_service
        )

        return True

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
            fileset_version: str,
            file_type: KgeFileType,
            file_name: str,
            file_size: int,
            object_key: str,
            s3_file_url: str
    ):
        """
        This method adds the given input file to a local catalog of recently
        updated files, within which files formats are asynchronously validated
        to KGX compliance, and the entire file set assessed for completeness.
        An exception is raise if there is an error.

        :param kg_id: identifier of the KGE Archive managed Knowledge Graph of interest
        :param fileset_version: version of interest of the KGE File Set associated with the Knowledge Graph
        :param file_type: KgeFileType of the file being added
        :param file_name: name of the file
        :param file_size: size of the file (number of bytes)
        :param object_key: AWS S3 object key of the file
        :param s3_file_url: currently active pre-signed url to access the file
        :return: None
        """
        knowledge_graph = self.get_knowledge_graph(kg_id)

        if not knowledge_graph:
            raise RuntimeError("KGE File Set '" + kg_id + "' is unknown?")
        else:
            # Found a matching KGE Knowledge Graph?
            file_set = knowledge_graph.get_file_set(fileset_version=fileset_version)
            # Add the current (meta-)data file to the KGE File Set
            # associated with this fileset_version of the graph.
            if file_type in [KgeFileType.KGX_DATA_FILE, KgeFileType.KGE_ARCHIVE]:
                file_set.add_data_file(
                    object_key=object_key,
                    file_type=file_type,
                    file_name=file_name,
                    file_size=file_size,
                    s3_file_url=s3_file_url
                )

            elif file_type == KgeFileType.KGX_CONTENT_METADATA_FILE:
                file_set.set_content_metadata_file(
                    file_name=file_name,
                    file_size=file_size,
                    object_key=object_key,
                    s3_file_url=s3_file_url
                )
            else:
                raise RuntimeError("Unknown KGE File Set type?")

    def get_kg_entries(self) -> Dict[str,  Dict[str, Union[str, List[str]]]]:
        """
        Get KGE Knowledge Graph Entries.
        
        :return: dictionary catalog of knowledge graphs and their validated file set versions.
        """
        # TODO: see KgeFileSetEntry schema in the ~/kgea/api/kgea_api.yaml
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

                # We only want to show graphs that either satisfy the existence of a filetype,
                # or a certain completion code. We do this now.
                versions = knowledge_graph.get_version_names()
                filtered_versions = [
                    version for version in versions if knowledge_graph.get_file_set(version).is_validated()
                ]
                catalog[kg_id] = dict()
                catalog[kg_id]['name'] = knowledge_graph.get_name()
                catalog[kg_id]['versions'] = filtered_versions

        return catalog


# TODO
@prepare_test
def test_check_kgx_compliance():
    return True


# TODO
@prepare_test
def test_get_catalog_entries():
    print("\ntest_get_catalog_entries() test output:\n", file=stderr)
    catalog = KnowledgeGraphCatalog.catalog().get_kg_entries()
    print(json.dumps(catalog, indent=4, sort_keys=True), file=stderr)
    return True


_TEST_TSE_PARAMETERS = dict(
    host=site_hostname,
    kg_id="disney_small_world_graph",
    kg_name="Disneyland Small World Graph",
    kg_description="""Voyage along the Seven Seaways canal and behold a cast of
    almost 300 Audio-Animatronics dolls representing children
    from every corner of the globe as they sing the classic
    anthem to world peace—in their native languages.""",
    fileset_version="1964-04-22",
    translator_component="KP",
    translator_team="Disney Knowledge Provider",
    submitter_name="Mickey Mouse",
    submitter_email="mickey.mouse@disneyland.disney.go.com",
    license_name="Artistic 2.0",
    license_url="https://opensource.org/licenses/Artistic-2.0",
    terms_of_service="https://disneyland.disney.go.com/en-ca/terms-conditions/"
)
_TEST_TPMF = 'empty'
_TEST_TFMF = 'empty'
_TEST_TRE = 'empty'


def test_kg_id_normalization():
    name1 = 'A sample name with spaces'
    kg_id1 = KgeKnowledgeGraph.normalize_name(name1)
    assert kg_id1 == 'a-sample-name-with-spaces'

    name2 = 'Cr@%y   and $lick    NAME.'
    kg_id2 = KgeKnowledgeGraph.normalize_name(name2)
    assert kg_id2 == 'cry-and-lick-name'


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


def prepare_test_file_set(fileset_version: str = "1.0") -> KgeFileSet:
    """

    :param fileset_version:
    :return:
    """
    kg_id = "disney_small_world_graph"
    date_stamp = "1964-04-22"

    file_set = KgeFileSet(
        kg_id=kg_id,
        biolink_model_release="2.0.2",
        fileset_version=fileset_version,
        date_stamp=date_stamp,
        submitter_name="Mickey Mouse",
        submitter_email="mickey.mouse@disneyland.disney.go.com"
    )
    file_set_location, _ = with_version(func=get_object_location, version=fileset_version)(kg_id)

    test_file1 = tempfile.NamedTemporaryFile()
    test_file1.write(bytes(random_alpha_string(), "UTF-8"))
    test_file1.seek(0)
    size = test_file1.tell()
    file_name = 'MickeyMouseFanClub_nodes.tsv'
    object_key = get_object_key(file_set_location, file_name)
    key = upload_file(
        bucket=default_s3_bucket,
        object_key=object_key,
        source=test_file1
    )
    file_set.add_data_file(
        object_key=key,
        file_type=KgeFileType.KGX_DATA_FILE,
        file_name=file_name,
        file_size=size,
        s3_file_url=''
    )
    test_file1.close()

    test_file2 = tempfile.NamedTemporaryFile()
    test_file2.write(bytes(random_alpha_string(), "UTF-8"))
    test_file2.seek(0)
    size = test_file2.tell()
    file_name = 'MinnieMouseFanClub_edges.tsv'
    object_key = get_object_key(file_set_location, file_name)
    key = upload_file(
        bucket=default_s3_bucket,
        object_key=object_key,
        source=test_file2
    )
    file_set.add_data_file(
        object_key=key,
        file_type=KgeFileType.KGX_DATA_FILE,
        file_name=file_name,
        file_size=size,
        s3_file_url=''
    )
    test_file2.close()

    with tempfile.TemporaryDirectory() as tempdir:

        # homogenize the names so these files don't clutter the test folder when uploaded
        test_name = {
            'nodes': 'test_nodes.tsv',
            'edges': 'test_edges.tsv',
            'archive': 'test_archive.tar.gz'
        }

        test_file3 = tempfile.NamedTemporaryFile(suffix='_nodes.tsv', delete=False)
        test_file3.write(bytes(random_alpha_string(), "UTF-8"))
        test_file3.close()

        test_file4 = tempfile.NamedTemporaryFile(suffix='_edges.tsv', delete=False)
        test_file4.write(bytes(random_alpha_string(), "UTF-8"))
        test_file4.close()

        import tarfile
        tar_file_name = random_alpha_string() + '.tar.gz'
        with tarfile.open(name=tempdir+'/'+tar_file_name, mode='w:gz') as test_tarfile:
            # OR use os.path.basename()
            test_tarfile.add(test_file3.name, arcname=test_name['nodes'])
            test_tarfile.add(test_file4.name, arcname=test_name['edges'])
        with open(tempdir+'/'+tar_file_name, 'rb') as test_tarfile1:
            object_key = get_object_key(file_set_location, test_name['archive'])
            key = upload_file(
                bucket=default_s3_bucket,
                object_key=object_key,
                source=test_tarfile1
            )
            file_set.add_data_file(
                object_key=key,
                file_type=KgeFileType.KGX_DATA_FILE,
                file_name=test_name['archive'],
                file_size=999,
                s3_file_url=''
            )

    return file_set


@prepare_test
def test_create_fileset_metadata_file():
    global _TEST_TFMF
    print("\ntest_create_fileset_metadata_entry() test output:\n", file=stderr)

    fs = prepare_test_file_set()

    _TEST_TFMF = fs.generate_fileset_metadata_file()

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


def add_to_s3_repository(
        kg_id: str,
        text: str,
        file_name: str,
        fileset_version: str = ''
) -> str:
    """
    Add a file of specified text content and name,
     to a KGE Archive (possibly versioned) S3 folder.
    :param kg_id: knowledge graph
    :param text: string blob contents of the file.
    :param file_name: of the file.
    :param fileset_version: version (optional)
    :return: str object key of the uploaded file
    """

    if text:
        if fileset_version:
            file_set_location, _ = with_version(func=get_object_location, version=fileset_version)(kg_id)
        else:
            file_set_location = get_object_location(kg_id)
        data_bytes = text.encode('utf-8')
        object_key = get_object_key(file_set_location, file_name)
        upload_file(
            bucket=default_s3_bucket,
            object_key=object_key,
            source=BytesIO(data_bytes)
        )
        return object_key
    else:
        logger.warning("add_to_s3_repository(): Empty text string argument? Can't archive a vacuum!")
        return ''


def get_github_token() -> Optional[str]:
    """
    
    :return:
    """
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
    """
    
    :param kg_id:
    :param text:
    :param repo_path:
    :param target_directory:
    :return:
    """
    status: bool = False

    gh_token = get_github_token()

    logger.info("Calling add_to_github(gh_token: '"+str(gh_token)+"')")

    if gh_token and text:

        logger.info(
            "\n\t### api_specification = '''\n" + text[:60] + "...\n'''\n" +
            "\t### repo_path = '" + str(repo_path) + "'\n" +
            "\t### target_directory = '" + str(target_directory) + "'"
        )

        if text and repo_path and target_directory:

            entry_path = target_directory+"/"+kg_id + ".yaml"

            logger.info("\t### gh_url = '" + str(entry_path) + "'")

            g = Github(gh_token)

            content_file = repo = None

            try:
                # TODO: should I be explicit somewhere here
                #       about the repo branch being used? How?
                repo = g.get_repo(repo_path)
                content_file = repo.get_contents(entry_path)
            except BadCredentialsException as bce:
                logger.error(str(bce))
                repo = None
            except UnknownObjectException:
                content_file = None

            if not repo:
                logger.error("Could not connect to Github repo: "+repo_path)
                return False

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
    outcome: str = add_to_s3_repository(
        kg_id="kge_test_provider_metadata_file",
        text=_TEST_TPMF,
        file_name="test_provider_metadata_file",
        fileset_version="100.0"
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


def get_github_releases(repo_path: str = ''):
    """
    
    :param repo_path:
    :return:
    """
    if not repo_path:
        logger.error("get_github_releases(): repo_path argument is empty?")
        return []

    gh_token = get_github_token()
    if not gh_token:
        logger.error("get_github_releases(): need a non-null gh_token to access Github!")
        return []

    logger.info("Calling get_github_releases(repo_path: '" + str(repo_path) + "')")

    g = Github(gh_token)

    repo = g.get_repo(repo_path)

    releases = repo.get_releases()

    return [entry.tag_name for entry in releases]


def get_biolink_model_releases():
    """
    
    :return:
    """
    all_releases = get_github_releases(repo_path=BIOLINK_GITHUB_REPO)
    filtered_releases = list()
    for r in all_releases:
        if r.startswith('v'):
            continue
        major, minor, patch = r.split('.')
        if major == '1' and int(minor) < 8:
            continue
        if major == '1' and minor == '8' and patch != '2':
            continue
        filtered_releases.append(r)

    return filtered_releases


@prepare_test
def test_get_biolink_releases():
    """
    
    :return:
    """
    releases: List = get_biolink_model_releases()
    assert('2.0.2' in releases)
    print("Test access to Biolink releases:")
    for release in releases:
        print(f"\t{release}")


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
        "Calling clean_tests()",
        file=stderr
    )

    if gh_token and repo_path and target_directory:

        entry_path = target_directory + "/" + kg_id + ".yaml"

        g = Github(gh_token)
        repo = g.get_repo(repo_path)

        contents = repo.get_contents(entry_path)
        repo.delete_file(contents.path, "Remove test entry = '" + entry_path + "'", contents.sha)

#########################################################################
# KGX File Set Validation Code ##########################################
#########################################################################


"""
Knowledge Graph eXchange (KGX) tool kit validation of
Knowledge Graph Exchange (KGE) File Sets located on AWS S3
"""

# KGX Content Metadata Validator is a simply JSON Schema validation operation
CONTENT_METADATA_SCHEMA_FILE = abspath(dirname(__file__) + '/content_metadata.schema.json')
with open(CONTENT_METADATA_SCHEMA_FILE, mode='r', encoding='utf-8') as cms:
    CONTENT_METADATA_SCHEMA = json.load(cms)


# This first iteration only validates the JSON structure and property tags against the JSON schema
# TODO: perhaps should also check the existence of Biolink
#       node categories and predicates (using the Biolink Model Toolkit)?
def validate_content_metadata(content_metadata_file) -> List:
    """
    
    :param content_metadata_file:
    :return:
    """
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


def get_default_model_version():
    """
    
    :return:
    """
    semver = Validator.get_default_model_version()
    return semver.split('.')


class ProgressMonitor:
    """
    ProgressMonitor
    """
    
    # TODO: how do we best track the validation here?
    #       We start by simply counting the nodes and edges
    #       and periodically reporting to debug logger.
    def __init__(self):
        self._node_count = 0
        self._edge_count = 0

    def __call__(self, entity_type: GraphEntityType, rec: List):
        logger.setLevel(logging.DEBUG)
        if entity_type == GraphEntityType.EDGE:
            self._edge_count += 1
            if self._edge_count % 100000 == 0:
                logger.info(str(self._edge_count) + " edges processed so far...")
        elif entity_type == GraphEntityType.NODE:
            self._node_count += 1
            if self._node_count % 10000 == 0:
                logger.info(str(self._node_count) + " nodes processed so far...")
        else:
            logger.warning("Unexpected GraphEntityType: " + str(entity_type))


class KgeArchiver:
    """
    KGE Archive building wrapper.
    """

    def __init__(self, max_tasks=Number_of_Archiver_Tasks, max_queue=MAX_QUEUE, max_wait=MAX_WAIT):
        """
        Constructor for a single archiver task wrapper.
        """
        self._archiver_queue: Queue = Queue(maxsize=max_queue)
        self._archiver_worker: List[Task] = list()

        self.max_tasks: int = max_tasks
        self.max_wait: int = max_wait

    _the_archiver = None
    
    @classmethod
    def get_archiver(cls):
        """

        :return: singleton KgeArchiver
        """
        if not cls._the_archiver:
            cls._the_archiver = KgeArchiver()
        return cls._the_archiver
    
    @staticmethod
    def aggregate_to_archive(file_set: KgeFileSet, data_type: str, file_object_keys, match_function=lambda x: True):
        """
        Wraps file aggregator for a given file type.
        
        :param file_set:
        :param data_type:
        :param file_object_keys:
        :param match_function:
        """

        # TODO: what do we do if we want to aggregate more than just KGX TSV files?
        data_type += ".tsv"
        
        key_list = "\n\t".join(file_object_keys)
        logger.debug(f"Aggregating {data_type} files in File Set '{file_set.id()}'\n"
                     f"\tcontaining object keys:\n\t{key_list}")

        try:
            agg_path: str = aggregate_files(
                target_folder=f"kge-data/{file_set.kg_id}/{file_set.fileset_version}/archive",
                target_name=data_type,
                file_object_keys=file_object_keys,
                match_function=match_function
            )
            logger.debug(f"{data_type} path: {agg_path}")
    
        except Exception as e:
            # Can't be more specific than this 'cuz not sure what errors may be thrown here...
            print_error_trace(f"{data_type} file aggregation failure! " + str(e))
            raise e

        file_set.add_data_file(KgeFileType.KGX_DATA_FILE, data_type, 0, agg_path, '')
    
    @staticmethod
    def copy_to_kge_archive(file_set: KgeFileSet, file_name: str):
        """
        Copy (meta)-data files to appropriate archive directory.
        
        :param file_set:
        :param file_name:
        """
        logger.info(f"Copying over '{file_name}' file, if available:")
        try:
            # Simple exceptional source key case...
            if file_name == "provider.yaml":
                source_key = f"kge-data/{file_set.kg_id}/provider.yaml"
            else:
                source_key = f"kge-data/{file_set.kg_id}/{file_set.fileset_version}/{file_name}"
            
            if object_key_exists(object_key=source_key):
                copy_file(
                    source_key=source_key,
                    target_dir=f"kge-data/{file_set.kg_id}/{file_set.fileset_version}/archive"
                )
            else:
                logger.warning(f"{source_key} not found?")
    
        except Exception as e:
            # Can't be more specific than this 'cuz not sure what errors may be thrown here...
            print_error_trace(f"Failure to copy '{file_name}' file?" + str(e))
            raise e
    
    async def worker(self, task_id=None):
        """

        :param task_id:
        """
        if task_id is None:
            task_id = len(self._archiver_worker)

        while True:
            file_set: KgeFileSet = await self._archiver_queue.get()

            logger.info(f"KgeArchiver worker {task_id} starting archive of {file_set.id()}")
            
            # perhaps await a second before starting the work,
            # to unblock co-routine responses in the main web application
            await sleep(1)

            # 1. Unpack any uploaded archive(s) where they belong: (JSON) content metadata, nodes and edges
            try:
                logger.debug(
                    f"KgeArchiver task {task_id} unpacking incoming tar.gz archives: " +
                    f"{file_set.get_archive_file_keys()}")
                
                for archive_file_key in file_set.get_archive_file_keys():
                    
                    archive_filename = file_set.get_property_of_data_file_key(archive_file_key, 'file_name')
                    
                    logger.debug(f"Unpacking archive {archive_filename}")
                    
                    #
                    # RMB: 2021-10-07, we deprecated the RAM-based version of the 'decompress-in-place' operation,
                    # moving instead towards the kge_extract_data_archive.bash harddisk-centric solution
                    #
                    # archive_file_entries = decompress_to_kgx(file_key, archive_location)
                    #
                    archive_file_entries: List[Dict[str, str]] = \
                        extract_data_archive(
                            kg_id=file_set.get_kg_id(),
                            file_set_version=file_set.get_fileset_version(),
                            archive_filename=archive_filename
                        )

                    # Republish the file_set.yaml file to modify the archives in place. This is done as a side-effect
                    # onto S3, before the files are aggregated to the archive, or are copied to the archive.
                    #
                    # ...Remove the archive entry from the KgxFileSet
                    file_set.remove_data_file(archive_file_key)
                    
                    logger.debug(f"Adding {len(archive_file_entries)} files to fileset '{file_set.id()}':")
                    
                    # add the archive's files to the file set
                    for entry in archive_file_entries:
                        # spread the entry across the add_data_file function,
                        # which will take all its values as arguments
                        logger.debug(f"\t{entry['file_name']}")
                        file_set.add_data_file(
                            file_name=entry["file_name"],
                            file_type=KgeFileType(int(entry["file_type"])),
                            file_size=int(entry["file_size"]),
                            object_key=entry["object_key"],
                            s3_file_url=entry["s3_file_url"]
                        )

                    logger.debug("Generating new fileset.yaml metadata file...")
                    
                    # rewrite the new file set file
                    fileset_metadata_file = file_set.generate_fileset_metadata_file()

                    logger.debug("... then, adding the fileset.yaml to the KGE S3 repository")
                    
                    # TODO: is it helpful to store this object key somewhere in the KgeFileSet?
                    fileset_metadata_object_key = add_to_s3_repository(
                        kg_id=file_set.kg_id,
                        text=fileset_metadata_file,
                        file_name=FILE_SET_METADATA_FILE,
                        fileset_version=file_set.fileset_version
                    )

            except Exception as e:
                # Can't be more specific than this 'cuz not sure what errors may be thrown here...
                print_error_trace("KgeArchiver.worker(): Error while unpacking archive?: "+str(e))
                raise e

            logger.debug("Aggregating nodes")
            
            # 2. Aggregate each of all nodes and edges each
            #    into their respective files in the archive folder
            self.aggregate_to_archive(file_set, "nodes", file_set.get_nodes())
            self.aggregate_to_archive(file_set, "edges", file_set.get_edges())

            # 3. Copy over metadata files into the archive folder
            self.copy_to_kge_archive(file_set, PROVIDER_METADATA_FILE)
            self.copy_to_kge_archive(file_set, FILE_SET_METADATA_FILE)
            self.copy_to_kge_archive(file_set, CONTENT_METADATA_FILE)

            # 4. Tar and gzip a single <kg_id>.<fileset_version>.tar.gz archive file
            #    containing the aggregated nodes.tsv, edges.tsv, Appending `file_set_root_key`
            #    with 'aggregates/' and 'archive/'  to prevent multiple compress_fileset runs
            #    from compressing the previous compression (so the source of files is distinct
            #    from the target to which it is written)
            logger.debug("Compressing total KGE file set...")
            try:
                s3_archive_key: str = compress_fileset(
                    kg_id=file_set.kg_id,
                    version=file_set.fileset_version
                )
            except Exception as e:
                # Can't be more specific than this 'cuz not sure what errors may be thrown here...
                print_error_trace("File set compression failure! "+str(e))
                raise e

            logger.debug("...File compression completed!")

            # 5. Compute the SHA1 hash sum for the resulting archive file. Hmm... since we are adding the
            #  file_set.yaml file to the archive, it would not really help to embed the hash sum into the fileset
            #  yaml itself, but we can store it in an extra small text file (e.g. sha1.txt?) and read it in during
            #  the catalog loading, for communication back to the user as part of the catalog metadata
            #  (once the archiving and hash generation is completed...)
            logger.debug("Computing SHA1 hash sum...")
            try:
                # NOTE: We have to "disable" compression as smart_open auto-decompresses based off of the format
                # of whatever is being opened. If we let this happen, then the hash function would run over
                # a decompressed buffer; not the compressed file/buffer that we expect our users to use when
                # they download and validate the archive.
                with smart_open.open(s3_archive_key, 'rb', compression='disable') as archive_file_key:
                    sha1sum = sha1_manifest(archive_file_key)
                    sha1sum_value = sha1sum[archive_file_key.name]
                    sha1tsv = f"{file_set.kg_id}_{file_set.fileset_version}.sha1.txt"
                    manifest_object_location = f"kge-data/{file_set.kg_id}/{file_set.fileset_version}/manifest/"
                    sha1_s3_path = f"s3://{default_s3_bucket}/{manifest_object_location}{sha1tsv}"
                    with smart_open.open(sha1_s3_path, 'w') as sha1file:
                        sha1file.write(sha1sum_value)

            except Exception as e:
                # Can't be more specific than this 'cuz not sure what errors may be thrown here...
                print_error_trace("SHA1 hash sum computation failure! "+str(e))
                raise e

            # 6. KGX validation of KGE compliant archive.
            
            # TODO: Debug and/or redesign KGX validation of data files - doesn't yet work properly
            # TODO: need to managed multiple Biolink Model specific KGX validators
            logger.debug(
                f"(Future) KgeArchiver worker {task_id} validation of {file_set.id()} tar.gz archive..."
            )
            # validator: KgxValidator = KnowledgeGraphCatalog.catalog().get_validator()
            # KgxValidator.validate(self)
            
            # Assume that the TAR.GZ archive of the
            # KGE File Set is validated by this point
            file_set.status = KgeFileSetStatusCode.VALIDATED
            
            logger.debug(f"KgeArchiver worker {task_id} finished archiving of {file_set.id()}")

            self._archiver_queue.task_done()

    def create_workers(self, worker_count):
        """
        Initializes Archiver tasks if not yet running
         and less than Number_of_Archiver_Tasks.
        """
        assert(worker_count > -1)

        worker_additions: int = 0
        if worker_count + len(self._archiver_worker) < self.max_tasks:
            worker_additions = worker_count
        elif worker_count + len(self._archiver_worker) >= self.max_tasks:
            # the sum of WC and len of workers could be greater either because len of workers is greater,
            # or both are lesser but the sum of both is greater

            # if the length is already greater then we want to do nothing
            if len(self._archiver_worker) >= self.max_tasks:
                raise Warning('Max Workers')
            else:
                # max out workers up to the limit, which is the number of additions required to make the limit
                worker_additions = self.max_tasks - len(self._archiver_worker)

        for i in range(0, worker_additions):
            self._archiver_worker.append(create_task(self.worker()))

    async def shutdown_workers(self):
        """
        Shut down the background KGE Archive processing.
        :return:
        """
        await self._archiver_queue.join()
        try:
            # Cancel the KGX validation worker tasks
            for worker in self._archiver_worker:
                worker.cancel()

            # Wait until all worker tasks are cancelled.
            await gather(*self._archiver_worker, return_exceptions=True)

        except Exception as exc:
            msg = "KgeArchiver() worker shutdown exception: " + str(exc)
            logger.error(msg)

    async def process(self, file_set: KgeFileSet, wait=10, waits=0, maxwait=MAX_WAIT):
        """
        This method posts a KgeFileSet to the KgeArchiver for processing.

        :param maxwait:
        :param waits:
        :param wait:
        :param file_set: KgeFileSet.
        
        :return: None
        """
        # Post the file set to the KgeArchiver task Queue for processing
        try:
            logger.debug("KgeArchiver.process(): adding '"+file_set.id()+"' to archiver work queue")
            self._archiver_queue.put_nowait(
                file_set
            )
        except QueueFull:
            
            logger.debug("KgeArchiver.process(): work queue is full? Will sleep awhile...")
            await sleep(wait)
            try:
                assert(waits < maxwait)
                waits += 1
                await self.process(file_set, wait, waits, maxwait)
            except (AssertionError, TimeoutError):
                raise TimeoutError
            #
            # it's unclear to me why this
            # try block should finally return 'False'
            #
            # finally:
            #     return False
       
        return True


class KgxValidator:
    """
    KGX Validation wrapper.
    """
    def __init__(self, biolink_model_release: str):
        Validator.set_biolink_model(biolink_model_release)
        self.kgx_data_validator = Validator(progress_monitor=ProgressMonitor())
        self._validation_queue: Queue = Queue()

        # Do I still need a list of task objects here,
        # to handle multiple validations concurrently?
        self.number_of_tasks = Number_of_Validator_Tasks
        self._validation_tasks: List = list()

    # Catalog of Biolink Model version specific validators
    _biolink_validator = dict()
    
    def get_validation_queue(self) -> Queue:
        """
        :return:
        """
        return self._validation_queue

    def get_validation_tasks(self) -> List:
        """
        :return:
        """
        return self._validation_tasks

    # The method should be called at the beginning of KgxValidator processing
    @classmethod
    def get_validator(cls, biolink_model_release: str):
        """
        :param biolink_model_release:
        :return:
        """
        if biolink_model_release in cls._biolink_validator:
            validator = cls._biolink_validator[biolink_model_release]
        else:
            validator = KgxValidator(biolink_model_release)
            cls._biolink_validator[biolink_model_release] = validator

        if validator.number_of_tasks:
            validator.number_of_tasks -= 1
            validator._validation_tasks.append(create_task(validator()))
        return validator
    
    @classmethod
    async def shutdown_tasks(cls):
        """
        Shut down the background validation processing.
        
        :return:
        """
        for validator in cls._biolink_validator.values():
            await validator.get_validation_queue().join()
            try:
                # Cancel the KGX validation worker tasks
                for task in validator.get_validation_tasks():
                    task.cancel()

                # Wait until all worker tasks are cancelled.
                await gather(*validator.get_validation_tasks().values(), return_exceptions=True)

            except Exception as exc:
                msg = "KgxValidator() KGX worker task exception: " + str(exc)
                logger.error(msg)

    @classmethod
    def validate(cls, file_set: KgeFileSet):
        """
        This method posts a KgeFileSet to the KgxValidator for validation.

        :param file_set: KgeFileSet.

        :return: None
        """
        # First, initialize task queue if not running...
        validator = cls.get_validator(file_set.biolink_model_release)

        # ...then, post the file set to the KGX validation task Queue
        try:
            validator._validation_queue.put_nowait(file_set)
        except QueueFull:
            # TODO: retry?
            raise QueueFull

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
            file_type_opt: Optional[KgeFileType] = None
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
                if not file_type_opt:
                    file_type_opt = entry["file_type"]  # this should be a KgeFileType enum value?
                if not input_format:
                    input_format = entry["input_format"]
                if not input_compression:
                    input_compression = entry["input_compression"]

                file_name = entry["file_name"]
                object_key = entry["object_key"]
                s3_file_url = entry["s3_file_url"]

                logger.debug(
                    f"KgxValidator() processing file '{file_name}' '{object_key}' " +
                    f"of type '{file_type_opt.name}', input format '{input_format}' " +
                    f"and with compression '{input_compression}', "
                )

                # The file to be processed should currently be
                # a resource accessible from this S3 authenticated URL?
                input_files.append(s3_file_url)

            ###################################
            # ...then, process them together...
            ###################################
            if file_type_opt == KgeFileType.KGX_DATA_FILE:
                #
                # Run validation of KGX knowledge graph data files here
                #
                validation_errors: List[str] = \
                    await self.validate_file_set(
                        file_set_id=file_set.id(),
                        input_files=input_files,
                        input_format=input_format,
                        input_compression=input_compression
                    )
                if validation_errors:
                    file_set.report_error(validation_errors)

            elif file_type_opt == KgeFileType.KGE_ARCHIVE:
                # TODO: perhaps need more work to properly dissect and
                #       validate a KGX Data archive? Maybe need to extract it
                #       then get the distinct files for processing? Or perhaps,
                #       more direct processing is feasible (with the KGX Transformer?)
                file_set.report_error("KGE Archive validation is not yet implemented?")
            else:
                file_set.report_error(f"WARNING: Unexpected KgeFileType{file_type_opt.name} ... Ignoring?")

            compliance: str = ' not ' if file_set.errors else ' '
            logger.debug(
                f"has finished processing. {str(file_set)} is" +
                compliance + "KGX compliant"
            )

            self._validation_queue.task_done()

    async def validate_file_set(
            self,
            file_set_id: str,
            input_files: List[str],
            input_format: str = 'tsv',
            input_compression: Optional[str] = None
    ) -> List:
        """
        Validates KGX compliance of a specified data file.

        :param file_set_id: name of the file set, generally a composite identifier of the kg_id plus fileset_version?
        :param input_files: list of file path strings pointing to files to be validated (could be a resolvable URL?)
        :param input_format: currently restricted to 'tsv' (its default?) - should be consistent for all input_files
        :param input_compression: currently expected to be 'tar.gz' or 'gz' - should be consistent for all input_files
        :return: (possibly empty) List of errors returned
        """
        logger.setLevel(logging.DEBUG)
        logger.debug(
            "Entering KgxValidator.validate_data_file() with arguments:" +
            "\n\tfile set ID:" + str(file_set_id) +
            "\n\tinput files:" + str(input_files) +
            "\n\tinput format:" + str(input_format) +
            "\n\tinput compression:" + str(input_compression)
        )

        if input_files:
            # The putative KGX 'source' input files are currently sitting
            # at the end of S3 signed URLs for streaming into the validation.

            logger.debug("KgxValidator.validate_data_file(): creating the Transformer...")

            transformer = Transformer(stream=True)

            logger.debug("KgxValidator.validate_data_file(): running the Transformer.transform...")

            transformer.transform(
                input_args={
                    'name': file_set_id,
                    'filename': input_files,
                    'format': input_format,
                    'compression': input_compression
                },
                output_args={
                    # we don't keep the graph in memory...
                    # too RAM costly and not needed later
                    'format': 'null'
                },
                inspector=self.kgx_data_validator
            )

            logger.debug("KgxValidator.validate_data_file(): transform validation completed")

            errors: List[str] = self.kgx_data_validator.get_error_messages()

            if errors:
                n = len(errors)
                n = 9 if n >= 10 else n
                logger.error("Sample of errors seen:\n"+'\n'.join(errors[0:n]))

            logger.debug("KgxValidator.validate_data_file(): Exiting validate_file_set()")

            return errors

        else:
            return ["Missing file name inputs for validation?"]


# This is a simple test of the KgxArchive queue/task.
# It cannot be run with the given test_file_set object
# since the data files don't exist in S3!
def test_stub_archiver() -> bool:
    
    archiver: KgeArchiver = KgeArchiver()
    
    async def archive_test():
        """
        async archive test wrapper
        :return:
        """

        logger.debug("\ntest_stub_archiver() startup of tasks\n")

        fs = prepare_test_file_set("1.0")
        await archiver.process(fs)
        archiver.create_workers(2)

        # fs = test_file_set("1.1")
        # await archiver.process(fs)
        # fs = test_file_set("1.2")
        # await archiver.process(fs)
        # fs = test_file_set("1.3")
        # await archiver.process(fs)

        # # Don't want to finish too quickly...
        # await sleep(30)
        #
        # logger.debug("\ntest_stub_archiver() shutdown now!\n")
        # await archiver.shutdown_workers()
        
    run(archive_test())
    return True


"""
Test Parameters + Decorator
"""
TEST_BUCKET = 'kgea-test-bucket'
TEST_KG_NAME = 'test_kg'
TEST_FILE_DIR = 'kgea/server/test/data/'
TEST_FILE_NAME = 'somedata.csv'

SAMPLE_META_KNOWLEDGE_GRAPH_FILE = abspath(dirname(__file__) + '/sample_meta_knowledge_graph.json')


def test_contents_metadata_validator():
    """
    
    :return:
    """
    print("\ntest_contents_metadata_validator() test output:\n", file=stderr)

    with open(SAMPLE_META_KNOWLEDGE_GRAPH_FILE, mode='r', encoding='utf-8') as smkg:
        mkg_json = json.load(smkg)

    errors: List[str] = validate_content_metadata(mkg_json)

    if errors:
        logger.error("test_contents_metadata_validator() errors: " + str(errors))
    return not errors


# TODO: more complete KGX validator test
def test_kgx_data_validator():
    """
    
    :return:
    """
    print("\ntest_contents_data_validator() test output:\n", file=stderr)

    # with open(SAMPLE_META_KNOWLEDGE_GRAPH_FILE, mode='r', encoding='utf-8') as smkg:
    #     mkg_json = json.load(smkg)

    errors: List[str] = []  # validate_content_metadata(mkg_json)

    if errors:
        logger.error("test_contents_data_validator() errors: " + str(errors))
    return not errors


def run_test(test_func):
    """
    Wrapper to run a test.

    :param test_func:
    :return:
    """
    try:
        start = datetime.now()
        assert (test_func())
        end = datetime.now()
        print(f"{test_func.__name__} passed: {str(end - start)} seconds")
    except Exception as e:
        logger.error(f"{test_func.__name__} failed!")
        logger.error(e)


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

        print("Catalog package module tests")

        # The generate_translator_registry_entry() and add_to_github() methods both work as coded as of 29 March 2021,
        # thus we comment out this test to avoid repeated commits to the KGE repo. The 'clean_tests()' below
        # is thus not currently needed either, since it simply removes the github artifacts from add_to_github().
        # This code can be uncommented if these features need to be tested again in the future
        # test_kg_id_normalization()
        # assert (test_create_provider_metadata_file())
        # assert (test_create_fileset_metadata_file())
        # assert (test_add_to_archive())
        # assert (test_create_translator_registry_entry())
        # assert (test_add_to_github())

        # assert (test_get_catalog_entries())
        #
        # print("all KGE Archive Catalog tests passed")
        #
        print("KgeArchiver unit tests")
        #
        # Just a test of the basic KgeArchiver queue/task
        run_test(test_stub_archiver)
        #
        # print("KgxValidator unit tests")
        #
        # run_test(test_contents_metadata_validator)
        # run_test(test_kgx_data_validator)

        # test_get_biolink_releases()

        print("Catalog package module tests completed?")

    # if CLEAN_TESTS:
    #     clean_tests()
