from asyncio import run
from sys import stderr
from typing import List

from kgea.server.archiver import KgeArchiver
from kgea.server.archiver.kge_archiver_util import compress_fileset, logger
from kgea.server.catalog import prepare_test_file_set
from kgea.server.tests import TEST_KG_ID, TEST_FS_VERSION, TEST_BUCKET
from kgea.server.tests.unit.test_kgea_file_ops import logger


async def test_compress_fileset():
    try:
        s3_archive_key: str = await compress_fileset(
            kg_id=TEST_KG_ID,
            version=TEST_FS_VERSION,
            bucket=TEST_BUCKET,
            root='kge-data'
        )
        logger.info(f"test_compress_fileset(): s3_archive_key == {s3_archive_key}")
        assert (s3_archive_key == f"s3://{TEST_BUCKET}/kge-data/{TEST_KG_ID}/{TEST_FS_VERSION}"
                                  f"/archive/{TEST_KG_ID + '_' + TEST_FS_VERSION}.tar.gz")
    except Exception as e:
        logger.error(e)
        assert False


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

        # We create all our workers in the KgeArchiver() constructor
        # archiver.create_workers(2)

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


# TODO: more complete KGX validator test
def test_kgx_data_validator():
    """

    :return:
    """
    print("\ntest_kgx_data_validator() test output:\n", file=stderr)

    errors: List[str] = []  # validate_content_metadata(mkg_json)

    if errors:
        logger.error("test_contents_data_validator() errors: " + str(errors))
    return not errors
