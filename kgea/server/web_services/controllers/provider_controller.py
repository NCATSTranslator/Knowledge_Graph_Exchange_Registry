from aiohttp import web

from ..kgea_handlers import  (
    kge_access,
    get_kge_file_set_catalog,
)


async def access(request: web.Request, kg_id: str) -> web.Response:
    """Get KGE File Set provider metadata.

    :param request:
    :type request: web.Request
    :param kg_id: KGE File Set identifier for the knowledge graph for which data files are being accessed
    :type kg_id: str

    """
    return await kge_access(request, kg_id)


async def get_file_set_catalog(request: web.Request) -> web.Response:
    """Returns the catalog of available KGE File Sets
    
    :param request:
    :type request: web.Request
    """
    return await get_kge_file_set_catalog(request)
