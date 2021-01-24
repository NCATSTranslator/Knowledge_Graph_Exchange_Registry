#!/usr/bin/env bash
#
# Script to (re-)generate the KGE Server, whenever the
# underlying api/kgea_api.yaml specification is modified.
#

# Note: the generator CLI parser does NOT properly parse spaces
# anywhere in the '--additional-properties' argument strings below.
# Use underscores or hyphens. You've been warned...
#
echo
NAME="kge-archive"
echo "Project name: "$NAME

DESCRIPTION="NCATS_Knowledge_Graph_Exchange_Archive_Web_Services"
echo "Project description: "$DESCRIPTION
echo

# Identify your location of script execution
# Assume it to be the project 'root' directory
PROJECT=`pwd`
echo "The root of all (project) evils: "$PROJECT

SCRIPTS=$PROJECT/scripts
echo "Scripts are here: "$SCRIPTS
CODE_GEN_CLI=$SCRIPTS/openapi-generator-cli.sh

API=$PROJECT/api
#SPECIFICATION=$API/trapi.yaml
SPECIFICATION=$API/kgea_api.yaml
echo "Target OpenAPI: "$SPECIFICATION

SRC=$PROJECT/kgea
echo "Project source code is here: "$SRC

# Server code placed in its own KGEA subdirectory?
MODULE="server"
OUTPUT=$SRC/$MODULE
echo "Generated "$MODULE" code: "$OUTPUT

#
# A SemVer major.minor.patch version identifier (e.g. 0.0.1)
# can be given as the first argument of the script.
#
VERSION=${1:-0.0.1}
echo "Target version is: "$VERSION
echo

read -p "Continue (yes/no - default 'no'): " YESNO

if [[ ! $YESNO = "yes" ]]; then
   echo "Sorry to see you leave... Good bye!";
   exit
else
  echo "OK, here we go!...";
fi

# Capture HERE any project metadata, from the previously generated code base,
# likely to be overwritten by the fresh code generation, e.g. package version?
# Maybe can use '(g)awk' to capture?

$CODE_GEN_CLI generate \
   -g python-flask \
   -i $SPECIFICATION \
   -o $OUTPUT \
   --additional-properties=projectName=$NAME,projectDescription=$DESCRIPTION,moduleName=$MODULE,projectVersion=$VERSION

#
# After code generation, the package.json has been overwritten again,
# thus HERE I need to postprocess the generated code to fix and restore
# a few elements, like the version and underscores in the name,
#
# Perhaps use 'sed', i.e.?
#
# sed /pattern/ {generated code file} | sed /pattern2/ ... | sed /pattern#/ >{fixed code file}
