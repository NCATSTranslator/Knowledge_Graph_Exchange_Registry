"""
Tests against the KGE Catalog module
"""
import pytest
import re
import json

from kgea.server.web_services.catalog import CONTENT_METADATA_SCHEMA, validate_content_metadata

source_regex = r"^((https?://\w(\w|\.|\-|\/)+)|(\w|\.)+:)?(\w|\.|\-)+"


@pytest.mark.parametrize(
    "query",
    [
        ('semmeddb_04-2021.tar.gz',),
        ('infores:semmeddb_04-2021.tar.gz',),
        ('PANTHER.FAMILY:PTHR10104',),
        ('http://example.com/ABC123',),
        ('https://example.com/ABC123',),
        ("infores:flyBase",),
        ("infores:go",),
    ],
)
def test_content_metadata_source_regex(query):
    """
    Test of Content Metadata knowledge source regex
    """
    sp = re.compile(source_regex)
    m = sp.fullmatch(query[0])
    assert m
    assert m[0] == query[0]


@pytest.mark.parametrize(
    "query",
    [
        (
                """
{
    "nodes": {
        "biolink:Gene": {
            "id_prefixes": [
                "FlyBase"
            ],
            "count": 29906,
            "count_by_source": {
                "infores:flyBase": 29906
            }
        },
        "biolink:OntologyClass": {
            "id_prefixes": [
                "GO"
            ],
            "count": 2928,
            "count_by_source": {
                "infores:go": 2928
            }
        }
    },
    "edges": [
            {
            "subject": "biolink:Gene",
            "predicate": "biolink:enables",
            "object": "biolink:OntologyClass",
            "relations": [
                "RO:0002327"
            ],
            "count_by_source": {
                "infores:go": 6
            },
            "count": 6
        }
    ],
    "name": "Test Graph"
}
""",
                True
        )
,
        (
                """
{
    "not_a_field": {},
    "nodes": [],
    "edges": [],
    "name": "Empty Graph"
}
""",
                False,
        ),
    ],
)
def test_content_metadata_schema(query):
    metadata_json = json.loads(query[0])
    errors = validate_content_metadata(metadata_json)
    assert not errors == query[1]
