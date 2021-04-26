# coding: utf-8

import pytest
import json
from aiohttp import web

from kgea.server.web_services.models.attribute import Attribute


async def test_access(client):
    """Test case for access

    Get KGE File Sets
    """
    params = [('session', 'session_example')]
    headers = { 
        'Accept': 'application/json',
    }
    response = await client.request(
        method='GET',
        path='/{kg_name}/access'.format(kg_name='kg_name_example'),
        headers=headers,
        params=params,
        )
    assert response.status == 200, 'Response body is : ' + (await response.read()).decode('utf-8')

