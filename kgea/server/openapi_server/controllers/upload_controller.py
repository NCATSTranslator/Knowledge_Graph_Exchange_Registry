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


def upload_file_set(submitter, data_file, metadata_file=None):  # noqa: E501
    """upload_file_set

    Upload Web Form details specifying a KGE File Set upload process # noqa: E501

    :param submitter: 
    :type submitter: str
    :param data_file: 
    :type data_file: str
    :param metadata_file: 
    :type metadata_file: str

    :rtype: str
    """
    return upload_kge_file_set(submitter, data_file, metadata_file=None)
