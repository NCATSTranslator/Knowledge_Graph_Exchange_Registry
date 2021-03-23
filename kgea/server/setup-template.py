# coding: utf-8

from setuptools import setup, find_packages

NAME = "web_services"
VERSION = "1.0.0"

# To install the library, run the following
#
# python setup.py install
#
# prerequisite: setuptools
# http://pypi.python.org/pypi/setuptools

REQUIRES = [
    # TODO: fix temporary Patched version of Connexion for proper 'application/x-www-form-urlencoded' support
    "connexion @ git+https://github.com/STARInformatics/connexion.git#egg=connexion",
    "swagger-web_ui-bundle==0.0.6",
    "aiohttp_jinja2==1.2.0",
    "jsonschema<3.0.0"
]

setup(
    name=NAME,
    version=VERSION,
    description="OpenAPI for the NCATS Biomedical Translator Knowledge Graph EXchange (KGE) Archive",
    author_email="richard.bruskiewich@delphinai.com",
    url="",
    keywords=["OpenAPI", "OpenAPI for the NCATS Biomedical Translator Knowledge Graph EXchange (KGE) Archive"],
    install_requires=REQUIRES,
    packages=find_packages(),
    package_data={'': ['openapi/openapi.yaml']},
    include_package_data=True,
    entry_points={
        'console_scripts': ['web_services=web_services.__main__:main']},
    long_description="""\
    OpenAPI for the NCATS Biomedical Translator Knowledge Graph Exchange Archive
    """
)

