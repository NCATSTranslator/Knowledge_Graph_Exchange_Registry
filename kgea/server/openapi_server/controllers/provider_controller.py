from ..kgea_handlers import kge_access


def access(kg_name, session):  # noqa: E501
    """Get KGE File Sets

     # noqa: E501

    :param kg_name: Name label of KGE File Set, the knowledge graph for which data files are being accessed
    :type kg_name: str
    :param session: 
    :type session: str

    :rtype: Dict[str, Attribute]
    """
    return kge_access(kg_name, session)
