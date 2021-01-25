"""
Knowledge Graph Exchange Archive
Web form and service handler logic
"""

from flask import render_template


def get_kge_upload_form():  # noqa: E501
    """Get KGE File Sets

     # noqa: E501

    :rtype: str
    """
    return render_template('upload.html')
    

def upload_kge_file_set(submitter, data_file, metadata_file=None):  # noqa: E501
    """upload_file_set

    Upload Web Form details specifying a KGE File Set upload process # noqa: E501

    :param submitter:
    :type submitter: str
    :param data_file:
    :type data_file: str
    :param metadata_file:
    :type metadata_file: str

    :rtype: str
    """
    return "Implement me!"


def kge_access(kg_name):  # noqa: E501
    """Get KGE File Sets

     # noqa: E501

    :param kg_name: Name label of KGE File Set whose files are being accessed
    :type kg_name: str

    :rtype: Dict[str, Attribute]
    """
    return "Implement me!"


def kge_knowledge_map(kg_name):  # noqa: E501
    """Get supported relationships by source and target

     # noqa: E501

    :param kg_name: Name label of KGE File Set whose knowledge graph content metadata is being reported
    :type kg_name: str

    :rtype: Dict[str, Dict[str, List[str]]]
    """
    return "Implement me!"

