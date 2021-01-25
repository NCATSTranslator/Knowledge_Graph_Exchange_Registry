import connexion
import six

from openapi_server import util
from .kge_handlers import get_kge_upload_form, upload_kge_file_set


def get_upload_form():  # noqa: E501
    """get_upload_form

    Get Web Form for specifying KGE File Set upload # noqa: E501


    :rtype: str
    """
    return get_kge_upload_form()


def upload_file_set(submitter, kg_name, data_file_name, metadata_file_name=None):  # noqa: E501
    """upload_file_set

    Upload Web Form details specifying a KGE File Set upload process # noqa: E501

    :param submitter: 
    :type submitter: str
    :param kg_name: 
    :type kg_name: str
    :param data_file_name: 
    :type data_file_name: str
    :param metadata_file_name: 
    :type metadata_file_name: str

    :rtype: str
    """
    return upload_kge_file_set(submitter, kg_name, data_file_name, metadata_file_name)
