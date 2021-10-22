# coding: utf-8

import sys
from setuptools import setup, find_packages

NAME = "archiver"
VERSION = "1.0.0"

# To install the library, run the following
#
# python setup.py install
#
# prerequisite: setuptools
# http://pypi.python.org/pypi/setuptools

REQUIRES = [
    "connexion==2.6.0",
    "swagger-ui-bundle==0.0.6",
    "aiohttp_jinja2==1.2.0",
]

setup(
    name=NAME,
    version=VERSION,
    description="OpenAPI for the Biomedical Translator Knowledge Graph EXchange Archiver worker process which post-processes KGE File Sets which have been uploaded. Although this API is SmartAPI compliant, it will not normally be visible in the Translator SmartAPI Registry since it is mainly meant to be only accessed internally by the KGE Archiver back end.",
    author_email="richard.bruskiewich@delphinai.com",
    url="",
    keywords=["OpenAPI", "OpenAPI for the Biomedical Translator Knowledge Graph EXchange Archiver worker process which post-processes KGE File Sets which have been uploaded. Although this API is SmartAPI compliant, it will not normally be visible in the Translator SmartAPI Registry since it is mainly meant to be only accessed internally by the KGE Archiver back end."],
    install_requires=REQUIRES,
    packages=find_packages(),
    package_data={'': ['openapi/openapi.yaml']},
    include_package_data=True,
    entry_points={
        'console_scripts': ['archiver=archiver.__main__:main']},
    long_description="""\
    OpenAPI for the NCATS Biomedical Translator Knowledge Graph Exchange Archiver Post-Processor
    """
)

