"""
Shared module to manage Archiver process status
"""
import threading
from typing import Dict

from kgea.server.archiver.models import ProcessStatusCode

_process_status: Dict[str, ProcessStatusCode] = dict()


async def set_process_status(process_token: str, status: ProcessStatusCode):
    lock = threading.Lock()
    with lock:
        _process_status[process_token] = status


def get_process_status(process_token: str) -> ProcessStatusCode:
    if not process_token:
        return ProcessStatusCode.UNKNOWN
    return _process_status.setdefault(process_token, ProcessStatusCode.UNKNOWN)
