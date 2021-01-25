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
    

def upload_kge_file_set(formData):  # noqa: E501
    """Upload web form details specifying a KGE File Set upload process

     # noqa: E501

    :param form_data:
    :type form_data: dict | bytes

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

