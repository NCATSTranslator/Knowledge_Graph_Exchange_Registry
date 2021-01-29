# coding: utf-8

from __future__ import absolute_import
import unittest

from flask import json
from six import BytesIO

from openapi_server.models.attribute import Attribute  # noqa: E501
from openapi_server.test import BaseTestCase


class TestProviderController(BaseTestCase):
    """ProviderController integration test stubs"""

    def test_access(self):
        """Test case for access

        Get KGE File Sets
        """
        headers = { 
            'Accept': 'application/json',
        }
        response = self.client.open(
            '/kge-archive/{kg_name}/access'.format(kg_name='kg_name_example'),
            method='GET',
            headers=headers)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))


if __name__ == '__main__':
    unittest.main()
