"""
Tests against the KGE Catalog module
"""
import pytest
import re


# source_regex = r"^(https?://[a-z.]+(/[a-zA-Z_.]+)*/?|((\w|\.)+:)?(\w|\.|\-)+)$"
# source_regex = r"^((https?\://(\w|\.|\-\/)+)|(\w|\.)+\:)|(\w|\.|\-)+$"
source_regex = r"^((https?\://(\w|\.|\-\/)+)|(\w|\.)+\:(\w|\.|\-)+)$"


@pytest.mark.parametrize(
    "query",
    [
        ('semmeddb_04-2021.tar.gz'),
        ('infores:semmeddb_04-2021.tar.gz'),
        ('PANTHER.FAMILY:PTHR10104'),
        ('http://example.com/ABC123'),
        ('HTTPS://example.com/ABC123'),
    ],
)
def test_content_metadata_source_regex(query):
    """
    Test of Content Metadata knowledge source regex
    """
    sp = re.compile(source_regex)
    assert sp.fullmatch(query[0])[0] == query[0]
