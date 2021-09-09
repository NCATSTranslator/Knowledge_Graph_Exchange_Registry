from aiohttp import web

from ..kgea_handlers import (
    setup_kge_upload_context,
    kge_transfer_from_url,
    get_kge_upload_status,
    upload_kge_file
)


async def setup_upload_context(
        request: web.Request,
        kg_id: str,
        fileset_version: str,
        kgx_file_content: str,
        content_name: str
) -> web.Response:
    """Configure form upload context for a specific file of a KGE File Set.

    Uploading of (meta-)data files to a specific KGE File Set version, belonging to a specified Knowledge Graph.
    The files are assumed to be html form file &quot;blob&quot; objects. The &#39;get&#39; only sets up the
    file uploading (with progress indications). A follow-up HTTP POST call to the /upload endpoint is expected,
    with the &#39;upload token&#39; returned from this call and an &#39;uploaded_file&#39; parameter set to the
    file to be uploaded.  The &#39;content_name&#39; should be set either to the file name. The specific
    KGX file content of the current upload file is set by the &#x60;kgx_file_content&#39; for KGX data files
    uploaded as set by the selected &#39;metadata&#39;, &#39;nodes&#39; or &#39;edges&#39; radio button.

    :param request:
    :type request: web.Request
    :param kg_id: KGE File Set identifier for the knowledge graph for which data file metadata are being accessed
    :type kg_id: str
    :param fileset_version: Specific version of KGE File Set for the knowledge graph for which data file metadata are being accessed
    :type fileset_version: str
    :param kgx_file_content: Tags the upload as either &#39;metadata&#39;, &#39;nodes&#39;, &#39;edges&#39; or &#39;archive&#39;.
    :type kgx_file_content: str
    :param content_name: The file name of the data set to be uploaded.
    :type content_name: str
    :rtype: web.Response
    """
    return await setup_kge_upload_context(
        request, kg_id, fileset_version, kgx_file_content, content_name
    )


async def kge_transfer_from_url(
        request: web.Request,
        kg_id: str,
        fileset_version: str,
        kgx_file_content: str,
        content_url: str,
        content_name: str
) -> web.Response:
    """Trigger direct URL file transfer of a specific file of a KGE File Set.

    Direct file from URL transfer of (meta-)data files to a specific KGE File Set version, belonging to a
    specific Knowledge Graph. The &#39;content_url&#39; parameter is taken as a REST endpoint of a file
    to be transferred into the Archive (http authentication not yet supported, therefore, the URL should
    provide for unauthenticated access). The &#39;content_name&#39; is set the file name to be assigned
    to the file within the KGE Archive. The specific KGX file content of the current upload file is set
    by the &#x60;kgx_file_content&#39; for KGX data files uploaded as set by the selected &#39;metadata&#39;,
    &#39;nodes&#39; or &#39;edges&#39; radio button.

    :param request:
    :type request: web.Request
    :param kg_id: KGE File Set identifier for the knowledge graph for which data file metadata are being accessed
    :type kg_id: str
    :param fileset_version: Specific version of KGE File Set for the knowledge graph for which data file metadata are being accessed
    :type fileset_version: str
    :param kgx_file_content: Tags the upload as either &#39;metadata&#39;, &#39;nodes&#39;, &#39;edges&#39; or &#39;archive&#39;.
    :type kgx_file_content: str
    :param content_url: (Optional) URL to a web based file resource to be directly uploaded to the KGE Archive from it&#39;s server.
    :type content_url: str
    :param content_name: The file name of the data set to be uploaded.
    :type content_name: str

    """
    return await kge_transfer_from_url(
        request, kg_id, fileset_version, kgx_file_content, content_url, content_name
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
