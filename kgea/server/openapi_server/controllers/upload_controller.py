import connexion
import six

#from openapi_server.models.upload_form_data import UploadFormData  # noqa: E501
from openapi_server import util
from .kge_handlers import get_kge_upload_form, upload_kge_file_set

def get_upload_form():  # noqa: E501
    """Get web form for specifying KGE File Set upload

     # noqa: E501


    :rtype: str
    """
    return get_kge_upload_form()


def upload_file_set(form_data):  # noqa: E501
    """Upload web form details specifying a KGE File Set upload process

     # noqa: E501

    :param form_data: 
    :type form_data: dict | bytes

    :rtype: str
    """
    #if connexion.request.is_json:
    #    form_data = UploadFormData.from_dict(connexion.request.get_json())  # noqa: E501
    return upload_kge_file_set(form_data)
