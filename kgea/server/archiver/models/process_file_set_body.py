"""
Process File Set Body
"""
from typing import List

from kgea.server.archiver.models.base_model_ import Model
from kgea.server.archiver.models.kge_archived_file_set import KgeArchivedFileSet
from kgea.server.archiver import util


class ProcessFileSetBody(Model):
    
    def __init__(self, kg_id: str = None,  fileset: KgeArchivedFileSet = None):
        """ProcessFileSetBody - a model defined in OpenAPI

        :param kg_id: The Knowledge Graph Identifier submitted by this ProcessFileSetBody.
        :param fileset: The fileset of this ProcessFileSetBody.
        """
        self.openapi_types = {
            'kg_id': str,
            'fileset': KgeArchivedFileSet
        }

        self.attribute_map = {
            'kg_id': 'kg_id',
            'fileset': 'fileset'
        }

        self._kg_id = kg_id
        self._fileset = fileset

    @classmethod
    def from_dict(cls, dikt: dict) -> 'ProcessFileSetBody':
        """Returns the dict as a model

        :param dikt: A dict.
        :return: The ProcessFileSetBody of this object.
        """
        return util.deserialize_model(dikt, cls)

    @property
    def kg_id(self):
        """Gets the Knowledge Graph Identifier submitted by this ProcessFileSetBody.

        Knowledge Graph identifier ('kg_id')

        :return: The kg_id of this ProcessFileSetBody.
        :rtype: str
        """
        return self._kg_id

    @kg_id.setter
    def kg_id(self, kg_id):
        """Sets the kg_id of this ProcessFileSetBody.

        Knowledge Graph identifier ('kg_id')

        :param kg_id: The Knowledge Graph Identifier submitted by this ProcessFileSetBody.
        :type kg_id: str
        """

        self._kg_id = kg_id

    @property
    def fileset(self):
        """Gets the fileset of this ProcessFileSetBody.

        Metadata of a KGE File Set

        :return: The fileset of this ProcessFileSetBody.
        :rtype: List[str]
        """
        return self._fileset

    @fileset.setter
    def fileset(self, fileset):
        """Sets the fileset of this ProcessFileSetBody.

        Metadata of a KGE File Set

        :param fileset: The fileset of this ProcessFileSetBody.
        :type fileset: List[str]
        """

        self._fileset = fileset

    def to_json(self):
        """
        Serialize the ProcessFileSetBody as a JSON blob
        """
        # return "{}"
        raise NotImplemented
