from flask import session
from flask.ext.session import Session

from uuid import uuid4

from connexion import App
from .kgea_config import resources

SESSION_TYPE = 'filesystem'
SESSION_COOKIE_DOMAIN = resources['oauth2']['site_uri']
SESSION_COOKIE_NAME = 'KGE-Archive'
Session(App)


def create_session() -> str:
    """
    Create a new session and return the session identifier.
    
    :return: str session key
    """
    session_id = str(uuid4())
    session[session_id] = {1}
    return session_id


def valid_session(session_id: str) -> bool:
    """
    Validate a session identifier, return False if not valid
    
    :param session_id:
    :return: True if valid
    """
    return session.get(session_id, False)


def delete_session(session_id: str):
    if session.get(session_id, False):
        session.pop(session_id)
