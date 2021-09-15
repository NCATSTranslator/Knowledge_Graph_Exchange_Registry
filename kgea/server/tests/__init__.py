"""
test package

Test Parameters + Decorator
"""
from os.path import abspath, dirname
from pathlib import Path

TEST_DATA_DIR = Path(dirname(abspath(__file__))).joinpath("data")

TEST_SMALL_FILE_NAME = 'somedata.csv'
TEST_SMALL_FILE_PATH = TEST_DATA_DIR.joinpath(TEST_SMALL_FILE_NAME)

TEST_BUCKET = 'kgea-test-bucket'
TEST_KG_NAME = 'test_kg'
TEST_FILESET_VERSION = '4.3'

TEST_LARGE_KG = "sri-reference-graph"
TEST_LARGE_FS_VERSION = "2.0"

TEST_LARGE_NODES_FILE = "sm_nodes.tsv"
TEST_LARGE_NODES_FILE_KEY = f"kge-data/{TEST_LARGE_KG}/{TEST_LARGE_FS_VERSION}/nodes/{TEST_LARGE_NODES_FILE}"

TEST_HUGE_NODES_FILE = "sri-reference-kg_nodes.tsv"
TEST_HUGE_NODES_FILE_KEY = f"kge-data/{TEST_LARGE_KG}/{TEST_LARGE_FS_VERSION}/nodes/{TEST_HUGE_NODES_FILE}"
TEST_HUGE_EDGES_FILE = "sri-reference-kg_edges.tsv"
TEST_HUGE_EDGES_FILE_KEY = f"kge-data/{TEST_LARGE_KG}/{TEST_LARGE_FS_VERSION}/edges/{TEST_HUGE_EDGES_FILE}"

TEST_DIRECT_TRANSFER_LINK = 'https://archive.monarchinitiative.org/latest/kgx/sri-reference-kg_nodes.tsv'
TEST_DIRECT_TRANSFER_LINK_FILENAME = 'sri-reference-kg_nodes.tsv'
TEST_SMALL_FILE_RESOURCE_URL = "https://raw.githubusercontent.com/NCATSTranslator/" + \
                               "Knowledge_Graph_Exchange_Registry/master/LICENSE"
