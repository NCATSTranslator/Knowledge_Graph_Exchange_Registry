from aiohttp import web

from ..kgea_handlers import (
    get_kge_knowledge_graph_catalog,
    register_kge_knowledge_graph,
    publish_kge_file_set,
    kge_file_set_status
)


async def get_knowledge_graph_catalog(request: web.Request) -> web.Response:
    """Returns the catalog of available KGE File Sets

    :param request:
    :type request: web.Request
    """
    return await get_kge_knowledge_graph_catalog(request)


async def register_knowledge_graph(request: web.Request):
    """Register core parameters for the KGE File Set upload

    :param request:
    :type request: web.Request

    """
    # This method raises an obligatory web.HTTPFound
    # redirection exception to the /upload form
    await register_kge_knowledge_graph(request)


async def publish_file_set(request: web.Request, kg_id: str, kg_version: str):
    """Publish a registered File Set

    :param request:
    :type request: web.Request
    :param kg_id: KGE File Set identifier for the knowledge graph for which data files are being accessed.
    :type kg_id: str
    :param kg_version: KGE File Set identifier for the knowledge graph for which data files are being accessed.
    :type kg_version: str

    """
    # This method raises an obligatory web.HTTPFound
    # redirection exception back to /home page
    await publish_kge_file_set(request, kg_id, kg_version)


async def file_set_status(request: web.Request, kg_id: str, kg_version: str) -> web.Response:
    """Retrieve KGE File Set status

    :param kg_id: KGE Knowledge Graph identifier for the knowledge graph with a versioned KGE File Se for which status is required.
    :type kg_id: str
    :param kg_version: Version identifier of the KGE File Set for which status is required.
    :type kg_version: str

    """
    return await kge_file_set_status(request, kg_id, kg_version)
