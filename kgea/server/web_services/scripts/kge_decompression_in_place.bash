#!/usr/bin/env bash
#
# Shell script for *nix command line driven
# decompression-in-place of an uploaded KGX dataset.
#
# Script performance constraints:
# ------------------------------
# NOTE: This script uses the local filing system to manipulate archive files downloaded from S3.
# Thus, the local drive must be large enough to accommodate the largest file downloaded.
#
gzip=gzip
# If multicore CPU's are available and compression speed is desired,
# the 'parallel gz' (pigz; https://zlib.net/pigz/) could be used
# gzip=pigz
#
# the --quiet switch suppresses AWS command output. Might wish to control this external to this script?
#
aws_flags=--quiet

usage () {
    echo
    echo "Usage:"
    echo
    echo "$0 <archive_location> <target_location>"
#    exit -1  bash exits 0-255
    exit 1
}

if [[ -z "$1" ]]; then
    usage
else
    # Source key for archive
    archive_location=$1
fi

if [[ -z "$2" ]]; then
    usage
else
    # Target location for files
    target_location=$2
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

echo
echo "Beginning decompression-in-place of '$archive_location'"

# STEP 1 - download the archive to disk
# STEP 2 - unzip the archive
# STEP 3 -

  #     def traversal_func_kgx(tf, location):
  #        """
  #        :param tf:
  #        :param location:
  #        :return:
  #        """
  #        logger.debug('traversal_func_kgx(): Begin traversing across the archive for nodes and edge files', tf)
  #        file_entries = []
  #        for entry in tf:  # list each entry one by one
  #
  #            logger.debug('traversal_func_kgx(): Traversing entry', entry)
  #
  #            object_key = location  # if not strict else None
  #
  #            fileobj = tf.extractfile(entry)
  #
  #            logger.debug('traversal_func_kgx(): Entry file object', fileobj)
  #
  #            if fileobj is not None:  # not a directory
  #
  #                pre_name = entry.name
  #                unpacked_filename = basename(pre_name)
  #
  #                logger.debug(f"traversal_func_kgx(): Entry names: {pre_name}, {unpacked_filename}")
  #
  #                if is_node_y(pre_name):
  #                    object_key = location + 'nodes/' + unpacked_filename
  #                elif is_edge_y(pre_name):
  #                    object_key = location + 'edges/' + unpacked_filename
  #                else:
  #                    object_key = location + unpacked_filename
  #
  #                logger.debug('traversal_func_kgx(): Object key will be', object_key)
  #
  #                if object_key is not None:
  #
  #                    logger.debug(f"traversal_func_kgx(): uploading entry into '{object_key}'")
  #
  #                    s3_client().upload_fileobj(  # upload a new obj to s3
  #                        Fileobj=io.BytesIO(fileobj.read()),
  #                        Bucket=default_s3_bucket,  # target bucket, writing to
  #                        Key=object_key  # TODO was this a bug before? (when it was location + unpacked_filename)
  #                    )
  #
  #                    file_entries.append({
  #                        "file_type": "KGX data file",  # TODO: refine to more specific types?
  #                        "file_name": unpacked_filename,
  #                        "file_size": entry.size,
  #                        "object_key": object_key,
  #                        "s3_file_url": '',
  #                    })
  #        logger.debug('traversal_func_kgx(): file entries: ', file_entries)
  #        return file_entries

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
