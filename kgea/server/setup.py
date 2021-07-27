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
    # TODO: temporary patched version of KGX for proper streaming of files for validation
    "swagger-web_ui-bundle==0.0.6",
    "aiohttp_jinja2==1.2.0",
    "jsonschema<3.0.0",
    "multidict",
    "jinja2 == 2.11.3",
    "aiohttp_cors >= 0.7.0",
    # KGE specific
    "botocore<1.21.0,>=1.20.12",
    "boto3 >= 1.17.0",
    "s3-tar",
    "pyyaml",
    "aiohttp<3.7",
    "aiohttp-session",
    "aiomcache",
    "jsonschema",
    "PyGithub"
]

setup(
    name=NAME,
    version=VERSION,
    description="OpenAPI for the Biomedical Translator Knowledge Graph EXchange Archive. Although this API is SmartAPI compliant, it will not normally be visible in the Translator SmartAPI Registry since it is mainly meant to be accessed through Registry indexed KGE File Sets, which will have distinct entries in the Registry.",
    author_email="richard.bruskiewich@delphinai.com",
    url="",
    keywords=["OpenAPI", "OpenAPI for the Biomedical Translator Knowledge Graph EXchange Archive. Although this API is SmartAPI compliant, it will not normally be visible in the Translator SmartAPI Registry since it is mainly meant to be accessed through Registry indexed KGE File Sets, which will have distinct entries in the Registry."],
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
