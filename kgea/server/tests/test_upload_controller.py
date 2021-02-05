# coding: utf-8

import pytest
import json
from aiohttp import web
from aiohttp import FormData



async def test_get_registration_form(client):
    """Test case for get_registration_form

    Prompt user for core parameters of the KGE File Set upload
    """
    params = [('session', 'session_example')]
    headers = { 
        'Accept': 'text/html',
    }
    response = await client.request(
        method='GET',
        path='/register',
        headers=headers,
        params=params,
        )
    assert response.status == 200, 'Response body is : ' + (await response.read()).decode('utf-8')


async def test_get_upload_form(client):
    """Test case for get_upload_form

    Get web form for specifying KGE File Set upload
    """
    params = [('session', 'session_example')]
    headers = { 
        'Accept': 'text/html',
    }
    response = await client.request(
        method='GET',
        path='/upload_form/{kg_name}'.format(kg_name='kg_name_example'),
        headers=headers,
        params=params,
        )
    assert response.status == 200, 'Response body is : ' + (await response.read()).decode('utf-8')


@pytest.mark.skip("application/x-www-form-urlencoded not supported by Connexion")
async def test_register_file_set(client):
    """Test case for register_file_set

    Register core parameters for the KGE File Set upload
    """
    params = [('session', 'session_example')]
    headers = { 
        'Accept': 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    data = {
        'submitter': 'submitter_example',
        'kg_name': 'kg_name_example'
        }
    response = await client.request(
        method='POST',
        path='/register',
        headers=headers,
        data=data,
        params=params,
        )
    assert response.status == 200, 'Response body is : ' + (await response.read()).decode('utf-8')


@pytest.mark.skip("multipart/form-data not supported by Connexion")
async def test_upload_file_set(client):
    """Test case for upload_file_set

    Upload web form details specifying a KGE File Set upload process
    """
    params = [('session', 'session_example')]
    headers = { 
        'Accept': 'application/json',
        'Content-Type': 'multipart/form-data',
    }
    data = FormData()
    data.add_field('data_file_content', (BytesIO(b'some file data'), 'file.txt'))
    data.add_field('data_file_metadata', (BytesIO(b'some file data'), 'file.txt'))
    response = await client.request(
        method='POST',
        path='/upload/{kg_name}'.format(kg_name='kg_name_example'),
        headers=headers,
        data=data,
        params=params,
        )
    assert response.status == 200, 'Response body is : ' + (await response.read()).decode('utf-8')

