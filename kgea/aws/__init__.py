"""
AWS utility package
"""
import sys
from pathlib import Path
from typing import Optional, Dict


class Help:
    """
    Help class wrapper for KGE AWS utility modules.
    """
    def __init__(self, default_usage: str):
        self.default_usage = default_usage
        
    def usage(
            self,
            err_msg: str = '',
            command: str = '',
            args:  Optional[Dict] = None
    ):
        """
    
        :param err_msg:
        :param command:
        :param args:
        """
        if err_msg:
            print(f"{command} error: err_msg")
    
        if not command:
            cmd = " <operation>"
            description = self.default_usage
        else:
            cmd = f" {command}"
            description = ''
            for arg, desc in args.items():
                cmd += f" {arg}"
                description += f"\t{arg} is the {desc}\n"
                
        print(
            f"Usage:\n\npython -m kgea.aws.{Path(sys.argv[0]).stem}{cmd}\n\n" +
            "where:\n" +
            f"{description}\n"
    
        )
        exit(0)
