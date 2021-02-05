# coding: utf-8

import pytest
import json
from aiohttp import web



async def test_knowledge_map(client):
    """Test case for knowledge_map

    Get supported relationships by source and target
    """
    params = [('session', 'session_example')]
    headers = { 
        'Accept': 'application/json',
    }
    response = await client.request(
        method='GET',
        path='/{kg_name}/knowledge_map'.format(kg_name='kg_name_example'),
        headers=headers,
        params=params,
        )
    assert response.status == 200, 'Response body is : ' + (await response.read()).decode('utf-8')

