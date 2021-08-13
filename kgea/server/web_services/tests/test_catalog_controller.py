# coding: utf-8
import json
from typing import Dict

import pytest


async def test_get_knowledge_graph_catalog(client):
    """Test case for get_knowledge_graph_catalog

    Returns the catalog of available KGE File Sets
    """
    headers = { 
        'Accept': 'application/json',
    }
    response = await client.request(
        method='GET',
        path='/archive/catalog',
        headers=headers,
        )
    assert response.status == 200, 'Response body is : ' + (await response.read()).decode('utf-8')


async def test_publish_file_set(client):
    """Test case for publish_file_set

    Publish a registered File Set
    """
    headers = { 
    }
    response = await client.request(
        method='GET',
        path='/archive/publish/{kg_id}/{fileset_version}'.format(kg_id='kg_id_example', fileset_version='fileset_version_example'),
        headers=headers,
        )
    assert response.status == 200, 'Response body is : ' + (await response.read()).decode('utf-8')


@pytest.mark.skip("application/x-www-form-urlencoded not supported by Connexion")
async def test_register_file_set(client):
    """Test case for register_file_set

    Register core metadata for a distinctly versioned file set of a KGE Knowledge Graph
    """
    test_file_registration: Dict = dict()
    body = json.dumps(test_file_registration)
    headers = { 
        'Accept': 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    response = await client.request(
        method='POST',
        path='/archive/register/fileset',
        headers=headers,
        json=body,
        )
    assert response.status == 200, 'Response body is : ' + (await response.read()).decode('utf-8')


@pytest.mark.skip("application/x-www-form-urlencoded not supported by Connexion")
async def test_register_knowledge_graph(client):
    """Test case for register_knowledge_graph

    Register core metadata for a distinct KGE Knowledge Graph
    """
    test_kg_registration: Dict = dict()
    body = json.dumps(test_kg_registration)
    headers = { 
        'Accept': 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    response = await client.request(
        method='POST',
        path='/archive/register/graph',
        headers=headers,
        json=body,
        )
    assert response.status == 200, 'Response body is : ' + (await response.read()).decode('utf-8')

