"""
Knowledge Graph eXchange (KGX) tool kit validation of
Knowledge Graph Exchange (KGE) File Sets located on AWS S3
"""
from typing import List, Optional
from sys import stderr
from os import getenv

import logging

from kgx.transformer import Transformer
from kgx.validator import Validator

logger = logging.getLogger(__name__)
DEBUG = getenv('DEV_MODE', default=False)
if DEBUG:
    logger.setLevel(logging.DEBUG)


class KgxValidator:
    
    def __init__(self):
        self.validator = Validator()
    
    @staticmethod
    def validate_content_metadata(file_path) -> List:
        # TODO: Stub implementation of metadata validator
        if file_path:
            # use the self.validator ... maybe? or need something else for KGX metadata JSON?
            return []
        else:
            return ["No file name provided - nothing to validate"]
    
    async def validate_data_file(
            self,
            file_path: str,
            input_format: str = 'tsv',
            input_compression: Optional[str] = None,
            output: Optional[str] = None
    ) -> List:
        """
        Validates KGX compliance of a specified data file.
        
        :param file_path: string specification of a single file path (may be a resolvable URL?)
        :param input_format: currently restricted to 'tsv' (its default?)
        :param input_compression: currently expected to be 'tar.gz' or 'gz'
        :param output: default None
        :return: (possibly empty) List of errors returned
        """
        
        if file_path:
            # The putative KGX file 'source' is currently sitting at the end
            # of an S3 signed URL(!?) for streaming into the validation.

            transformer = Transformer(stream=True)
            
            transformer.transform(
                {
                    'filename': [file_path],
                    'format': input_format,
                    'compression': input_compression
                }
            )

            errors = self.validator.validate(transformer.store.graph)
            
            if errors:
                if output:
                    self.validator.write_report(errors, open(output, 'w'))
                else:
                    if DEBUG:
                        self.validator.write_report(errors, stderr)

            return errors
        
        else:
            return ["Empty file source"]
