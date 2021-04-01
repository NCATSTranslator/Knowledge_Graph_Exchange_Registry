from aiohttp import web

from ..kgea_handlers import (
    register_kge_file_set,
    upload_kge_file,
    publish_kge_file_set
)


async def register_file_set(request: web.Request):
    """Register core parameters for the KGE File Set upload

    :param request:
    :type request: web.Request

    """
    # This method raises an obligatory web.HTTPFound
    # redirection exception to the /upload form
    await register_kge_file_set(request)


async def upload_file(
        request: web.Request,
        kg_id: str,
        upload_mode: str,
        content_name: str,
        content_url: str = None,
        uploaded_file=None
) -> web.Response:
    """Upload processing of KGE File Set file

    :param request:
    :type request: web.Request
    :param kg_id:
    :type kg_id: str
    :param upload_mode:
    :type upload_mode: str
    :param content_name:
    :type content_name: str
    :param content_url:
    :type content_url: str
    :param uploaded_file:
    :type uploaded_file: FileField

    """
    return await upload_kge_file(
        request,
        kg_id,
        upload_mode,
        content_name,
        content_url,
        uploaded_file
    )


async def publish_file_set(request: web.Request, kg_id):
    """Publish a registered File Set

    :param request:
    :type request: web.Request
    :param kg_id: KGE File Set identifier for the knowledge graph for which data files are being accessed.
    :type kg_id: str

    """
    # This method raises an obligatory web.HTTPFound
    # redirection exception back to /home page
    await publish_kge_file_set(request, kg_id)
