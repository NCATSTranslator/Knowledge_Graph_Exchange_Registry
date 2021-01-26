import connexion
import six

from openapi_server import util


def get_upload_form():  # noqa: E501
    """Get web form for specifying KGE File Set upload

     # noqa: E501


    :rtype: str
    """
    return 'do some magic!'


def upload_file_set(data_file_content):  # noqa: E501
    """Upload web form details specifying a KGE File Set upload process

     # noqa: E501

    :param data_file_content: 
    :type data_file_content: str

    :rtype: str
    """
    with data_file_content.stream as file:
        content = file.read()
        print(content)
    return "working on file"