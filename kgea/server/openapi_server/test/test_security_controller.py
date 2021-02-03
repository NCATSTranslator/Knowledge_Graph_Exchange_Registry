# coding: utf-8

from __future__ import absolute_import
import unittest

from ..test import BaseTestCase


class TestSecurityController(BaseTestCase):
    """SecurityController integration test stubs"""

    def test_client_authentication(self):
        """Test case for client_authentication

        Process client authentication
        """
        query_string = [('code', 'code_example')]
        headers = { 
            'Accept': 'text/html',
        }
        response = self.client.open(
            '/kge-archive/oauth2callback',
            method='GET',
            headers=headers,
            query_string=query_string)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_login(self):
        """Test case for login

        Process client user login
        """
        headers = { 
        }
        response = self.client.open(
            '/kge-archive/login',
            method='GET',
            headers=headers)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_logout(self):
        """Test case for logout

        Process client user logout
        """
        headers = { 
        }
        response = self.client.open(
            '/kge-archive/logout',
            method='GET',
            headers=headers)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))


if __name__ == '__main__':
    unittest.main()
