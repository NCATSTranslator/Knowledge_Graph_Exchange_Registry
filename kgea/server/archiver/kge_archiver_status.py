"""
Shared module to manage Archiver process status
"""
import threading
from typing import Dict

from kgea.server.archiver.models import ProcessStatusCode

_process_status: Dict[str, ProcessStatusCode] = dict()


async def set_process_status(process_token: str, status: ProcessStatusCode):
    """
    Sets the assigned to a post-processing task identified by the process_token.
    
    :param process_token: string token previously assigned to a post-processing task
    :param status: current ProcessStatusCode to be associated with the process_token
    """
    lock = threading.Lock()
    with lock:
        _process_status[process_token] = status


def get_process_status(process_token: str) -> ProcessStatusCode:
    """
    Archiver handler returning process status associated with
    a given process (if it exists and is active or complete)
    
    :param process_token: string token previously assigned to a post-processing task
    :return: ProcessStatusCode associated with the process_token
    """
    if not process_token:
        return ProcessStatusCode.UNKNOWN
    return _process_status.setdefault(process_token, ProcessStatusCode.UNKNOWN)
