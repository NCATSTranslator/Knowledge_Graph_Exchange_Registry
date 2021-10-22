# coding: utf-8

import pytest
import json
from aiohttp import web

from archiver.models.status_token import StatusToken


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
        path='/api/status',
        headers=headers,
        params=params,
        )
    assert response.status == 200, 'Response body is : ' + (await response.read()).decode('utf-8')

