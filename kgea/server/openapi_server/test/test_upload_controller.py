# coding: utf-8

from __future__ import absolute_import
import unittest

from ..test import BaseTestCase


class TestUploadController(BaseTestCase):
    """UploadController integration test stubs"""

    def test_get_upload_form(self):
        """Test case for get_upload_form

        Get web form for specifying KGE File Set upload
        """
        headers = { 
            'Accept': 'text/html',
        }
        response = self.client.open(
            '/kge-archive/upload',
            method='GET',
            headers=headers)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    @unittest.skip("multipart/form-data not supported by Connexion")
    def test_upload_file_set(self):
        """Test case for upload_file_set

        Upload web form details specifying a KGE File Set upload process
        """
        headers = { 
            'Accept': 'application/json',
            'Content-Type': 'multipart/form-data',
        }
        response = self.client.open(
            '/kge-archive/upload',
            method='POST',
            headers=headers,
            content_type='multipart/form-data')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))


if __name__ == '__main__':
    unittest.main()
