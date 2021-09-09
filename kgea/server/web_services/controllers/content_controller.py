from aiohttp import web

from ..kgea_handlers import (
    get_kge_file_set_metadata,
    kge_meta_knowledge_graph,
    download_kge_file_set_archive,
    download_kge_file_set_archive_sha1hash
)


async def get_file_set_metadata(request: web.Request, kg_id: str, fileset_version: str) -> web.Response:
    """Get file list and details for a given KGE File Set version.

    :param request:
    :type request: web.Request
    :param kg_id: KGE File Set identifier for the knowledge graph for which data file metadata are being accessed
    :type kg_id: str
    :param fileset_version: Specific version of KGE File Set for the knowledge graph for which metadata are being accessed
    :type fileset_version: str

    """
    return await get_kge_file_set_metadata(request, kg_id, fileset_version)


async def meta_knowledge_graph(
        request: web.Request,
        kg_id: str,
        fileset_version: str,
        downloading: bool = True
) -> web.Response:
    """Meta knowledge graph representation of this KGX knowledge graph.

    :param request:
    :type request: web.Request
    :param kg_id: KGE File Set identifier for the knowledge graph for which graph metadata is being accessed.
    :type kg_id: str
    :param fileset_version: Version of KGE File Set for a given knowledge graph.
    :type fileset_version: str
    :param downloading: Boolean flag indicating whether data is to be downloaded as an attachment or rather if a signed URL (string) is to be returned to the caller, for direct access to the data file (default: true).
    :type downloading: bool

    """
    return await kge_meta_knowledge_graph(request, kg_id, fileset_version, downloading)


async def download_file_set_archive(request: web.Request, kg_id: str, fileset_version: str):
    """Returns specified KGE File Set as a gzip compressed tar archive

    :param request:
    :type request: web.Request
    :param kg_id: Identifier of the knowledge graph of the KGE File Set a file set version for which is being accessed.
    :type kg_id: str
    :param fileset_version: Version of file set of the knowledge graph being accessed.
    :type fileset_version: str

    :return: None - redirection responses triggered
    """
    await download_kge_file_set_archive(request, kg_id, fileset_version)


async def download_file_set_archive_sha1hash(request: web.Request, kg_id, fileset_version):
    """Returns SHA1 hash of the current KGE File Set as a small text file.

    :param request:
    :type request: web.Request
    :param kg_id: Identifier of the knowledge graph of the KGE File Set a file set version for which is being accessed.
    :type kg_id: str
    :param fileset_version: Version of file set of the knowledge graph being accessed.
    :type fileset_version: str

    :return: None - redirection responses triggered
    """
    await download_kge_file_set_archive_sha1hash(request, kg_id, fileset_version)
