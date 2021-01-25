import connexion
import six

from openapi_server import util

from kge_handlers import kge_upload

def upload():  # noqa: E501
    """Get KGE File Sets

     # noqa: E501


    :rtype: str
    """
    return kge_upload()
