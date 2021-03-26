from aiohttp import web

from ..kgea_handlers import kge_access


async def access(request: web.Request, kg_id: str) -> web.Response:
    """Get KGE File Sets

    :param request:
    :type request: web.Request
    :param kg_id: Name label of KGE File Set, the knowledge graph for which data files are being accessed
    :type kg_id: str

    """
    return await kge_access(request, kg_id)
