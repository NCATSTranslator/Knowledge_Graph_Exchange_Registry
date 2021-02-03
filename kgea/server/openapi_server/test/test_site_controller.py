# coding: utf-8

from __future__ import absolute_import
import unittest

from ..test import BaseTestCase


class TestSiteController(BaseTestCase):
    """SiteController integration test stubs"""

    def test_get_home(self):
        """Test case for get_home

        Get default landing page
        """
        headers = { 
            'Accept': 'text/html',
        }
        response = self.client.open(
            '/kge-archive/',
            method='GET',
            headers=headers)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))


if __name__ == '__main__':
    unittest.main()
