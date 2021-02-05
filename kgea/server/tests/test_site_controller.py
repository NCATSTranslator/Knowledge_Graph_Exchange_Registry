# coding: utf-8

import pytest
import json
from aiohttp import web



async def test_client_authentication(client):
    """Test case for client_authentication

    Process client authentication
    """
    params = [('code', 'code_example'),
                    ('state', 'state_example')]
    headers = { 
        'Accept': 'text/html',
    }
    response = await client.request(
        method='GET',
        path='/oauth2callback',
        headers=headers,
        params=params,
        )
    assert response.status == 200, 'Response body is : ' + (await response.read()).decode('utf-8')


async def test_get_home(client):
    """Test case for get_home

    Display home landing page
    """
    params = [('session', 'session_example')]
    headers = { 
        'Accept': 'text/html',
    }
    response = await client.request(
        method='GET',
        path='/home',
        headers=headers,
        params=params,
        )
    assert response.status == 200, 'Response body is : ' + (await response.read()).decode('utf-8')


async def test_login(client):
    """Test case for login

    Process client user login
    """
    headers = { 
    }
    response = await client.request(
        method='GET',
        path='/login',
        headers=headers,
        )
    assert response.status == 200, 'Response body is : ' + (await response.read()).decode('utf-8')


async def test_logout(client):
    """Test case for logout

    Process client user logout
    """
    params = [('session', 'session_example')]
    headers = { 
    }
    response = await client.request(
        method='GET',
        path='/logout',
        headers=headers,
        params=params,
        )
    assert response.status == 200, 'Response body is : ' + (await response.read()).decode('utf-8')

