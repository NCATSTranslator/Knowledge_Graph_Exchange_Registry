#####################################################
# General Utility Functions for the various servers #
#####################################################
import traceback
from sys import exc_info, stderr
from typing import Tuple, List
from subprocess import Popen, PIPE, STDOUT
import logging

logger = logging.getLogger(__name__)


#############################################
# General Utility Functions for this Module #
#############################################
async def run_script(
        script,
        args: Tuple = (),
        # env: Optional = None
        stdout_parser=None
) -> int:
    """
    Run a given script in the background, with specified arguments and environment variables.

    :param script: full OS path to the executable script.
    :param args: command line arguments for the script
    :param stdout_parser: (optional) single string argument function to parse lines piped back from stdout of the script
    :return: return code of the script
    """
    cmd: List = list()
    cmd.append(script)
    cmd.extend(args)

    logger.debug(f"run_script(cmd: '{cmd}')")
    try:
        with Popen(
                args=cmd,
                # env=env,
                bufsize=1,
                universal_newlines=True,
                stdout=PIPE,
                stderr=STDOUT
        ) as proc:
            logger.info(f"run_script({script}) log:")
            for line in proc.stdout:
                line = line.strip()
                if stdout_parser:
                    stdout_parser(line)
                logger.info(line)

    except RuntimeError:
        logger.error(f"run_script({script}) exception: {exc_info()}")
        return -1

    return proc.returncode


def print_error_trace(err_msg: str):
    """
    Print Error Exception stack
    """
    logger.error(err_msg)
    exc_type, exc_value, exc_traceback = exc_info()
    traceback.print_exception(exc_type, exc_value, exc_traceback, file=stderr)
