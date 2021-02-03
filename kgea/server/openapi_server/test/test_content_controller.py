# coding: utf-8

from __future__ import absolute_import
import unittest

from ..test import BaseTestCase


class TestContentController(BaseTestCase):
    """ContentController integration test stubs"""

    def test_knowledge_map(self):
        """Test case for knowledge_map

        Get supported relationships by source and target
        """
        headers = { 
            'Accept': 'application/json',
        }
        response = self.client.open(
            '/kge-archive/{kg_name}/knowledge_map'.format(kg_name='your_gene_info'),
            method='GET',
            headers=headers)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))


if __name__ == '__main__':
    unittest.main()
