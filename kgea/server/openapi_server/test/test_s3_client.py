# coding: utf-8

from __future__ import absolute_import
import unittest

from ..test import BaseTestCase

import boto3

class S3Client(BaseTestCase):
    """SiteController integration test stubs"""

    def test_validate_configure(self):
        """Test case for ~/.aws/config
        """
        print('test configure', boto3) 


    def test_validate_credentials(self):
        """Test case for ~/.aws/credentials
        """
        print('test credentials') 


if __name__ == '__main__':
    unittest.main()
