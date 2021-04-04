from aiohttp import web

from ..kgea_handlers import  (
   kge_meta_knowledge_graph,
   download_kge_file_set
)


async def meta_knowledge_graph(request: web.Request, kg_id: str, kg_version: str) -> web.Response:
    """Meta knowledge graph representation of this KGX knowledge graph.

    :param request:
    :type request: web.Request
    :param kg_id: KGE File Set identifier for the knowledge graph for which graph metadata is being accessed.
    :type kg_id: str
    :param kg_version: Version of KGE File Set for a given knowledge graph.
    :type kg_version: str

    """
    return await kge_meta_knowledge_graph(request, kg_id, kg_version)


async def download_file_set(request: web.Request, kg_id, kg_version) -> web.Response:
    """Returns specified KGE File Set as a gzip compressed tar archive


    :param request:
    :type request: web.Request
    :param kg_id: KGE File Set identifier for the knowledge graph being accessed.
    :type kg_id: str
    :param kg_version: Version of KGE File Set of the knowledge graph being accessed.
    :type kg_version: str

    """
    return await download_kge_file_set(request, kg_id, kg_version)
