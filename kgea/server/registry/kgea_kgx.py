"""
Knowledge Graph eXchange (KGX) tool kit validation of
Knowledge Graph Exchange (KGE) File Sets located on AWS S3
"""
from kgx.validator import Validator


class KgxValidator:
    
    def __init__(self):
        # singleton KGX validator for a given instance of
        # this class which should generally just be applied
        # to validate the data files of a single KGE File Set
        self.validator = Validator()
    
    async def validate_metadata(self, source) -> bool:
        if source:
            # use the self.validator ... maybe? or need something else for KGX metadata JSON?
            return True
        else:
            return False
    
    async def validate_data_file(self, source) -> bool:
        if source:
            # use the self.validator on the putative KGX file 'source'
            # parse in the source - which is likely an S3 signed URL(!?)
            # then validate it?
            return True
        else:
            return False
