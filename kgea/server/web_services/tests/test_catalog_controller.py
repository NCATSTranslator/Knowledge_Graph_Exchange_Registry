# coding: utf-8

import pytest
from kgea.config import BACKEND_PATH


async def test_get_knowledge_graph_catalog(client):
    """Test case for get_knowledge_graph_catalog

    Returns the catalog of available KGE File Sets
    """
    headers = { 
        'Accept': 'application/json',
    }
    response = await client.request(
        method='GET',
        path=f'/{BACKEND_PATH}catalog',
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
        path='/{path}publish/{kg_id}/{fileset_version}'.format(
            path=BACKEND_PATH, kg_id='kg_id_example', fileset_version='fileset_version_example'
        ),
        headers=headers,
        )
    assert response.status == 200, 'Response body is : ' + (await response.read()).decode('utf-8')


@pytest.mark.skip("application/x-www-form-urlencoded not supported by Connexion")
async def test_register_file_set(client):
    """Test case for register_file_set

    Register core metadata for a distinctly versioned file set of a KGE Knowledge Graph
    """
    body = "web_services.RegisterFileSetRequestBody()"
    headers = { 
        'Accept': 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    response = await client.request(
        method='POST',
        path=f'/{BACKEND_PATH}register/fileset',
        headers=headers,
        json=body,
        )
    assert response.status == 200, 'Response body is : ' + (await response.read()).decode('utf-8')


@pytest.mark.skip("application/x-www-form-urlencoded not supported by Connexion")
async def test_register_knowledge_graph(client):
    """Test case for register_knowledge_graph

    Register core metadata for a distinct KGE Knowledge Graph
    """
    body = "web_services.RegisterGraphRequestBody()"
    headers = { 
        'Accept': 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    response = await client.request(
        method='POST',
        path=f'/{BACKEND_PATH}register/graph',
        headers=headers,
        json=body,
        )
    assert response.status == 200, 'Response body is : ' + (await response.read()).decode('utf-8')

