from typing import List, Dict
from aiohttp import web

from openapi_server import util


async def knowledge_map(request: web.Request, kg_name, session) -> web.Response:
    """Get supported relationships by source and target

    

    :param kg_name: Name label of KGE File Set, the knowledge graph for which content metadata is being accessed
    :type kg_name: str
    :param session: 
    :type session: str

    """
    return web.Response(status=200)
