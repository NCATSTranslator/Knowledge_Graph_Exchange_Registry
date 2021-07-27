from aiohttp import web

from ..kgea_handlers import (
    setup_kge_upload_context,
    get_kge_upload_status,
    upload_kge_file
)


async def setup_upload_context(
        request: web.Request,
        kg_id: str,
        fileset_version: str,
        kgx_file_content: str,
        upload_mode: str,
        content_name: str,
        content_url: str = None
) -> web.Response:
    """Configure upload context for a specific file of a KGE File Set.

    Uploading of (meta-)data files to a specific KGE File Set version, belonging to a specific Knowledge Graph.
    The &#39;upload_mode&#39; argument specifies the upload mode as either &#39;content_from_local_file&#39;
    or &#39;content_from_url&#39;. If &#39;content_from_local_file&#39; is indicated, then a follow-up HTTP POST
    call to the /upload endpoint is expected, with the token returned from this call and an &#39;uploaded_file&#39;
    parameter set to the file to be uploaded. If &#39;upload_mode&#39; is set to &#39;content_from_url&#39; then
    the &#39;content_url&#39; parameter is taken as a REST endpoint of the file to be transferred into the Archive
    (authentication is not yet supported - URL should provide unauthenticated access). The &#39;content_name&#39;
    should be set either to the file name of the &#39;content_from_local_file&#39;, or url transfers, set by inference
    or as specified by the caller (especially if the &#39;content_url&#39; doesn&#39;t resolve to a definitive
    file name). The specific KGX file content of the current upload file is set by the &#x60;kgx_file_content&#39;
    for KGX data files uploaded in the &#39;content_from_local_file&#39; or &#39;content_from_url&#39; modes set
    by the selected &#39;nodes&#39; versus &#39;edges&#39; radio button.

    :param request:
    :type request: web.Request
    :param kg_id: KGE File Set identifier for the knowledge graph for which data file metadata are being accessed
    :type kg_id: str
    :param fileset_version: Specific version of KGE File Set for the knowledge graph for which data file metadata are being accessed
    :type fileset_version: str
    :param kgx_file_content: Tags the upload as either &#39;metadata&#39;, &#39;nodes&#39;, &#39;edges&#39; or &#39;archive&#39;.
    :type kgx_file_content: str
    :param upload_mode: Specifies the upload mode as either &#39;content_from_local_file&#39; or &#39;content_from_url&#39;
    :type upload_mode: str
    :param content_name: The file name of the data set to be uploaded.
    :type content_name: str
    :param content_url: (Optional) URL to a web based file resource to be directly uploaded to the KGE Archive from it&#39;s server.
    :type content_url: str
    :rtype: web.Response
    """
    return await setup_kge_upload_context(
        request, kg_id, fileset_version, kgx_file_content, upload_mode, content_name, content_url
    )


async def get_upload_status(request: web.Request, upload_token: str) -> web.Response:
    """Get the progress of uploading for a specific file of a KGE File Set.

    Poll the status of a given upload process.

    :param request:
    :type request: web.Request
    :param upload_token: Upload token associated with a given file for uploading to the Archive as specified by a preceding /upload GET call.
    :type upload_token: str
    :rtype: web.Response

    """
    return await get_kge_upload_status(request, upload_token)


async def upload_file(
        request: web.Request,
        upload_token,
        uploaded_file
) -> web.Response:
    """Uploading of a specified file from a local computer.

    :param request:
    :type request: web.Request
    :param upload_token: Upload token associated with a given file for Archive uploading as specified by a preceding /upload GET call.
    :type upload_token: str
    :param uploaded_file: File (blob) object to be uploaded.
    :type uploaded_file: str
    :rtype: web.Response

    """
    return await upload_kge_file(
        request,
        upload_token=upload_token,
        uploaded_file=uploaded_file
    )
