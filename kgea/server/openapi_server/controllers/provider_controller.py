import connexion
import six

from openapi_server.models.attribute import Attribute  # noqa: E501
from openapi_server import util

from openapi_server.kge_handlers import kge_access

def access(kg_name):  # noqa: E501
    """Get KGE File Sets

     # noqa: E501

    :param kg_name: Name label of KGE File Set whose files are being accessed
    :type kg_name: str

    :rtype: Dict[str, Attribute]
    """
    return kge_access(kg_name)
