import connexion
import six

from openapi_server import util


def knowledge_map(kg_name):  # noqa: E501
    """Get supported relationships by source and target

     # noqa: E501

    :param kg_name: Name label of KGE File Set whose knowledge graph content metadata is being reported
    :type kg_name: str

    :rtype: Dict[str, Dict[str, List[str]]]
    """
    # TODO: deserializing KGX files?
    object_location = Template('$DIRECTORY_NAME/$KG_NAME/$SUBFOLDER/').substitute(
        DIRECTORY_NAME='kge-data', 
        KG_NAME=kg_name,
        SUBFOLDER='metadata'
    )
    return 'do some magic!'
