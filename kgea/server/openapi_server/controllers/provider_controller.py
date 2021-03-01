from typing import List, Dict
from aiohttp import web

from openapi_server.models.attribute import Attribute
from openapi_server import util


async def access(request: web.Request, kg_name, session) -> web.Response:
    """Get KGE File Sets

    

    :param kg_name: Name label of KGE File Set, the knowledge graph for which data files are being accessed
    :type kg_name: str
    :param session: 
    :type session: str

    """
    return web.Response(status=200)
