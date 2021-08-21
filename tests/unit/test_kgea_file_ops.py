"""
Test Parameters + Decorator
"""
import logging
from sys import stderr

import requests

from kgea.server.web_services.kgea_file_ops import upload_from_link

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logging = True

TEST_BUCKET = 'kgea-test-bucket'
TEST_KG_NAME = 'test_kg'
TEST_FILESET_VERSION = '4.3'
TEST_FILE_DIR = 'kgea/server/test/data/'
TEST_FILE_NAME = 'somedata.csv'

DIRECT_TRANSFER_TEST_LINK = 'https://archive.monarchinitiative.org/latest/kgx/sri-reference-kg_nodes.tsv'
DIRECT_TRANSFER_TEST_LINK_FILENAME = 'sri-reference-kg_nodes.tsv'


def test_upload_from_link(
        test_bucket=TEST_BUCKET,
        test_link=DIRECT_TRANSFER_TEST_LINK,
        test_link_filename=DIRECT_TRANSFER_TEST_LINK_FILENAME,
        test_kg=TEST_KG_NAME,
        test_fileset_version=TEST_FILESET_VERSION
):
    progress_monitor = None

    if logging:

        class ProgressPercentage(object):
            """
            Class to track percentage completion of an upload.
            """

            REPORTING_INCREMENT: int = 1000000

            def __init__(self, filename, file_size, cont=None):
                self._filename = filename
                self.size = file_size
                self._seen_so_far = 0
                self._report_threshold = self.REPORTING_INCREMENT
                self.cont = cont

            def get_file_size(self):
                """
                :return: file size of the file being uploaded.
                """
                return self.size

            def __call__(self, bytes_amount):
                # To simplify we'll assume this is hooked up
                # to a single filename.
                # with self._lock:
                self._seen_so_far += bytes_amount

                if self.cont is not None:
                    # cont lets us inject e.g. logging
                    if self._seen_so_far > self._report_threshold:
                        self.cont(self)
                        self._report_threshold += self.REPORTING_INCREMENT

        # url = "https://speed.hetzner.de/100MB.bin"
        # just a dummy file URL
        info = requests.head(test_link)
        # fetching the header information
        logger.debug(info.headers['Content-Length'])

        progress_monitor = ProgressPercentage(
            test_link_filename,
            info.headers['Content-Length'],
            cont=lambda progress: print(
                f"upload progress for link {test_link} so far: {progress._seen_so_far}", file=stderr, flush=True
            )
        )

    object_key = f"{test_kg}/{test_fileset_version}/{test_link_filename}"

    logger.debug("\ntest_upload_from_link() url: '"+test_link+"' to object key '"+object_key+"':\n")

    try:
        upload_from_link(
            url=test_link,
            bucket=test_bucket,
            object_key=object_key,
            callback=progress_monitor
        )
    except RuntimeError as rte:
        logger.error('Failed?: '+str(rte))
        assert False
    logger.debug('Success!')