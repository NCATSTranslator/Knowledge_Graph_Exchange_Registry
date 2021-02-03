import connexion
import six

from openapi_server import util

from openapi_server.kgea_handlers import get_kge_home


def get_home():  # noqa: E501
    """Get default landing page

     # noqa: E501


    :rtype: str
    """
    return get_kge_home()
