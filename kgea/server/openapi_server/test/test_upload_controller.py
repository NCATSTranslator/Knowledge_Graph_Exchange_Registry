# coding: utf-8

from __future__ import absolute_import
import unittest

from flask import json
from six import BytesIO

from openapi_server.test import BaseTestCase


class TestUploadController(BaseTestCase):
    """UploadController integration test stubs"""

    def test_upload(self):
        """Test case for upload

        Get KGE File Sets
        """
        headers = { 
            'Accept': 'application/html',
        }
        response = self.client.open(
            '/kge-archive/upload',
            method='GET',
            headers=headers)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))


if __name__ == '__main__':
    unittest.main()
