from ..kgea_handlers import (
    kge_client_authentication,
    kge_login,
    kge_logout,
    get_kge_landing_page,
    get_kge_home
)


def client_authentication(code):  # noqa: E501
    """Process client authentication

     # noqa: E501

    :param code: 
    :type code: str

    :rtype: str
    """
    return kge_client_authentication(code)


def get_home(session):  # noqa: E501
    """Get main home page for logged in user

     # noqa: E501

    :param session: 
    :type session: str

    :rtype: str
    """
    return get_kge_home(session)


def get_landing_page(session=None):  # noqa: E501
    """Get default public landing page (when the site visitor is not authenticated)

     # noqa: E501

    :param session: 
    :type session: str

    :rtype: str
    """
    return get_kge_landing_page(session)


def login():  # noqa: E501
    """Process client user login

     # noqa: E501

    :rtype: None
    """
    return kge_login()


def logout():  # noqa: E501
    """Process client user logout

     # noqa: E501

    :rtype: None
    """
    return kge_logout()
