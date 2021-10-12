#!/usr/bin/env bash
#
# Shell script for *nix command line driven
# archiving of a KGE File Set for downloading.
#
# Script performance constraints:
# ------------------------------
# NOTE: This script temporarily caches files from S3 onto the local hard drive, before tar'ing them.
# Thus, the local drive must be large enough to accommodate the largest file downloaded, plus
# space for the resulting tar file (which could be somewhat significant in size before gzip compression?)
#
gzip=gzip
# If multicore CPU's are available and compression speed is desired,
# the 'parallel gz' (pigz; https://zlib.net/pigz/) could be used
# gzip=pigz
#
# the --quiet switch suppresses AWS command output. Might wish to control this external to this script?
#
aws_flags=--quiet

# AWS command (can be tweaked if problematic, e.g. under Windows?)
if [[ "$OSTYPE" == "cygwin" ]]; then
        aws=$(which aws.cmd)
else
        aws=$(which aws)
fi

if [[ ! -f ${aws} ]]; then
  echo "Please install Amazon Web Service ('aws') CLI tools before running this script."
  exit 2
fi

usage () {
    echo
    echo "Usage:"
    echo
    echo "${0} <KGE Bucket> <KGE Root Directory> <Knowledge Graph Identifier> <File Set Version>"
#    exit -1  bash exits 0-255
    exit 1
}

if [[ -z "${1}" ]]; then
    usage
else
    # Archive Bucket
    kge_bucket=${1}
fi

if [[ -z "${2}" ]]; then
    usage
else
    # Root folder of all archives
    kge_root_directory=${2}
fi

if [[ -z "${3}" ]]; then
    usage
else
    # Knowledge Graph Identifier
    knowledge_graph=${3}
fi

if [[ -z "${4}" ]]; then
    usage
else
    # TODO: [perhaps need to validate proper SemVer format of file set version string here?
    # File Set Version of the Knowledge Graph
    version=${4}
fi

echo
echo "Beginning creation of tar.gz archive for file set version '$version' of '$knowledge_graph'"

# Folder of given versioned file set of the Knowledge Graph
file_set="${knowledge_graph}/${version}"

# Full S3 object key to the file set folder
s3="s3://${kge_bucket}/${kge_root_directory}/${file_set}/archive"

# File Set tar archive
tarfile="${knowledge_graph}_${version}.tar"

# echo Knowledge Graph File Set = $knowledge_graph $version
# echo s3 archive root = ${s3}
# echo archive = "${s3}/${tarfile.gz}"

output=( "provider.yaml" "file_set.yaml" "content_metadata.json" \
         "nodes.tsv" "edges.tsv" "nodes/nodes.tsv" "edges/edges.tsv")

# iterate over files
echo
echo Retrieve and tar files:

# shellcheck disable=SC2068
for file in ${output[@]};
do
  $aws s3 cp ${aws_flags} "${s3}/${file}" .
  if [ $? -eq 0 ] && [ -f "${file}" ]; then
     echo -n "- ${file}..."
     # use `rf` for tar to create if not exists,
     # append files if existing
     tar rf "${tarfile}" "${file}"
     echo "archived!"
     rm "${file}"
  else
     echo "${file} unavailable for archiving?"
  fi
done

## after archiving all of the files, compress them
echo Running ${gzip}
$gzip "${tarfile}"

## copy the new archive file to s3
echo Uploading "${s3}/${tarfile}.gz" archive
$aws s3 cp  ${aws_flags} "${tarfile}.gz" "$s3/${tarfile}.gz"

## cleanup the local copy of the tar.gz file
echo "Deleting ${tarfile}.gz"
rm "${tarfile}.gz"

echo
echo "Done creating tar.gz archive for file set version '${version}' of '${knowledge_graph}'"

# signal of success to other processes
exit 0;
