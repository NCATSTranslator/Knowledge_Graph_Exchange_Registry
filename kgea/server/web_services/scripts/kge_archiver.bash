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
gzip=gzip
# If multicore CPU's are available and compression speed is desired,
# the 'parallel gz' (pigz; https://zlib.net/pigz/) could be used
# gzip=pigz

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
    knowledge_graph=$1
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

echo
echo "Beginning archiving of file set version '$version' of knowledge graph '$kgid'"
echo

# Folder of given versioned file set of the Knowledge Graph
file_set=$knowledge_graph/$version

# Full S3 object key to the file set folder
s3=s3://$KGE_BUCKET/$KGE_ROOT_DIRECTORY/$file_set/archive

# File Set tar archive
tarfile=$knowledge_graph'_'$version.tar

# echo Knowledge Graph File Set = $knowledge_graph $version
# echo s3 archive root = $s3
# echo archive = $s3/$tarfile.gz

# use awk to get the keys for files
# output=`$aws s3 ls "$s3/"| awk '{print $4}'`
output=("provider.yaml" "file_set.yaml" "content_metadata.json" "nodes.tsv" "edges.tsv")

# iterate over files
echo
echo Retrieve and tar files:
for file in ${output[@]};
do
  $aws s3 cp $s3/$file .
  if [ $? -eq 0 ] && [ -f $file ]; then
     echo "- $file: archived!"
     # use `rf` for tar to create if not exists, append files if existing
     tar rf $tarfile $file
     rm $file
  else
     echo "- $file: unavailable for archiving?"
  fi
done

## after archiving all of the files, compress them
## note that `z` is incompatible with `r`, so we couldn't compress as we go
# tar czf "$tarfile.gz" "$tarfile"
$gzip $tarfile

## copy the new archive file to s3
$aws s3 cp $tarfile.gz $s3/$tarfile.gz

## cleanup the files
## both the local copies of the tar file and gz files
rm $tarfile.gz

echo
echo "...done archiving"