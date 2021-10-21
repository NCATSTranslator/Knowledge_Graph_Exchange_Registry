# coding: utf-8

from kgea.config import BACKEND_PATH


async def test_download_file_set(client):
    """Test case for download_file_set

    Returns specified KGE File Set as a gzip compressed tar archive
    """
    headers = { 
        'Accept': 'application/json',
    }
    response = await client.request(
        method='GET',
        path=f'/{path}{kg_id}/{fileset_version}/download'.format(
            path=BACKEND_PATH, kg_id='kg_id_example', fileset_version='fileset_version_example'
        ),
        headers=headers,
        )
    assert response.status == 200, 'Response body is : ' + (await response.read()).decode('utf-8')


async def test_get_file_set_metadata(client):
    """Test case for get_file_set_metadata

    Get provider and content metadata for a specified KGE File Set version.
    """
    headers = { 
        'Accept': 'application/json',
    }
    response = await client.request(
        method='GET',
        path=f'/{path}{kg_id}/{fileset_version}/metadata'.format(
            path=BACKEND_PATH, kg_id='kg_id_example', fileset_version='fileset_version_example'
        ),
        headers=headers,
        )
    assert response.status == 200, 'Response body is : ' + (await response.read()).decode('utf-8')


async def test_meta_knowledge_graph(client):
    """Test case for meta_knowledge_graph

    Meta knowledge graph representation of this KGX knowledge graph.
    """
    params = [('downloading', True)]
    headers = { 
        'Accept': 'application/json',
    }
    response = await client.request(
        method='GET',
        path='/{path}{kg_id}/{fileset_version}/meta_knowledge_graph'.format(
            path=BACKEND_PATH, kg_id='kg_id_example', fileset_version='fileset_version_example'
        ),
        headers=headers,
        params=params,
        )
    assert response.status == 200, 'Response body is : ' + (await response.read()).decode('utf-8')

