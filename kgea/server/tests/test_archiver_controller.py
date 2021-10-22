# coding: utf-8

import pytest
import json
from aiohttp import web

from archiver.models.process_file_set_body import ProcessFileSetBody


@pytest.mark.skip("application/x-www-form-urlencoded not supported by Connexion")
async def test_process_fileset(client):
    """Test case for process_fileset

    Posts a KGE File Set for post-processing after upload.
    """
    body = archiver.ProcessFileSetBody()
    headers = { 
        'Accept': 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    response = await client.request(
        method='POST',
        path='/api/process',
        headers=headers,
        json=body,
        )
    assert response.status == 200, 'Response body is : ' + (await response.read()).decode('utf-8')

