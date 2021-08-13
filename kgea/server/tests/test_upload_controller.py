# coding: utf-8

import pytest
import json
from aiohttp import web
from aiohttp import FormData

from web_services.models.upload_progress_token import UploadProgressToken
from web_services.models.upload_request_body import UploadRequestBody
from web_services.models.upload_token_object import UploadTokenObject


async def test_get_upload_status(client):
    """Test case for get_upload_status

    Get the progress of uploading for a specific file of a KGE File Set.
    """
    params = [('upload_token', 'upload_token_example')]
    headers = { 
        'Accept': 'application/json',
    }
    response = await client.request(
        method='GET',
        path='/archive/upload/progress',
        headers=headers,
        params=params,
        )
    assert response.status == 200, 'Response body is : ' + (await response.read()).decode('utf-8')


async def test_setup_upload_context(client):
    """Test case for setup_upload_context

    Configure upload context for a specific file of a KGE File Set.
    """
    params = [('kg_id', 'kg_id_example'),
                    ('fileset_version', 'fileset_version_example'),
                    ('kgx_file_content', 'kgx_file_content_example'),
                    ('upload_mode', 'upload_mode_example'),
                    ('content_name', 'content_name_example'),
                    ('content_url', 'content_url_example')]
    headers = { 
        'Accept': 'application/json',
    }
    response = await client.request(
        method='GET',
        path='/archive/upload',
        headers=headers,
        params=params,
        )
    assert response.status == 200, 'Response body is : ' + (await response.read()).decode('utf-8')


@pytest.mark.skip("multipart/form-data not supported by Connexion")
async def test_upload_file(client):
    """Test case for upload_file

    Uploading of a specified file from a local computer.
    """
    body = web_services.UploadRequestBody()
    headers = { 
        'Accept': 'application/json',
        'Content-Type': 'multipart/form-data',
    }
    response = await client.request(
        method='POST',
        path='/archive/upload',
        headers=headers,
        json=body,
        )
    assert response.status == 200, 'Response body is : ' + (await response.read()).decode('utf-8')

