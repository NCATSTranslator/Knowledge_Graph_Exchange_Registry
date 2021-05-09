from aiohttp import web

from ..kgea_handlers import (
    get_kge_knowledge_graph_catalog,
    register_kge_knowledge_graph,
    register_kge_file_set,
    publish_kge_file_set
)


async def get_knowledge_graph_catalog(request: web.Request) -> web.Response:
    """Returns the catalog of available KGE File Sets

    :param request:
    :type request: web.Request
    """
    return await get_kge_knowledge_graph_catalog(request)


async def register_knowledge_graph(request: web.Request):
    """Register core metadata for a distinct KGE Knowledge Graph

    Register core metadata for a new KGE persisted Knowledge Graph. Since this endpoint assumes assumes a web session authenticated user, this user is automatically designated as the &#39;owner&#39; of the new KGE graph.

    :param request:
    :type request: web.Request

    """
    # This method raises an obligatory web.HTTPFound
    # redirection exception to the /register/graph form
    await register_kge_knowledge_graph(request)


async def register_file_set(request: web.Request):
    """Register core metadata for a distinctly versioned file set of a KGE Knowledge Graph

    Register core metadata for a newly persisted file set version of a KGE persisted Knowledge Graph. Since this endpoint assumes a web session authenticated session user, this user is automatically designated as the &#39;owner&#39; of the new versioned file set.

    :param request:
    :type request: web.Request

    """
    # This method raises an obligatory web.HTTPFound
    # redirection exception to the /register/fileset form
    await register_kge_file_set(request)


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

