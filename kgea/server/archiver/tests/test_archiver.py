from asyncio import sleep
from sys import stderr
from typing import List, Dict

import pytest

from kgea.aws.ec2 import scratch_dir_path
from kgea.server import print_error_trace
from kgea.server.archiver.kge_archiver_util import compress_fileset, logger, KgeArchiver, aggregate_files, \
    extract_data_archive
from kgea.server.catalog.tests.test_catalog import prepare_test_file_set
from kgea.server.tests import TEST_KG_ID, TEST_FS_VERSION, TEST_BUCKET, TEST_HUGE_NODES_FILE_KEY, \
    TEST_HUGE_EDGES_FILE_KEY, TEST_SMALL_FILE_1_PATH, TEST_SMALL_FILE_2_PATH
from kgea.server.tests.unit.test_kgea_file_ops import logger, upload_test_file, delete_test_file


def test_aggregate_files():

    test_kg_folder = f"kge-data/{TEST_KG_ID}"
    test_fileset_folder = f"{test_kg_folder}/{TEST_FS_VERSION}"

    test_file_1_object_key = upload_test_file(
        test_bucket=TEST_BUCKET,
        test_kg=TEST_KG_ID,
        test_file_path=TEST_SMALL_FILE_1_PATH
    )
    test_file_2_object_key = upload_test_file(
        test_bucket=TEST_BUCKET,
        test_kg=TEST_KG_ID,
        test_file_path=TEST_SMALL_FILE_2_PATH
    )

    test_archive_folder = f"{test_fileset_folder}/archive"

    try:
        # only aggregating one file?
        agg_path: str = aggregate_files(
            target_folder=test_archive_folder,
            target_name='edges.tsv',
            file_object_keys=[
                test_file_1_object_key,
                test_file_2_object_key
            ],
            bucket=TEST_BUCKET,
            match_function=lambda x: True
        )
    except Exception as e:
        print_error_trace("Error while unpacking archive?: " + str(e))
        assert False

    assert (agg_path == f"s3://{TEST_BUCKET}/{test_archive_folder}/edges.tsv")

    # This should delete all the current test artifacts
    delete_test_file(test_object_key=f"{test_archive_folder}/edges.tsv")
    delete_test_file(test_object_key=test_file_1_object_key)
    delete_test_file(test_object_key=test_file_2_object_key)


@pytest.mark.skip(reason="Huge File Test not normally run")
def test_huge_aggregate_files():
    """
    NOTE: This test attempts transfer of a Huge pair or multi-gigabyte files in S3.
    It is best to run this test on an EC2 server with the code.

    :return:
    """
    target_folder = f"kge-data/{TEST_KG_ID}/{TEST_FS_VERSION}/archive"
    try:
        agg_path: str = aggregate_files(
            bucket=TEST_BUCKET,
            target_folder=target_folder,
            target_name='nodes_plus_edges.tsv',
            file_object_keys=[
                TEST_HUGE_NODES_FILE_KEY,
                TEST_HUGE_EDGES_FILE_KEY
            ],
            match_function=lambda x: True
        )
    except Exception as e:
        print_error_trace("Error while unpacking archive?: " + str(e))
        assert False

    assert (agg_path == f"s3://{TEST_BUCKET}/{target_folder}/nodes_plus_edges.tsv")


@pytest.mark.asyncio
async def test_extract_data_archive():
    archive_file_entries: List[Dict[str, str]] = await extract_data_archive(
        kg_id=TEST_KG_ID,
        version=TEST_FS_VERSION,
        scratch_dir=scratch_dir_path(),
        bucket=TEST_BUCKET,
        root_directory='kge-data'
    )
    logger.info(f"test_extract_data_archive(): archive_file_entries == {str(archive_file_entries)}")


@pytest.mark.asyncio
async def test_compress_fileset():
    s3_archive_key: str = await compress_fileset(
        kg_id=TEST_KG_ID,
        version=TEST_FS_VERSION,
        scratch_dir=scratch_dir_path(),
        bucket=TEST_BUCKET,
        root_directory='kge-data'
    )
    logger.info(f"test_compress_fileset(): s3_archive_key == {s3_archive_key}")
    assert (s3_archive_key == f"s3://{TEST_BUCKET}/kge-data/{TEST_KG_ID}/{TEST_FS_VERSION}"
                              f"/archive/{TEST_KG_ID + '_' + TEST_FS_VERSION}.tar.gz")


# TODO: more complete KGX validator test
@pytest.mark.skip("Not yet implemented")
def test_kgx_data_validator():
    """

    :return:
    """
    print("\ntest_kgx_data_validator() test output:\n", file=stderr)

    errors: List[str] = []  # validate_content_metadata(mkg_json)

    if errors:
        logger.error("test_contents_data_validator() errors: " + str(errors))

    assert not errors


# This is a simple test of the KgxArchive queue/task.
# It cannot be run with the given test_file_set object
# since the data files don't exist in S3!
@pytest.mark.asyncio
async def archive_test():
    """
    async archive test wrapper
    :return:
    """
    logger.debug("\nRunning test_stub_archiver()")

    archiver: KgeArchiver = KgeArchiver()

    # We now create all our workers in the KgeArchiver() constructor
    # archiver.create_workers(2)

    fs = prepare_test_file_set("1.0")
    await archiver.process(fs)

    # fs = test_file_set("1.1")
    # await archiver.process(fs)
    # fs = test_file_set("1.2")
    # await archiver.process(fs)
    # fs = test_file_set("1.3")
    # await archiver.process(fs)

    # # Don't want to finish too quickly...
    await sleep(30)
    #
    logger.debug("\ntest_stub_archiver() shutdown now!\n")
    await archiver.shutdown_workers()
