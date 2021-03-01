from aiohttp import web

from ..kgea_handlers import kge_access


async def access(request: web.Request, kg_name: str, session: str) -> web.Response:
    """Get KGE File Sets

    :param request:
    :type request: web.Request
    :param kg_name: Name label of KGE File Set, the knowledge graph for which data files are being accessed
    :type kg_name: str
    :param session: 
    :type session: str

    """
    return await kge_access(request, kg_name, session)
