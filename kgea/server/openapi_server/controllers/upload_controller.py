import connexion
import six

from openapi_server import util

from .kge_handlers import (
    get_kge_register_form,
    get_kge_upload_form,
    register_kge_file_set,
    upload_kge_file_set,
)


def get_register_form(kg_name=None, submitter=None):  # noqa: E501
    """Get web form for specifying KGE File Set upload

     # noqa: E501

    :param kg_name: 
    :type kg_name: str
    :param submitter: 
    :type submitter: str

    :rtype: str
    """
    return get_kge_register_form(kg_name, submitter)


def get_upload_form(kg_name):  # noqa: E501
    """Get web form for specifying KGE File Set upload

     # noqa: E501

    :param kg_name: 
    :type kg_name: str

    :rtype: str
    """
    return get_kge_upload_form(kg_name)


def register_file_set(submitter, kg_name):  # noqa: E501
    """Register web form details specifying a KGE File Set location

     # noqa: E501

    :param submitter: 
    :type submitter: str
    :param kg_name: 
    :type kg_name: str

    :rtype: str
    """
    return register_kge_file_set(submitter, kg_name)


def upload_file_set(kg_name, data_file_content, data_file_metadata=None):  # noqa: E501
    """Upload web form details specifying a KGE File Set upload process

     # noqa: E501

    :param kg_name: 
    :type kg_name: str
    :param data_file_content: 
    :type data_file_content: str
    :param data_file_metadata: 
    :type data_file_metadata: str

    :rtype: str
    """
    return upload_kge_file_set(kg_name, data_file_content, data_file_metadata)
