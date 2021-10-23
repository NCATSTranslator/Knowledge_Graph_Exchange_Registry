# coding: utf-8

import pytest
import json
from aiohttp import web

from kgea.server.archiver.models.process_file_set_body import ProcessFileSetBody


@pytest.mark.skip("application/x-www-form-urlencoded not supported by Connexion")
async def test_process_fileset(client):
    """Test case for process_fileset

    Posts a KGE File Set for post-processing after upload.
    """
    body = ProcessFileSetBody()
    headers = { 
        'Accept': 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    response = await client.request(
        method='POST',
        path='/archiver/process',
        headers=headers,
        json=body,
        )
    assert response.status == 200, 'Response body is : ' + (await response.read()).decode('utf-8')


async def test_get_processing_status(client):
    """Test case for get_processing_status

    Get the progress of post-processing of a KGE File Set.
    """
    params = [('process_token', 'process_token_example')]
    headers = {
        'Accept': 'application/json',
    }
    response = await client.request(
        method='GET',
        path='/archiver/status',
        headers=headers,
        params=params,
        )
    assert response.status == 200, 'Response body is : ' + (await response.read()).decode('utf-8')