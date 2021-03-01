from aiohttp import web

from ..kgea_handlers import kge_knowledge_map


async def knowledge_map(request: web.Request, kg_name: str, session: str) -> web.Response:
    """Get supported relationships by source and target

    :param request:
    :type request: web.Request
    :param kg_name: Name label of KGE File Set, the knowledge graph for which content metadata is being accessed
    :type kg_name: str
    :param session: 
    :type session: str

    """
    return kge_knowledge_map(request, kg_name, session)
