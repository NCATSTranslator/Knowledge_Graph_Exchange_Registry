from aiohttp import web

from ..kgea_handlers import (
    get_kge_file_set_catalog,
    kge_access
)


async def access(request: web.Request, kg_id: str, version: str) -> web.Response:
    """Get KGE File Sets

    :param request:
    :type request: web.Request
    :param kg_id: Name label of KGE File Set, the knowledge graph for which data files are being accessed
    :type kg_id: str
    :param version: Version of the KGE File Set
    :type version: str

    """
    return await kge_access(request, kg_id, version)


async def get_file_set_catalog(request: web.Request) -> web.Response:
    """Returns the catalog of available KGE File Sets
    
    :param request:
    :type request: web.Request
    """
    return await get_kge_file_set_catalog(request)
