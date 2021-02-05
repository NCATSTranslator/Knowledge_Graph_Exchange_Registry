from ..kgea_handlers import (
    get_kge_registration_form,
    get_kge_file_upload_form,
    register_kge_file_set,
    upload_kge_file_set
)


def get_registration_form(session, kg_name=None, submitter=None):  # noqa: E501
    """Prompt user for core parameters of the KGE File Set upload

     # noqa: E501

    :param session: 
    :type session: str
    :param kg_name: 
    :type kg_name: str
    :param submitter: 
    :type submitter: str

    :rtype: str
    """
    return get_kge_registration_form(session, kg_name, submitter)


def get_file_upload_form(session, submitter, kg_name):  # noqa: E501
    """Get web form for specifying KGE File Set upload

     # noqa: E501

    :param session:
    :type session: str
    :param submitter:
    :type submitter: str
    :param kg_name:
    :type kg_name: str

    :rtype: str
    """
    return get_kge_file_upload_form(session, submitter, kg_name)


def register_file_set(session, body):  # noqa: E501
    """Register core parameters for the KGE File Set upload

     # noqa: E501

    :param body:
    :type body: dict

    :rtype: str
    """
    return register_kge_file_set(body)


def upload_file_set(body):  # noqa: E501
    """Upload web form details specifying a KGE File Set upload process

     # noqa: E501

    :param body:
    :type body: dict

    :rtype: str
    """
    return upload_kge_file_set(body)
