from aiohttp import web

from ..kgea_handlers import kge_meta_knowledge_graph


async def meta_knowledge_graph(request: web.Request, kg_name: str) -> web.Response:
    """Meta knowledge graph representation of this KGX knowledge graph.

    :param request:
    :type request: web.Request
    :param kg_name: KGE File Set identifier for the knowledge graph for which data files are being accessed.
    :type kg_name: str

    """
    return await kge_meta_knowledge_graph(request, kg_name)