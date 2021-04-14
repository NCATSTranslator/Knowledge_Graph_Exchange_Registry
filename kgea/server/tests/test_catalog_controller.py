# coding: utf-8

import pytest
import json
from aiohttp import web

from web_services.models.kge_file_set_entry import KgeFileSetEntry


async def test_get_file_set_catalog(client):
    """Test case for get_file_set_catalog

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
        path='/archive/publish/{kg_id}'.format(kg_id='kg_id_example'),
        headers=headers,
        )
    assert response.status == 200, 'Response body is : ' + (await response.read()).decode('utf-8')


@pytest.mark.skip("application/x-www-form-urlencoded not supported by Connexion")
async def test_register_file_set(client):
    """Test case for register_file_set

    Register core parameters for the KGE File Set upload
    """
    headers = { 
        'Accept': 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    data = {
        'kg_name': 'kg_name_example',
        'kg_description': 'kg_description_example',
        'submitter': 'submitter_example',
        'submitter_email': 'submitter_email_example',
        'translator_component': 'translator_component_example',
        'translator_team': 'translator_team_example',
        'license_name': 'license_name_example',
        'license_url': 'license_url_example',
        'terms_of_service': 'terms_of_service_example'
        }
    response = await client.request(
        method='POST',
        path='/archive/register',
        headers=headers,
        data=data,
        )
    assert response.status == 200, 'Response body is : ' + (await response.read()).decode('utf-8')

