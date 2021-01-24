#!/usr/bin/env bash
SCRIPTS=`pwd`
CODE_GEN_CLI=$SCRIPTS/openapi-generator-cli.sh

# Script to (re-)generate the KGE Server, whenever the
# underlying api/kgea_api.yaml specification is modified.
#
# A SemVer major.minor.patch version identifier (e.g. 0.0.1)
# can be given as the first argument of the script.
#
#SPECIFICATION=$SCRIPTS/../api/trapi.yaml
SPECIFICATION=$SCRIPTS/../api/kgea_api.yaml

# Capture any project metadata likely to be overwritten
# by the code generation, e.g. package.json version?
# Using 'awk'?
VERSION=${1:-0.0.1}

# Note: the generator CLI parser does NOT properly parse spaces
# anywhere in the '--additional-properties' argument strings below.
# Use underscores or hyphens. You've been warned...
#
NAME="kge-archive"
DESCRIPTION="NCATS_Knowledge_Graph_Exchange_Archive_Web_Services"
MODULE="server"

$CODE_GEN_CLI generate \
   -g python \
   -i $SPECIFICATION \
   -o $MODULE \
   --additional-properties=projectName=$NAME,projectDescription=$DESCRIPTION,moduleName=$MODULE,projectVersion=$VERSION

#
# After code generation, the package.json has been overwritten again, thus I need to postprocess
# it to fix and restore a few elements, like the version and underscores in the name, e.g. using 'sed'?
#
# sed /pattern/ package.json.old | sed /pattern2/ ... | sed /pattern#/ >package.json.new
