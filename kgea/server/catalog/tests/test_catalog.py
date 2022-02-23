"""
KGE Catalog tests (extracted from catalog module, 22-2-2022
"""

from sys import stderr
from datetime import datetime

import asyncio

from os.path import dirname, abspath
import tempfile
import json
from typing import List

from github import Github

from kgea import PROVIDER_METADATA_TEMPLATE_FILE_PATH, TRANSLATOR_SMARTAPI_TEMPLATE_FILE_PATH
from kgea.config import get_flag, get_app_config
from kgea.server.catalog import (
    KnowledgeGraphCatalog,
    KgeKnowledgeGraph,
    populate_template,
    add_to_s3_repository,
    KgeFileSet,
    KgeFileType,
    add_to_github,
    get_biolink_model_releases,
    get_github_token,
    validate_content_metadata
)
from kgea.server.kgea_file_ops import (
    default_s3_bucket,
    get_object_location,
    get_object_key,
    with_version,
    upload_file,
    random_alpha_string
)

import logging
logger = logging.getLogger(__name__)

# Opaquely access the configuration dictionary
_KGEA_APP_CONFIG = get_app_config()
site_hostname = _KGEA_APP_CONFIG['site_hostname']

RUN_TESTS = get_flag('RUN_TESTS')
CLEAN_TESTS = get_flag('CLEAN_TESTS')

_TEST_SMARTAPI_REPO = "NCATSTranslator/Knowledge_Graph_Exchange_Registry"
_TEST_KGE_SMARTAPI_TARGET_DIRECTORY = "kgea/server/tests/output"

"""
Test Parameters + Decorator
"""
TEST_BUCKET = 'kgea-test-bucket'
TEST_KG_NAME = 'test_kg'
TEST_FILE_DIR = 'kgea/server/test/data/'
TEST_FILE_NAME = 'somedata.csv'

SAMPLE_META_KNOWLEDGE_GRAPH_FILE = abspath(dirname(__file__) + '/sample_meta_knowledge_graph.json')


def test_get_catalog_entries():
    loop = asyncio.get_event_loop()
    catalog = loop.run_until_complete(KnowledgeGraphCatalog.catalog().get_kg_entries())
    print("\ntest_get_catalog_entries() test output:\n", file=stderr)
    print(json.dumps(catalog, indent=4, sort_keys=True), file=stderr)


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


def test_create_provider_metadata_file():
    global _TEST_TPMF
    print("\ntest_create_provider_metadata_entry() test output:\n", file=stderr)
    _TEST_TPMF = populate_template(
        filename=PROVIDER_METADATA_TEMPLATE_FILE_PATH,
        **_TEST_TSE_PARAMETERS
    )
    print(str(_TEST_TPMF), file=stderr)


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
        file_type=KgeFileType.DATA_FILE,
        file_name=file_name,
        file_size=size
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
        file_type=KgeFileType.DATA_FILE,
        file_name=file_name,
        file_size=size
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
                file_type=KgeFileType.DATA_FILE,
                file_name=test_name['archive'],
                file_size=999
            )

    return file_set


def test_create_fileset_metadata_file():

    global _TEST_TFMF
    
    print("\ntest_create_fileset_metadata_entry() test output:\n", file=stderr)

    fs = prepare_test_file_set()

    _TEST_TFMF = fs.generate_fileset_metadata_file()

    print(str(_TEST_TPMF), file=stderr)


def test_create_translator_registry_entry():
    global _TEST_TRE
    print("\ntest_create_translator_registry_entry() test output:\n", file=stderr)
    _TEST_TRE = populate_template(
        filename=TRANSLATOR_SMARTAPI_TEMPLATE_FILE_PATH,
        **_TEST_TSE_PARAMETERS
    )
    print(str(_TEST_TRE), file=stderr)


def test_add_to_archive() -> bool:
    outcome: str = add_to_s3_repository(
        kg_id="kge_test_provider_metadata_file",
        text=_TEST_TPMF,
        file_name="test_provider_metadata_file",
        fileset_version="100.0"
    )

    return not outcome == ''


def test_add_to_github():
    outcome: bool = add_to_github(
        "kge_test_translator_registry_entry",
        _TEST_TRE,
        repo_path=_TEST_SMARTAPI_REPO,
        target_directory=_TEST_KGE_SMARTAPI_TARGET_DIRECTORY
    )

    return outcome


def test_get_biolink_releases():
    """

    :return:
    """
    releases: List = get_biolink_model_releases()
    assert ('2.0.2' in releases)
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
        # run_test(test_contents_metadata_validator)
        # test_get_biolink_releases()
        # assert (test_get_catalog_entries())
        #
        print("Catalog package module tests completed?")

    # if CLEAN_TESTS:
    #     clean_tests()
