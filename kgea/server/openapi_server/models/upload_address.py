# coding: utf-8

from __future__ import absolute_import
from datetime import date, datetime  # noqa: F401

from typing import List, Dict  # noqa: F401

from openapi_server.models.base_model_ import Model
from openapi_server import util


class UploadAddress(Model):
    """NOTE: This class is auto generated by OpenAPI Generator (https://openapi-generator.tech).

    Do not edit the class manually.
    """

    def __init__(self, street=None, city=None):  # noqa: E501
        """UploadAddress - a model defined in OpenAPI

        :param street: The street of this UploadAddress.  # noqa: E501
        :type street: str
        :param city: The city of this UploadAddress.  # noqa: E501
        :type city: str
        """
        self.openapi_types = {
            'street': str,
            'city': str
        }

        self.attribute_map = {
            'street': 'street',
            'city': 'city'
        }

        self._street = street
        self._city = city

    @classmethod
    def from_dict(cls, dikt) -> 'UploadAddress':
        """Returns the dict as a model

        :param dikt: A dict.
        :type: dict
        :return: The _upload_address of this UploadAddress.  # noqa: E501
        :rtype: UploadAddress
        """
        return util.deserialize_model(dikt, cls)

    @property
    def street(self):
        """Gets the street of this UploadAddress.


        :return: The street of this UploadAddress.
        :rtype: str
        """
        return self._street

    @street.setter
    def street(self, street):
        """Sets the street of this UploadAddress.


        :param street: The street of this UploadAddress.
        :type street: str
        """

        self._street = street

    @property
    def city(self):
        """Gets the city of this UploadAddress.


        :return: The city of this UploadAddress.
        :rtype: str
        """
        return self._city

    @city.setter
    def city(self, city):
        """Sets the city of this UploadAddress.


        :param city: The city of this UploadAddress.
        :type city: str
        """

        self._city = city