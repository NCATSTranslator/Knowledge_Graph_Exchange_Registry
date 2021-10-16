#!/usr/bin/env bash
#
# Shell script for *nix command line driven
# Direct Transfer of a URL defined web resource, to AWS S3
#
# Note that script is generally agnostic with respect to KGX file type being transferred.
#
curl=$(which curl)
#aws_flags=--quiet
aws_flags=

usage () {
    echo
    echo "Usage:"
    echo
    echo "${0} <source url> <target object key>"
#    exit -1  bash exits 0-255
    exit 1
}

if [[ -z ${KGE_BUCKET} ]]; then
    echo
    echo "Please set the KGE_BUCKET environment variable"
    echo "(S3 bucket source where the target object key is located)"
#    exit -2  bash exits 0-255
    exit 2
fi

if [[ -z "${1}" ]]; then
    usage
else
    # Source url resource to be transferred
    url=${1}
fi

if [[ -z "${2}" ]]; then
    usage
else
    # Target object key in for input source
    object_key=${2}
fi

# AWS command (can be tweaked if problematic, e.g. under Windows?)
if [[ "${OSTYPE}" == "cygwin" ]]; then
        aws=$(which aws.cmd)
else
        aws=$(which aws)
fi

if [[ ! -f ${aws} ]]; then
  echo "Please install Amazon Web Service ('aws') CLI tools before running this script."
  exit 3
fi

if [[ ! -f ${curl} ]]; then
  echo "Please install 'curl' before running this script."
  exit 4
fi

echo
echo "Beginning direct transfer of '${url}' of '${object_key}' to '${KGE_BUCKET}'"

${curl} -L -s "${url}" | ${aws} s3 cp "${aws_flags}" - "s3://${KGE_BUCKET}/${object_key}"

echo
echo "Completed direct transfer of '${url}' of '${object_key}' to '${KGE_BUCKET}'"

# signal of success to other processes
exit 0;
