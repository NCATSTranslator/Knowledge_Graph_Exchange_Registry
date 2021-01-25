import connexion
import six

from openapi_server import util
from .kge_handlers import kge_knowledge_map


def knowledge_map(kg_name):  # noqa: E501
    """Get supported relationships by source and target

     # noqa: E501

    :param kg_name: Name label of KGE File Set whose knowledge graph content metadata is being reported
    :type kg_name: str

    :rtype: Dict[str, Dict[str, List[str]]]
    """
    return kge_knowledge_map(kg_name)
