from sys import stderr
from typing import List

from kgea.server.archiver.kge_archiver_util import compress_fileset, logger
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
