from ..kgea_handlers import (
    kge_client_authentication,
    get_kge_home,
    kge_login,
    kge_logout
)


def client_authentication(code, state):  # noqa: E501
    """Process client authentication

     # noqa: E501

    :param code: 
    :type code: str
    :param state: 
    :type state: str

    :rtype: str
    """
    return kge_client_authentication(code, state)


def get_home(session=None):  # noqa: E501
    """Display home landing page

     # noqa: E501

    :param session: 
    :type session: str

    :rtype: str
    """
    return get_kge_home(session)


def login():  # noqa: E501
    """Process client user login

     # noqa: E501


    :rtype: None
    """
    return kge_login()


def logout(session=None):  # noqa: E501
    """Process client user logout

     # noqa: E501

    :param session: 
    :type session: str

    :rtype: None
    """
    return kge_logout(session)
