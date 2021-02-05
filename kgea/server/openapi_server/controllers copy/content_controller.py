from ..kgea_handlers import kge_knowledge_map


def knowledge_map(kg_name, session):  # noqa: E501
    """Get supported relationships by source and target

     # noqa: E501

    :param kg_name: Name label of KGE File Set, the knowledge graph for which content metadata is being accessed
    :type kg_name: str
    :param session: 
    :type session: str

    :rtype: Dict[str, Dict[str, List[str]]]
    """
    return kge_knowledge_map(kg_name, session)
