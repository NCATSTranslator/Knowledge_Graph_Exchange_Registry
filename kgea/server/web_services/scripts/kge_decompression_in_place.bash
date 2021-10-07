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
#    exit -1  bash exits 0-255
    exit 1
}

if [[ -z "${1}" ]]; then
    usage
else
    # KGE Bucket
    bucket="${1}"
fi

if [[ -z "${2}" ]]; then
    usage
else
    # Root directory of the KGE Knowledge Graphs
    root_directory="${2}"
fi

if [[ -z "${3}" ]]; then
    usage
else
    # Specific Knowledge Graph Identifier
    knowledge_graph=${3}
fi

if [[ -z "${4}" ]]; then
    usage
else
    # TODO: [perhaps need to validate proper SemVer format of file set version string here?
    # Specific File Set Version of interest for the Knowledge Graph
    version=${4}
fi

if [[ -z "${5}" ]]; then
    usage
else
    # Archive file name
    archive_filename="${5}"
fi

# Folder of given versioned file set of the Knowledge Graph
file_set="${knowledge_graph}/${version}"

# Full S3 object key to the file set folder
s3="s3://${bucket}/${root_directory}/${file_set}"

# Archive file to be extracted
archive_object_key=${s3}/${archive_filename}

echo
echo "Begin decompression-in-place of '${archive_object_key}'"

# To avoid collision in concurrent data operations across multiple graphs
# use a timestamped directory, instead of a simple literal subdirectory name
workdir=archive_$(date %s)
cd "${workdir}" || exit 3

# STEP 1 - download the tar.gz archive to the local working directory
$aws s3 cp "${aws_flags}" "${archive_object_key}" .

# STEP 2 - gunzip the archive
gz_file=$(ls *.gz)  # hopefully, just one file?
$gunzip "${gz_file}"

# STEP 3 - extract the tarfile for identification and later uploading
tar_file=$(ls *.tar)  # hopefully, just one file?
$tar xvf "${tar_file}"

parse_file () {
  file_type=''
  object_key="${1}/${2}"
  # problem: entry name file can be is nested. un-nest. Use os path to get the flat file name
  # unpacked_filename = basename(${1})
  #
  # if is_node_y (${1}):
  #    file_type="node"
  #    object_key = location + 'nodes/' + unpacked_filename
  # elif is_edge_y(${1}):
  #    file_type="edge"
  #    object_key = location + 'edges/' + unpacked_filename
  # elif is_metadata(${1}):
  #    file_type="metadata"
  #    object_key = location + unpacked_filename
  # else:
  #    file_type="unknown"
  #    object_key = location + unpacked_filename
  echo "${file_type},${object_key}"
}

# STEP 4 - for all archive files:
for file_name in *;
do
  #
  # STEP 4a - parse_file() applies the logic of the traversal_func() to extracted file entries
  #
  file_type_n_key=$(parse_file "${s3}" "${file_name}")
  IFS=',' read -ra file_data <<< "${file_type_n_key}"
  
  #
  # STEP 4b - Upload the resulting files back up to the target S3 location
  #
  echo "Uploading ${file_name} to ${file_data[1]}"
  $aws s3 cp  ${aws_flags} "${file_name}" "${file_data[1]}"
  
  #
  # STEP 4c - return the metadata about the uploaded (meta-)data files,
  #           back to the caller of the script, via STDOUT.
  # shellcheck disable=SC2012
  file_size=$(ls -lh "${file_name}" | awk '{print  $5}')
  echo "file_entry=${file_name},${file_size},${file_type_n_key}"
done

#
# STEP 7 - clean out the work directory
echo "Deleting working directory ${workdir}"
cd ..  # remember where you were just now...
rm -Rf "${workdir}"

echo
echo "Completed decompression-in-place of '${archive_object_key}'"

# signal of success to other processes
exit 0;
