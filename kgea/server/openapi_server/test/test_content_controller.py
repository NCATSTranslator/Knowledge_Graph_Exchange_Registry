# coding: utf-8

from __future__ import absolute_import
import unittest

from flask import json
from six import BytesIO

from openapi_server.test import BaseTestCase


class TestContentController(BaseTestCase):
    """ContentController integration test stubs"""

    def test_kg_name_knowledge_map_get(self):
        """Test case for kg_name_knowledge_map_get

        Get supported relationships by source and target
        """
        headers = { 
            'Accept': 'application/json',
        }
        response = self.client.open(
            '/kge-archive/{kg_name}/knowledge_map'.format(kg_name='kg_name_example'),
            method='GET',
            headers=headers)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))


if __name__ == '__main__':
    unittest.main()
