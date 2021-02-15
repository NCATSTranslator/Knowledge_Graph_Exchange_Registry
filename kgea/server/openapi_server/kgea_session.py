# from flask import Flask, session
# from flask_session import Session
# from connexion import App
# from .kgea_config import resources
#
# SESSION_TYPE = 'filesystem'
# SESSION_COOKIE_DOMAIN = resources['oauth2']['site_uri']
# SESSION_COOKIE_NAME = 'KGE-Archive'
# App.config.from_object(__name__)
# Session(App)

from uuid import uuid4

_session = {}


def create_session() -> str:
    """
    Create a new session and return the session identifier.
    
    :return: str session key
    """
    session_id = str(uuid4())
    _session[session_id] = {1}
    return session_id


def valid_session(session_id: str) -> bool:
    """
    Validate a session identifier, return False if not valid
    
    :param session_id:
    :return: True if valid
    """
    if not session_id:
        return False
    return _session.get(session_id, False)


def get_session(session_id: str) -> dict:
    """
    Get a session context (dictionary) if available.
    Allows direct updating of the dictionary.

    :param session_id:
    :return: session dictionary if valid; empty dictionary otherwise
    """
    session = valid_session(session_id)
    if not session:
        return {}
    return session


def delete_session(session_id: str) -> bool:
    """
    Delete an active session if it exists.

    :param session_id:
    :return: True if active session detected and deleted, returns False otherwise
    """
    session = _session.get(session_id, False)
    if session:
        _session.pop(session_id)
        return True
    else:
        return False
