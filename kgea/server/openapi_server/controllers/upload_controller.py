from ..kgea_handlers import (
    get_kge_registration_form,
    get_kge_upload_form,
    register_kge_file_set,
    upload_kge_file_set,
)


def get_registration_form(session):  # noqa: E501
    """Prompt user for core parameters of the KGE File Set upload

     # noqa: E501

    :param session: 
    :type session: str

    :rtype: str
    """
    return get_kge_registration_form(session)


def get_upload_form(kg_name, session):  # noqa: E501
    """Get web form for specifying KGE File Set upload

     # noqa: E501

    :param kg_name: 
    :type kg_name: str
    :param session: 
    :type session: str

    :rtype: str
    """
    return get_kge_upload_form(kg_name, session)


def register_file_set( body
        # session=None, submitter=None, kg_name=None, **kwargs
    ):  # noqa: E501
    """Register core parameters for the KGE File Set upload

     # noqa: E501

    :param session: 
    :type session: str
    :param submitter: 
    :type submitter: str
    :param kg_name: 
    :type kg_name: str

    :rtype: str
    """
    return register_kge_file_set(
        # session, submitter, kg_name, **kwargs
    )


def upload_file_set(kg_name=None, session=None, data_file_content=None, data_file_metadata=None):  # noqa: E501
    """Upload web form details specifying a KGE File Set upload process

     # noqa: E501

    :param kg_name: 
    :type kg_name: str
    :param session: 
    :type session: str
    :param data_file_content: 
    :type data_file_content: str
    :param data_file_metadata: 
    :type data_file_metadata: str

    :rtype: str
    """
    return upload_kge_file_set(kg_name, session, data_file_content, data_file_metadata)
