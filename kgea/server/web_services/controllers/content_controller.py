from aiohttp import web

from ..kgea_handlers import (
    get_kge_file_set_contents,
    kge_meta_knowledge_graph,
    download_kge_file_set
)


async def get_file_set_contents(request: web.Request, kg_id: str, kg_version: str) -> web.Response:
    """Get file list and details for a given KGE File Set version.

    :param request:
    :type request: web.Request
    :param kg_id: KGE File Set identifier for the knowledge graph for which data file metadata are being accessed
    :type kg_id: str
    :param kg_version: Specific version of KGE File Set for the knowledge graph for which metadata are being accessed
    :type kg_version: str

    """
    return await get_kge_file_set_contents(request, kg_id, kg_version)


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


async def download_file_set(request: web.Request, kg_id, kg_version):
    """Returns specified KGE File Set as a gzip compressed tar archive

    :param request:
    :type request: web.Request
    :param kg_id: KGE File Set identifier for the knowledge graph being accessed.
    :type kg_id: str
    :param kg_version: Version of KGE File Set of the knowledge graph being accessed.
    :type kg_version: str

    :return: None - redirection responses triggered
    """
    await download_kge_file_set(request, kg_id, kg_version)
