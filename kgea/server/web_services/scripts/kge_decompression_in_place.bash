#!/usr/bin/env bash
#
# Shell script for *nix command line driven
# decompression-in-place of an uploaded KGX dataset.
#
# Script performance constraints:
# ------------------------------
# NOTE: This script uses the local filing system
# to manipulate archive files downloaded from S3.
# Thus, the local drive must be large enough to accommodate
# all extracted files of the contents of the downloaded archive.
#
gunzip=$(which gunzip)
#
# If multicore CPU's are available and compression speed is desired,
# the 'parallel gz' (pigz; https://zlib.net/pigz/) could be used.
# However, do confirm which command flags are needed here??
#
# gunzip=$(which pigz)
#

# TAR command
tar=$(which tar)

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
    echo "$0 <bucket> <root directory> <kg_id> <fileset version> <subdirectory> <archive_filename>"
    echo
#    exit -1  bash exits 0-255
    exit 1
}

if [[ -z "${1}" ]]; then
    echo "Specify S3 bucket for operation!"
    usage
else
    # KGE Bucket
    bucket="${1}"
    echo "Bucket: ${bucket}"
fi

if [[ -z "${2}" ]]; then
    echo "Specify root data directory in S3 bucket for operation!"
    usage
else
    # Root directory of the KGE Knowledge Graphs
    root_directory="${2}"
    echo "Root directory: ${root_directory}"
fi

if [[ -z "${3}" ]]; then
    echo "Specify knowledge graph id for operation!"
    usage
else
    # Specific Knowledge Graph Identifier
    kg_id=${3}
    echo "Knowledge Graph Id: ${kg_id}"
fi

if [[ -z "${4}" ]]; then
    echo "Specify file set version for operation!"
    usage
else
    # TODO: [perhaps need to validate proper SemVer format of file set version string here?
    # Specific File Set Version of interest for the Knowledge Graph
    file_set_version=${4}
    echo "File Set Version: ${file_set_version}"
fi

if [[ -z "${5}" ]]; then
    echo "Specify target archive file name for operation!"
    usage
else
    # Archive file name
    archive_filename="${5}"
    echo "Archive file name: ${archive_filename}"
fi

# Folder of given versioned file set of the Knowledge Graph
file_set_key_path="${kg_id}/${file_set_version}"
echo "File Set Key Path: ${file_set_key_path}"

# Full S3 object key to the file set folder
s3_uri="s3://${bucket}/${root_directory}/${file_set_key_path}"
echo "S3 URI: ${s3_uri}"

# Archive file to be extracted
archive_object_key="${s3_uri}/${archive_filename}"

echo
echo "Begin decompression-in-place of '${archive_object_key}'"

# To avoid collision in concurrent data operations across multiple graphs
# use a timestamped directory, instead of a simple literal subdirectory name
workdir=archive_$(date +%s)
mkdir "${workdir}"
cd "${workdir}" || exit 3

# STEP 1 - download the tar.gz archive to the local working directory
$aws s3 cp "${aws_flags}" "${archive_object_key}" .

exit 100

# STEP 2 - gunzip the archive
gz_file=$(ls *.gz)  # hopefully, just one file?
echo "${gunzip}" "${gz_file}"

# STEP 3 - extract the tarfile for identification and later uploading
tar_file=$(ls *.tar)  # hopefully, just one file?
echo "${tar}" xvf "${tar_file}"

file_typed_object_key () {
  if [[ "${1}" =~ node[s]?.tsv ]];
  then
    object_key="nodes/${1}"
  elif [[ "${1}" =~ nodes/ ]];
  then
    object_key="${1}" ;
  elif [[ "${1}" =~ edge[s]?.tsv ]];
  then
    object_key="edges/${1}" ;
  elif [[ "${1}" =~ edges/ ]];
  then
    object_key="${1}" ;
  elif [[ "${1}" =~ content_metadata\.json ]];
  then
    object_key="metadata/content_metadata.json" ;
  elif [[ "${1}" =~ content_metadata\.json || "${1}" =~ metadata/ ]];
  then
    object_key="metadata/${1}" ;
  else
    object_key="${1}";
  fi
  echo "${object_key}"
}

# STEP 4 - for all archive files:
for file_path in *;
do
  echo "file_path: ${file_path}"

  # File name may at the end of the file path
  file_name=$(basename "${file_path}")

  #
  # STEP 4a - file_typed_object_key() heuristically assigns
  #           the object key for various file types
  #
  file_object_key=$(file_typed_object_key "${file_path}")
  echo "file_object_key: ${file_object_key}"

  # DON'T NEED RIGHT NOW.. BUT JUST KEEPING AROUND AS A CLUE ON HOW TO SPLIT A STRING IN BASH...
  #  IFS=',' read -ra file_data <<< "${file_object_key}"

  #
  # STEP 4b - Upload the resulting files back up to the target S3 location
  #
  echo "Uploading ${file_path} to ${file_object_key}"
  echo "${aws}" s3 cp "${aws_flags}" "${file_path}" "${file_object_key}"
  
  #
  # STEP 4c - return the metadata about the uploaded (meta-)data files,
  #           back to the caller of the script, via STDOUT.
  # shellcheck disable=SC2012
  file_size=$(ls -lh "${file_path}" | awk '{print  $5}')
  echo "file_entry=${file_name},${file_path},${file_size},${file_object_key}"
done

#
# STEP 7 - clean out the work directory
echo "Deleting working directory ${workdir}"
cd ..  # remember where you were just now...
echo rm -Rf "${workdir}"

echo
echo "Completed decompression-in-place of '${archive_object_key}'"

# signal of success to other processes
exit 0;
