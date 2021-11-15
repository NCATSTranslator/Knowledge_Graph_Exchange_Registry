"""
Shared module to manage Archiver process status
"""
import threading
from typing import Dict

from kgea.server.archiver.models import ProcessStatus, ProcessStatusCode

_process_status: Dict[str, ProcessStatus] = dict()


async def init_process_status(
        kg_id: str,
        fileset_version: str,
        process_token: str,
        status: ProcessStatusCode
):
    """
    Sets the assigned to a post-processing task identified by the process_token.
    
    :param kg_id: knowledge graph identifier of the KGE File Set being processed
    :param fileset_version: SemVer version of the KGE File Set being processed
    :param process_token: string token previously assigned to a post-processing task
    :param status: current ProcessStatusCode to be associated with the process_token
    """
    process_status: ProcessStatus = ProcessStatus(
        process_token=process_token,
        kg_id=kg_id,
        fileset_version=fileset_version,
        status=status
    )
    lock = threading.Lock()
    with lock:
        _process_status[process_token] = process_status


async def set_process_status(
        process_token: str,
        status: ProcessStatusCode
):
    """
    Resets the ProcessStatusCode of the post-processing task identified by the process_token.

    :param process_token: string token previously assigned to a post-processing task
    :param status: current ProcessStatusCode to be associated with the task
    """
    lock = threading.Lock()
    with lock:
        _process_status[process_token].status = status


def get_process_status(process_token: str) -> ProcessStatus:
    """
    Archiver handler returning process status associated with
    a given process (if it exists and is active or complete)
    
    :param process_token: string token previously assigned to a post-processing task
    :return: ProcessStatusCode associated with the process_token
    """
    if not process_token:
        raise RuntimeError("kge_archiver_status.get_process_status(): empty process_token?")
    else:
        try:
            process_status: ProcessStatus = _process_status[process_token]
        except KeyError:
            # fail gracefully if an unregistered process_token is encountered
            return ProcessStatus(
                process_token=process_token,
                kg_id="unknown",
                fileset_version="",
                status=ProcessStatusCode.UNKNOWN
            )

    return process_status
