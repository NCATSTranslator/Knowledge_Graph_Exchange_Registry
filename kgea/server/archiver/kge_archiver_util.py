from asyncio import Queue, Task, create_task, sleep, gather, QueueFull
from typing import List, Dict, Optional
from os.path import sep, dirname, abspath
from uuid import uuid4

import smart_open
from kgx.transformer import Transformer
from kgx.utils.kgx_utils import GraphEntityType
from kgx.validator import Validator

from kgea.config import (
    FILE_SET_METADATA_FILE,
    PROVIDER_METADATA_FILE,
    CONTENT_METADATA_FILE,
    get_app_config
)
from kgea.aws.assume_role import aws_config

from kgea.server import print_error_trace, run_script
from kgea.server.archiver.kge_archiver_status import set_process_status
from kgea.server.archiver.models import ProcessStatusCode

from kgea.server.catalog import (
    KgeFileSet,
    KgxFFP,
    add_to_s3_repository, KgeFileType
)

from kgea.server.kgea_file_ops import (
    object_key_exists,
    copy_file,
    create_presigned_url
)

from kgea.server.web_services.models import KgeFileSetStatusCode

import logging
logger = logging.getLogger(__name__)

s3_config = aws_config['s3']
default_s3_bucket = s3_config['bucket']
default_s3_root_key = s3_config['archive-directory']

_EDA_OUTPUT_DATA_PREFIX = "file_entry="  # the Decompress-In-Place bash script comment output data signal prefix
_KGEA_EDA_SCRIPT = f"{dirname(abspath(__file__))}{sep}scripts{sep}kge_extract_data_archive.bash"
_KGEA_ARCHIVER_SCRIPT = f"{dirname(abspath(__file__))}{sep}scripts{sep}kge_archiver.bash"

_KGEA_APP_CONFIG = get_app_config()

Number_of_Archiver_Tasks = \
    _KGEA_APP_CONFIG['Number_of_Archiver_Tasks'] if 'Number_of_Archiver_Tasks' in _KGEA_APP_CONFIG else 1

Number_of_Validator_Tasks = \
    _KGEA_APP_CONFIG['Number_of_Validator_Tasks'] if 'Number_of_Validator_Tasks' in _KGEA_APP_CONFIG else 1

# TODO: operational parameter dependent configuration
MAX_WAIT = 100  # number of iterations until we stop pushing onto the queue. -1 for unlimited waits


def aggregate_files(
        target_folder,
        target_name,
        file_object_keys,
        bucket=default_s3_bucket,
        match_function=lambda x: True
) -> str:
    """
    Aggregates files matching a match_function.

    :param bucket:
    :param target_folder:
    :param target_name: target data file format(s)
    :param file_object_keys:
    :param match_function:
    :return:
    """
    if not file_object_keys:
        return ''

    agg_path = f"s3://{bucket}/{target_folder}/{target_name}"
    logger.debug(f"agg_path: {agg_path}")
    with smart_open.open(agg_path, 'w', encoding="utf-8", newline="\n") as aggregated_file:
        file_object_keys = list(filter(match_function, file_object_keys))
        for index, file_object_key in enumerate(file_object_keys):
            target_key_uri = f"s3://{bucket}/{file_object_key}"
            with smart_open.open(target_key_uri, 'r', encoding="utf-8", newline="\n") as subfile:
                for line in subfile:
                    aggregated_file.write(line)
                if index < (len(file_object_keys) - 1):  # only add newline if it isn't the last file. -1 for zero index
                    aggregated_file.write("\n")

    return agg_path


async def compress_fileset(
        kg_id,
        version,
        bucket=default_s3_bucket,
        root=default_s3_root_key
) -> str:
    """
    :param kg_id:
    :param version:
    :param bucket:
    :param root:
    :return:
    """
    s3_archive_key = f"s3://{bucket}/{root}/{kg_id}/{version}/archive/{kg_id + '_' + version}.tar.gz"

    logger.info(f"Initiating execution of compress_fileset({s3_archive_key})")

    try:
        return_code = await run_script(
            script=_KGEA_ARCHIVER_SCRIPT,
            args=(bucket, root, kg_id, version)
        )
        logger.info(f"Finished archive script build {s3_archive_key}, return code: {str(return_code)}")

    except Exception as e:
        logger.error(f"compress_fileset({s3_archive_key}) exception: {str(e)}")

    logger.info(f"Exiting compress_fileset({s3_archive_key})")

    return s3_archive_key


async def extract_data_archive(
        kg_id: str,
        file_set_version: str,
        archive_filename: str,
        bucket: str = default_s3_bucket,
        root_directory: str = default_s3_root_key
) -> List[Dict[str, str]]:
    """
    Decompress a tar.gz data archive file from a given S3 bucket, and upload back its internal files back.

    Version 1.0 - decompress_in_place() below used Smart_Open... not scalable
    Version 2.0 - this version uses an external bash shell script to perform this operation...

    :param kg_id: knowledge graph identifier to which the archive belongs
    :param file_set_version: file set version to which the archive belongs
    :param archive_filename: base name of the tar.gz archive to be decompressed
    :param bucket: in S3
    :param root_directory: KGE data folder in the bucket

    :return: list of file entries
    """
    # one step decompression - bash level script operations on the local disk
    logger.debug(f"Initiating execution of extract_data_archive({archive_filename})")

    if not archive_filename.endswith('.tar.gz'):
        err_msg = f"archive name '{str(archive_filename)}' is not a 'tar.gz' archive?"
        logger.error(err_msg)
        raise RuntimeError(f"extract_data_archive(): {err_msg}")

    part = archive_filename.split('.')
    archive_filename = '.'.join(part[:-2])

    file_entries: List[Dict[str, str]] = []

    def output_parser(line: str):
        """
        :param line: bash script stdout line being parsed
        """
        if not line.strip():
            return   # empty line?

        # logger.debug(f"Entering output_parser(line: {line})!")
        if line.startswith(_EDA_OUTPUT_DATA_PREFIX):
            line = line.replace(_EDA_OUTPUT_DATA_PREFIX, '')
            file_name, file_type, file_size, file_object_key = line.split(',')
            logger.debug(f"DDA script file entry: {file_name}, {file_type}, {file_size}, {file_object_key}")
            file_entries.append({
                "file_name": file_name,
                "file_type": file_type,
                "file_size": str(file_size),
                "object_key": file_object_key
            })
    try:
        return_code = await run_script(
            script=_KGEA_EDA_SCRIPT,
            args=(
                bucket,
                root_directory,
                kg_id,
                file_set_version,
                archive_filename
            ),
            stdout_parser=output_parser
        )
        logger.debug(f"Completed extract_data_archive({archive_filename}.tar.gz), with return code {str(return_code)}")

    except Exception as e:
        logger.error(f"extract_data_archive({archive_filename}.tar.gz): exception {str(e)}")

    logger.debug(f"Exiting extract_data_archive({archive_filename}.tar.gz)")

    return file_entries


class KgeArchiver:
    """
    KGE Archive building wrapper.
    """
    #
    # we leave the Queue open ended now...
    #
    # def __init__(self, max_tasks=Number_of_Archiver_Tasks, max_queue=MAX_QUEUE, max_wait=MAX_WAIT):
    def __init__(self, max_tasks=Number_of_Archiver_Tasks, max_wait=MAX_WAIT):
        """
        Constructor for a single archiver task wrapper.
        """
        #  we won't worry about queue size in this application
        #  unless informed otherwise by our use cases...
        # self._archiver_queue: Queue = Queue(maxsize=max_queue)
        self._archiver_queue: Queue = Queue()  # unlimited queue size
        self._archiver_worker: List[Task] = list()

        # we hard code the creation of KgeArchiver tasks here, not later
        for i in range(0, max_tasks):
            self._archiver_worker.append(create_task(self.worker()))

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
    def aggregate_to_archive(
            file_set: KgeFileSet,
            kgx_file_type: str,
            file_object_keys
    ):
        """
        Wraps file aggregator for a given file type.

        :param file_set: KGE File Set metadata object
        :param kgx_file_type: the core file type to be aggregated (i.e. nodes or edges)
        :param file_object_keys: list of S3 object keys of files to be aggregated
        """
        key_list = "\n\t".join(file_object_keys)

        # Sanity check: in this release, KGX file formats
        # of aggregated files all need to be identical
        input_format = ''
        for fok in file_object_keys:
            part = fok.split('.')
            m = KgxFFP.match(part[-1])
            if m:
                if not input_format:
                    input_format = m['filext']
                elif input_format != m['filext']:
                    raise RuntimeError(f"aggregate_to_archive(): cannot have mixed KGX formats in'{key_list}'!")
        if input_format:
            kgx_file_type += f".{input_format}"
        else:
            # Default to KGX TSV format? Is this a risky assumption?
            kgx_file_type += ".tsv"

        logger.debug(f"Aggregating {kgx_file_type} files in KGE File Set '{file_set.id()}'\n"
                     f"\tcontaining KGX {input_format} formatted object keys:\n\t{key_list}")
        try:
            agg_path: str = aggregate_files(
                target_folder=f"kge-data/{file_set.kg_id}/{file_set.fileset_version}/archive",
                target_name=kgx_file_type,
                file_object_keys=file_object_keys
            )
            logger.debug(f"{kgx_file_type} path: {agg_path}")

        except Exception as e:
            # Can't be more specific than this 'cuz not sure what errors may be thrown here...
            print_error_trace(f"'{kgx_file_type}' file aggregation failure - " + str(e))
            raise e

        file_set.add_data_file(KgeFileType.DATA_FILE, kgx_file_type, 0, agg_path)

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
            process_token, file_set = await self._archiver_queue.get()

            # We need to signal a worker non-fatal local processing failure
            abort = False

            logger.info(
                f"KgeArchiver worker {task_id} starting archive of " +
                f"{file_set.id()} with process_token '{process_token}'"
            )

            # sleep briefly to yield to co-routine executed main web application code. Done several times below...
            # 10 seconds to allow the user to go to home and get the KG catalog, before this task ties up the CPU?
            # TODO: performance issue seems to result from execution of this code on servers with few CPU's?
            #       Or is this a main loop blockage issue (which maybe needs to be resolved some other way?)
            await sleep(0.001)

            # 1. Unpack any uploaded archive(s) where they belong: (JSON) content metadata, nodes and edges
            try:
                archive_file_key_list = file_set.get_archive_file_keys()
                logger.debug(f"KgeArchiver task {task_id} unpacking incoming tar.gz archives: {archive_file_key_list}")

                for archive_file_key in archive_file_key_list:

                    archive_filename = file_set.get_property_of_data_file_key(archive_file_key, 'file_name')

                    logger.debug(f"Unpacking archive {archive_filename}")

                    #
                    # RMB: 2021-10-07, we deprecated the RAM-based version of the 'decompress-in-place' operation,
                    # moving instead towards the kge_extract_data_archive.bash hard disk-centric solution
                    #
                    # archive_file_entries = decompress_to_kgx(file_key, archive_location)
                    #
                    archive_file_entries: List[Dict[str, str]] = \
                        await extract_data_archive(
                            kg_id=file_set.get_kg_id(),
                            file_set_version=file_set.get_fileset_version(),
                            archive_filename=archive_filename
                        )
                    #
                    # ...Remove the archive entry from the KgxFileSet...
                    file_set.remove_data_file(archive_file_key)

                    # take a quick rest, to give other co-routines a chance?
                    await sleep(0.001)

                    logger.debug(f"Adding {len(archive_file_entries)} files to fileset '{file_set.id()}':")

                    # ...but add in the archive's files to the file set
                    for entry in archive_file_entries:
                        # spread the entry across the add_data_file function,
                        # which will take all its values as arguments
                        logger.debug(f"\t{entry['file_name']}")
                        file_set.add_data_file(
                            file_name=entry["file_name"],
                            file_type=KgeFileType(int(entry["file_type"])),
                            file_size=int(entry["file_size"]),
                            object_key=entry["object_key"]
                        )

            except Exception as e:
                # Can't be more specific than this 'cuz not sure what errors may be thrown here...
                print_error_trace("KgeArchiver.worker(): Error while unpacking archive?: "+str(e))
                abort = True

            if not abort:
                # take a quick rest, to give other co-routines a chance?
                await sleep(0.001)

                logger.debug("Create and add the fileset.yaml to the KGE S3 repository")

                try:
                    # Publish a 'file_set.yaml' metadata file to the
                    # versioned archive subdirectory containing the KGE File Set

                    fileset_metadata_file = file_set.generate_fileset_metadata_file()
                    fileset_metadata_object_key = add_to_s3_repository(
                        kg_id=file_set.get_kg_id(),
                        text=fileset_metadata_file,
                        file_name=FILE_SET_METADATA_FILE,
                        fileset_version=file_set.get_fileset_version()
                    )
                    if fileset_metadata_object_key:
                        logger.info(f"KgeFileSet.publish(): successfully created object key {fileset_metadata_object_key}")
                    else:
                        msg = f"publish(): metadata '{FILE_SET_METADATA_FILE}" + \
                              f"' file for KGE File Set version '{file_set.get_fileset_version()}" + \
                              f"' of knowledge graph '{file_set.get_kg_id()}" + \
                              "' not successfully posted to the Archive?"
                        file_set.report_error(msg)
                        abort = True

                except Exception as exc:
                    msg = f"publish(): {file_set.get_kg_id()} {file_set.get_fileset_version()} {str(exc)}"
                    file_set.report_error(msg)
                    print_error_trace(msg)
                    abort = True

            if not abort:

                logger.debug("Aggregating data to archive")

                # take a quick rest, to give other co-routines a chance?
                await sleep(0.001)

                try:
                    # 2. Aggregate each of all nodes and edges each
                    #    into their respective files in the archive folder
                    self.aggregate_to_archive(
                        file_set=file_set,
                        kgx_file_type="nodes",
                        file_object_keys=file_set.get_nodes()
                    )
                    self.aggregate_to_archive(
                        file_set=file_set,
                        kgx_file_type="edges",
                        file_object_keys=file_set.get_edges()
                    )
                except Exception as e:
                    print_error_trace("KgeArchiver.worker(): aggregating files to archive - " + str(e))
                    abort = True

            if not abort:

                logger.debug("Copying over metadata to archive")

                try:
                    # 3. Copy over metadata files into the archive folder
                    self.copy_to_kge_archive(file_set, PROVIDER_METADATA_FILE)
                    self.copy_to_kge_archive(file_set, FILE_SET_METADATA_FILE)
                    self.copy_to_kge_archive(file_set, CONTENT_METADATA_FILE)
                except Exception as e:
                    print_error_trace("KgeArchiver.worker(): Error while copying metadata files to archive?: " + str(e))
                    abort = True

            if not abort:

                # take a quick rest, to give other co-routines a chance?
                await sleep(0.001)

                # 4. Tar and gzip a single <kg_id>.<fileset_version>.tar.gz archive file containing the
                #    aggregated kgx nodes, edges and metadata files. Computer SHA1 hash on the file.

                logger.debug("Compressing total KGE file set...")

                try:
                    s3_archive_key: str = await compress_fileset(
                        kg_id=file_set.get_kg_id(),
                        version=file_set.get_fileset_version()
                    )
                except Exception as e:
                    # Can't be more specific than this 'cuz not sure what errors may be thrown here...
                    print_error_trace("File set compression failure! "+str(e))
                    abort = True

                logger.debug("...File compression completed!")

            if not abort:

                # take a quick rest, to give other co-routines a chance?
                await sleep(0.001)

                # 5. KGX validation of KGE compliant archive.
                logger.debug(
                    f"(Future) KgeArchiver worker {task_id} validation of {file_set.id()} tar.gz archive..."
                )

                # TODO: Debug and/or redesign KGX validation of data files - doesn't yet work properly
                # TODO: need to managed multiple Biolink Model-specific KGX validators

                # try:
                #     validator: KgxValidator = KnowledgeGraphCatalog.catalog().get_validator()
                #     KgxValidator.validate(self)
                # except Exception as e:
                #     # Can't be more specific than this 'cuz not sure what errors may be thrown here...
                #     print_error_trace("File set validation failure! "+str(e))
                #     abort = True

                # Assume that the TAR.GZ archive of the
                # KGE File Set is validated by this point
                # TODO: need to fix propagation of file set validation status (now hiding behind 'Archiver' process?)
                file_set.status = KgeFileSetStatusCode.VALIDATED

            if not abort:
                logger.debug(f"KgeArchiver worker {task_id} finished archiving of {file_set.id()}")
                await set_process_status(process_token, ProcessStatusCode.COMPLETED)
            else:
                logger.error(f"Failed KgeArchiver worker {task_id} archiving of {file_set.id()}")
                await set_process_status(process_token, ProcessStatusCode.ERROR)

            self._archiver_queue.task_done()

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

    async def process(self, file_set: KgeFileSet) -> str:
        """
        This method posts a KgeFileSet to the KgeArchiver for processing.

        :param file_set: KgeFileSet.
        :param process_token: str.
        """

        process_token = uuid4().hex
        await set_process_status(process_token, ProcessStatusCode.ONGOING)

        # Post the file set to the KgeArchiver task Queue for processing
        logger.debug(
            f"KgeArchiver.process(): adding '{file_set.id()}' " +
            f"to archiver work queue, with process token '{process_token}'"
        )
        self._archiver_queue.put_nowait((process_token, file_set))  # sending a 2-tuple as an item

        return process_token


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

                logger.debug(
                    f"KgxValidator() processing file '{file_name}' '{object_key}' " +
                    f"of type '{file_type_opt.name}', input format '{input_format}' " +
                    f"and with compression '{input_compression}', "
                )

                # The file to be processed should currently be
                # a resource accessible from this S3 authenticated URL?
                s3_file_url = create_presigned_url(object_key=object_key)
                input_files.append(s3_file_url)

            ###################################
            # ...then, process them together...
            ###################################
            if file_type_opt == KgeFileType.DATA_FILE:
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

            elif file_type_opt == KgeFileType.ARCHIVE:
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
            input_format: str,
            input_compression: Optional[str] = None
    ) -> List:
        """
        Validates KGX compliance of a specified data file.

        :param file_set_id: name of the file set, generally a composite identifier of the kg_id plus fileset_version?
        :param input_files: list of file path strings pointing to files to be validated (could be a resolvable URL?)
        :param input_format: KGX file format (file extension) ... needs to be be consistent for all input_files
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
