from aiohttp import web

from ..kgea_handlers import upload_kge_file


async def upload_file(
        request: web.Request,
        kg_id: str,
        kgx_file_content: str,
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
    :param kgx_file_content:
    :type kgx_file_content: str
    :param content_url:
    :type content_url: str
    :param uploaded_file:
    :type uploaded_file: FileField

    """
    return await upload_kge_file(
        request,
        kg_id=kg_id,
        kgx_file_content=kgx_file_content,
        upload_mode=upload_mode,
        content_name=content_name,
        content_url=content_url,
        uploaded_file=uploaded_file
    )
