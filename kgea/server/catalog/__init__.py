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

from typing import Dict, Union, Set, List, Any, Optional, Tuple
from string import Template, punctuation
from datetime import date
from enum import Enum

# TODO: maybe convert Catalog components to Python Dataclasses?
# from dataclasses import dataclass

import re
import threading

from os.path import dirname, abspath
from io import BytesIO, StringIO

from operator import itemgetter

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

from kgx.validator import Validator

from kgea import (
    FILE_SET_METADATA_TEMPLATE_FILE_PATH,
    PROVIDER_METADATA_TEMPLATE_FILE_PATH,
    TRANSLATOR_SMARTAPI_TEMPLATE_FILE_PATH
)
from kgea.config import (
    DEV_MODE,
    get_app_config,
    PROVIDER_METADATA_FILE,
    FILE_SET_METADATA_FILE,
    FILESET_TO_ARCHIVER,
    FILESET_ARCHIVER_STATUS
)
from kgea.server.kgea_session import KgeaSession
from kgea.server.web_services.models import (
    KgeMetadata,
    KgeFileSetStatusCode,
    KgeFile,
    KgeProviderMetadata,
    KgeFileSetMetadata
)

from kgea.server.kgea_file_ops import (
    default_s3_bucket,
    get_default_date_stamp,
    get_object_location,
    get_archive_contents,
    get_object_key,
    with_version,
    load_s3_text_file,
    upload_file
)

import logging
logger = logging.getLogger(__name__)

OVERRIDE = True


# Opaquely access the configuration dictionary
_KGEA_APP_CONFIG = get_app_config()
site_hostname = _KGEA_APP_CONFIG['site_hostname']

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

# Recognized KGX file format extensions
KgxFileExt = "tsv|jsonl"

# KgxFFP == Kgx File Format Pattern
KgxFFP = re.compile(fr"(?P<filext>{KgxFileExt})", flags=re.RegexFlag.IGNORECASE)

# KgxNodeFFP == Kgx Nodes File Format Pattern
KgxNodeFFP = re.compile(fr"(?P<filetype>nodes\.({KgxFileExt}))", flags=re.RegexFlag.IGNORECASE)

# KgxEdgeFFP == Kgx Edges File Format Pattern
KgxEdgeFFP = re.compile(fr"(?P<filetype>edges\.({KgxFileExt}))", flags=re.RegexFlag.IGNORECASE)


def populate_template(filename, **kwargs) -> str:
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
    if not file_name:
        raise RuntimeError("format_and_compression(): empty file_name?")

    part = file_name.split('.')

    input_format = ''
    for w in part:
        m = KgxFFP.match(w)
        if m:
            input_format = m['filext']

    if len(part) > 2 and 'tar' in part[-2]:
        archive = 'tar'
    else:
        archive = None

    if len(part) >= 2 and 'gz' in part[-1]:
        compression = ''
        if archive:
            compression = archive + "."
        compression += 'gz'
    else:
        compression = None

    return input_format, compression


class KgeFileType(Enum):
    """
    KGE File types Enumerated
    """
    UNKNOWN = 0
    CONTENT_METADATA_FILE = 1
    DATA_FILE = 2
    NODES = 3
    EDGES = 4
    ARCHIVE = 5


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
            status: KgeFileSetStatusCode = KgeFileSetStatusCode.CREATED,
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

        # cache subset of files which are 'archive' files  (with their sizes)
        # TODO: need to make sure that the cache is only initialized once or remains 'current'!?!
        self.archive_file_list: List[Tuple[str, str, int]] = list()
        self.archive_s3_object_key: Optional[str] = None

        # no errors to start
        self.errors: List[str] = list()

        self.status: KgeFileSetStatusCode = status

        if archive_record:
            # File Set read in from the Archive
            # TODO: how need verify that an archived KGE File Set is truly KGX compliant?
            # self.status = KgeFileSetStatusCode.LOADED
            self.status = KgeFileSetStatusCode.VALIDATED

        self.process_token: Optional[str] = None

    def __str__(self):
        return f"File set version '{self.fileset_version}' of graph '{self.kg_id}': {self.data_files}"
    
    async def is_validated(self) -> bool:
        """
        Predicate to test if a KGE File Set is fully validated.
        
        :return: True if fileset has given status
        """
        if self.status != KgeFileSetStatusCode.VALIDATED and self.process_token:
            await self._get_fileset_processing_status(self.process_token)

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
        return f"{self.kg_id}_{self.fileset_version}"

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
        node_files_keys = list(
            filter(
                lambda x: 'nodes/' in x or KgxNodeFFP.search(x),
                self.get_data_file_object_keys()
            )
        )
        return node_files_keys

    def get_edges(self):
        """

        :return:
        """
        edge_files_keys = list(
            filter(
                lambda x: 'edges/' in x or KgxEdgeFFP.search(x),
                self.get_data_file_object_keys()
            )
        )
        return edge_files_keys

    def get_archive_files(self) -> List[Tuple[str, str, int]]:
        """
        Get the subset of 'tar.gz' archive file (object key, name and size) in the KgeFileSet.

        A tacit design assumption is that this method is only called once the upload of the KgeFileSet is completed,
        since it 'caches' the result of its generation, to accelerate future calls to contains_file_of_type().

        :return: list of archive file entries with object key, name and size, ordered from largest to smallest size.
        """
        if not self.archive_file_list:
            # populate if the archive file subset of the self.data_files is empty?
            for entry in self.data_files.values():
                object_key: str = entry["object_key"]
                file_name: str = entry["file_name"]
                file_size: int = entry["file_size"]
                if '.tar.gz' in file_name:
                    archive_file: Tuple[str, str, int] = object_key, file_name, file_size
                    self.archive_file_list.append(archive_file)
            self.archive_file_list = sorted(self.archive_file_list, key=itemgetter(1), reverse=True)

        return self.archive_file_list
    
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
        if filetype is KgeFileType.ARCHIVE:
            return len(self.get_archive_files()) > 0
        elif filetype is KgeFileType.NODES:
            return len(self.get_nodes()) > 0
        elif filetype is KgeFileType.EDGES:
            return len(self.get_edges()) > 0
        else:
            return False

    # Note: content metadata file name is already normalized on S3 to 'content_metadata.json'
    def set_content_metadata_file(
            self,
            file_name: str,
            file_size: int,
            object_key: str
    ):
        """
        Sets the metadata file identification for a KGE File Set
        :param file_name: original name of metadata file.
        :param file_size: size of metadata file (as number of bytes).
        :param object_key:
        :return: None
        """
        self.content_metadata = {
            "file_name": file_name,
            "file_size": file_size,
            "object_key": object_key,
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
            object_key: str
    ):
        """
        Adds a (meta-)data file to this current of KGE File Set.

        :param file_type: KgeFileType of file being added to the KGE File Set
        :param file_name: to add to the KGE File Set
        :param file_size: number of bytes in the file
        :param object_key: of the file in AWS S3

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
            "file_size": file_size,  # TODO: how do I ensure that this value is accurately set for all files?
            "input_format": input_format,
            "input_compression": input_compression,
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
                # TODO: this could be hazardous to assume True here?
                #       It would be better to track KGX compliance
                #       status somewhere in persisted Archive metadata.
                "kgx_compliant": True,
                # "errors": []
            }

    async def _post_fileset_to_archiver(self, fileset_payload: Dict):

        logger.debug(f"_post_fileset_to_archiver(fileset_payload:\n{fileset_payload}")

        # POST the KgeFileSet 'self' data to the kgea.server.archiver web service
        try:
            async with KgeaSession.get_global_session().post(
                    FILESET_TO_ARCHIVER,
                    json=fileset_payload
            ) as response:
                msg_prefix = "KgeFileSet._post_fileset_to_archiver(): Archiver response"
                logger.debug(f"{msg_prefix} 'status': {response.status}")
                logger.debug(f"{msg_prefix} 'content-type': {response.headers['content-type']}")
                result = await response.json()
                logger.debug(f"{msg_prefix} 'json': {result}")
                if "process_token" in result:
                    self.process_token = result["process_token"]
        except Exception as e:
            logger.error(f"_post_fileset_to_archiver() exception: {str(e)}")
            
    async def _get_fileset_processing_status(self, process_token: str):
        
        logger.debug(f"_get_fileset_processing_status(process_token: {process_token}")

        # POST the KgeFileSet 'self' data to the kgea.server.archiver web service
        async with KgeaSession.get_global_session().get(
                url=f"{FILESET_ARCHIVER_STATUS}?process_token={process_token}"
        ) as response:
            
            msg_prefix = "KgeFileSet._get_fileset_processing_status(): Archiver response"
            logger.debug(f"{msg_prefix} 'status': {response.status}")
            logger.debug(f"{msg_prefix} 'content-type': {response.headers['content-type']}")
            result = await response.json()
            logger.debug(f"{msg_prefix} 'json': {result}")
            
            if not all(key in result for key in ["process_token", "kg_id", "fileset_version", "status"]):
                logger.error(f"_get_fileset_processing_status() {result} missing keys")
                return
            
            # Sanity check: does the process_token belong to the specified file set?
            if result["kg_id"] != self.kg_id:
                logger.error(
                    f"{msg_prefix} : result kg_id '{result['kg_id']}' "
                    f"!= current kd_id '{self.kg_id}' ... skipping!"
                )
                return

            if result["fileset_version"] != self.fileset_version:
                logger.error(
                    f"_{msg_prefix} result kg_id '{result['fileset_version']}' "
                    f"!= current kd_id '{self.fileset_version}' ... skipping!"
                )
                return

            if result["process_token"] != self.process_token:
                logger.error(
                    f"{msg_prefix} : result process_token '{result['process_token']}' "
                    f"!= current process_token '{self.process_token}' ... skipping!"
                )
                return

            if result["status"] == "Completed":
                self.status = KgeFileSetStatusCode.VALIDATED
            elif result["status"] == "Ongoing":
                self.status = KgeFileSetStatusCode.PROCESSING
            else:
                # TODO: perhaps the Archiver "Error" results should return error messages in their payload?
                self.status = KgeFileSetStatusCode.ERROR

    ##########################################
    # KGE FileSet Publication to the Archive #
    ##########################################
    async def publish(self):
        """
        After a file_set is uploaded, publish file set in the Archive
        after post-processing the file set, including generation of the
        file set 'tar.gz' archive for for KGX validation then downloading.
        
        Also sets the file set KgeFileSetStatusCode to PROCESSING.
        """
        # Signal that the KGE File Set is in a post-processing state
        self.status = KgeFileSetStatusCode.PROCESSING

        # Publication of the file_set.yaml is delegated
        # to the kgea.server.archiver microservice task
        fileset_payload = self.to_json_obj()
        await self._post_fileset_to_archiver(fileset_payload)

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
        files = ""
        for entry in self.data_files.values():
            files += "- " + entry["file_name"]+"\n"
        try:
            fileset_metadata_yaml = populate_template(
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
                # TODO: how can we populate this with more complete file_set information here?
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

    def to_json_obj(self):
        """
        Convert KGX File Set to full JSON-like object for serialization
        """
        file_set_obj = {
          "kg_id": self.kg_id,
          "fileset_version": self.fileset_version,
          "date_stamp": self.date_stamp,
          "submitter_name": self.submitter_name,
          "submitter_email": self.submitter_email,
          "biolink_model_release": self.biolink_model_release,
          "status": self.status,
          "size": self.size
        }
        
        file_list = list()
        for object_key in self.get_data_file_object_keys():
            file_entry = self.data_files[object_key]
            file_entry = {
              "object_key": object_key,
              "file_type": file_entry["file_type"].name,
              "file_size": file_entry["file_size"]
            }
            file_list.append(file_entry)
        file_set_obj["files"] = file_list
        
        return file_set_obj


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

        # Trim off any leading and trailing hyphens
        kg_id = kg_id.strip("-")

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
            # logger.warning("KgeKnowledgeGraph.get_file_set(): KGE File Set version '"
            #                + fileset_version + "' unknown for Knowledge Graph '" + self.kg_id + "'?")
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
        return populate_template(
            filename=PROVIDER_METADATA_TEMPLATE_FILE_PATH,
            host=site_hostname, kg_id=self.kg_id, **self.parameter
        )

    def generate_translator_registry_entry(self) -> str:
        """

        :return:
        """
        return populate_template(
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
            object_key: str
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
        :return: None
        """
        knowledge_graph = self.get_knowledge_graph(kg_id)

        if not knowledge_graph:
            raise RuntimeError("add_to_kge_file_set(): Knowledge Graph '" + kg_id + "' is unknown?")
        else:
            # Found a matching KGE Knowledge Graph?
            file_set = knowledge_graph.get_file_set(fileset_version=fileset_version)
            if not file_set:
                raise RuntimeError("add_to_kge_file_set(): File Set version '" + fileset_version + "' is unknown?")

            # Add the current (meta-)data file to the KGE File Set
            # associated with this fileset_version of the graph.
            if file_type in [KgeFileType.DATA_FILE, KgeFileType.ARCHIVE]:
                file_set.add_data_file(
                    object_key=object_key,
                    file_type=file_type,
                    file_name=file_name,
                    file_size=file_size
                )

            elif file_type == KgeFileType.CONTENT_METADATA_FILE:
                file_set.set_content_metadata_file(
                    file_name=file_name,
                    file_size=file_size,
                    object_key=object_key
                )
            else:
                raise RuntimeError("Unknown KGE File Set type?")

    async def get_kg_entries(self) -> Dict[str,  Dict[str, Union[str, List[str]]]]:
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

                # We only want to show fileset versions that exist and are validated
                versions = knowledge_graph.get_version_names()
                filtered_versions = []
                for version in versions:
                    fileset = knowledge_graph.get_file_set(version)
                    if not fileset:
                        logger.warning(f"get_kg_entries(): unknown fileset version '{version}'... skipping")
                    elif await fileset.is_validated():
                        filtered_versions.append(version)
    
                catalog[kg_id] = dict()
                catalog[kg_id]['name'] = knowledge_graph.get_name()
                catalog[kg_id]['versions'] = filtered_versions

        return catalog


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
