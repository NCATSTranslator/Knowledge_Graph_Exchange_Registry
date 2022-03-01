"""
test package

Test Parameters + Decorator
"""
from os.path import abspath, dirname
from pathlib import Path

# A temporary convenience to point to testing data in a specific branch.
# Should default to 'master' or 'develop' later?
# https://raw.githubusercontent.com/NCATSTranslator/Knowledge_Graph_Exchange_Registry/pre-release_15-Sept-2021/kgea/tests/data/README.md
KGE_CODE_BRANCH = "master"

TEST_DATA_DIR = Path(abspath(dirname(__file__))).joinpath("data")
TEST_OUTPUT_DIR = Path(abspath(dirname(__file__))).joinpath("output")

TEST_BUCKET = 'kgea-test-bucket'
TEST_BUCKET_2 = 'delphinai-kgea-test-bucket-2'
TEST_KG_ID = 'test-kg'
TEST_FS_VERSION = "1.0"
TEST_OBJECT = "test_object.txt"

TEST_SMALL_FILE_1 = 'small_edges_1.tsv'
TEST_SMALL_FILE_1_PATH = str(TEST_DATA_DIR.joinpath(TEST_SMALL_FILE_1))
TEST_SMALL_FILE_1_KEY = f"test-data/{TEST_SMALL_FILE_1}"
TEST_SMALL_FILE_1_RESOURCE_URL = "https://raw.githubusercontent.com/NCATSTranslator/" + \
                               f"Knowledge_Graph_Exchange_Registry/" + \
                               f"{KGE_CODE_BRANCH}/kgea/tests/data/{TEST_SMALL_FILE_1}"

TEST_SMALL_FILE_2 = 'small_edges_2.tsv'
TEST_SMALL_FILE_2_PATH = str(TEST_DATA_DIR.joinpath(TEST_SMALL_FILE_2))
TEST_SMALL_FILE_2_KEY = f"test-data/{TEST_SMALL_FILE_2}"
TEST_SMALL_FILE_2_RESOURCE_URL = "https://raw.githubusercontent.com/NCATSTranslator/" + \
                               f"Knowledge_Graph_Exchange_Registry/" + \
                               f"{KGE_CODE_BRANCH}/kgea/tests/data/{TEST_SMALL_FILE_2}"

TEST_LARGE_NODES_FILE = "large_nodes.tsv"
TEST_LARGE_FILE_PATH = str(TEST_DATA_DIR.joinpath(TEST_LARGE_NODES_FILE))
TEST_LARGE_NODES_FILE_KEY = f"kge-data/{TEST_KG_ID}/{TEST_FS_VERSION}/nodes/{TEST_LARGE_NODES_FILE}"
TEST_LARGE_FILE_RESOURCE_URL = "https://raw.githubusercontent.com/NCATSTranslator/" + \
                               f"Knowledge_Graph_Exchange_Registry/" + \
                               f"{KGE_CODE_BRANCH}/kgea/tests/data/{TEST_LARGE_NODES_FILE}"

TEST_HUGE_NODES_FILE = "sri-reference-kg_nodes.tsv"
TEST_HUGE_NODES_FILE_KEY = f"kge-data/{TEST_KG_ID}/{TEST_FS_VERSION}/nodes/{TEST_HUGE_NODES_FILE}"
TEST_HUGE_EDGES_FILE = "sri-reference-kg_edges.tsv"
TEST_HUGE_EDGES_FILE_KEY = f"kge-data/{TEST_KG_ID}/{TEST_FS_VERSION}/edges/{TEST_HUGE_EDGES_FILE}"

# This is externally hosted Monarch data, the availability for which may change with time
TEST_HUGE_FILE_RESOURCE_URL = 'https://archive.monarchinitiative.org/latest/kgx/sri-reference-kg_nodes.tsv'

# a test kgx data archive
TEST_DATA_ARCHIVE = "test_data_archive.tar.gz"
TEST_DATA_ARCHIVE_PATH = str(TEST_DATA_DIR.joinpath(TEST_DATA_ARCHIVE))

# a production server test files
PROD_TEST_FILE_KEY = 'kge-data/sri-semantic-medline-database/4.3/content_metadata.json'
