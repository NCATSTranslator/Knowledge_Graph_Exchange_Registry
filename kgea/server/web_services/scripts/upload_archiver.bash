#!/usr/bin/env bash
#
# Shell script for *nix command line driven
# archiving of a KGE File Set for downloading
#
# Mandatory Environment Variables:
# -------------------------------
# $KGE_BUCKET - S3 bucket source where the file set is located
# $KGE_ROOT_DIRECTORY - Root S3 folder in the bucket, containing the knowledge graph -> file set
#
usage () {
    echo
    echo "Usage:"
    echo
    echo "./upload_archiver.bash <Knowledge Graph Identifier> <File Set Version>"
    exit -1
}

if [ -z "$KGE_BUCKET" ]
then
    echo
    echo "Please set the \$KGE_BUCKET environment variable"
    echo "(S3 bucket source where the file set is located)"
    exit -2
fi

if [ -z "$KGE_ROOT_DIRECTORY" ]
then
    echo
    echo "Please set the \$KGE_ROOT_DIRECTORY environment variable"
    echo "(Root S3 folder in the bucket, containing the knowledge graph -> file set)"
    exit -3
fi

if [ -z "$1" ]
then
    usage
else
    # Knowledge Graph Identifier
    kgid=$1
fi

if [ -z "$2" ]
then
    usage
else
    # TODO: validate proper SemVer format of file set version string here?
    # File Set Version of the Knowledge Graph
    version=$2
fi

# AWS command (can be tweaked if problematic, e.g. under Windows?)
if [[ "$OSTYPE" == "cygwin" ]]; then
        aws=`which aws.cmd`
else
        aws=`which aws`
fi

echo "Beginning archiving of file set version $version of knowledge graph $kgid"
echo

# Knowledge Graph S3 folder
knowledge_graph=$KGE_BUCKET'/'$KGE_ROOT_DIRECTORY'/'$kgid

# Folder of given versioned file set of the Knowledge Graph
file_set=$knowledge_graph'/'$version

# Full S3 object key to the file set folder
s3='s3://'$file_set

# File Set tar archive
tarfile=$kgid"_$version.tar"

echo kgid = $kgid
echo version = $version
echo bucket = $KGE_BUCKET
echo root = $KGE_ROOT_DIRECTORY
echo knowledge_graph = $knowledge_graph
echo file_set = $file_set
echo s3 = $s3
echo tarfile = $tarfile

# use awk to get the keys for files
output=`$aws s3 ls "$s3/"| awk '{print $4}'`

# iterate over file keys
for file in $output
do
  # remove trailing whitespace such as carriage returns
  file=`echo "$file" | sed 's/\s\$//g'`
  echo "$file"
  # example command:
  # aws s3 cp s3://kgea-test-bucket/kge-data/sri-reference-graph/1.0/content_metadata.json . | tar rf sri-reference-graph.1.0.tar content_metadata.json
  # use `rf` for tar to create if not exists, append files if existing
  $aws s3 cp $s3"/$file" - | tar rf "$tarfile" -
done

## after archiving all of the files, compress them
## note that `z` is incompatible with `r`, so we couldn't compress as we go
# tar czf "$tarfile.gz" "$tarfile"
gzip "$tarfile"

## copy the new archive file to s3
$aws s3 cp "$tarfile.gz" "$s3/archive/$tarfile.gz"

## cleanup the files
## both the local copies of the tar file and gz files
rm "$tarfile.gz"

echo
echo "...done archiving"