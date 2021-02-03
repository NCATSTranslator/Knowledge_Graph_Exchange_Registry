# coding: utf-8

from __future__ import absolute_import
import unittest

from ..test import BaseTestCase


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
            '/kge-archive/{kg_name}/access'.format(kg_name='your_gene_info'),
            method='GET',
            headers=headers)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))


if __name__ == '__main__':
    unittest.main()
