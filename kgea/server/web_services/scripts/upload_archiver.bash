#!/usr/bin/env bash
#
# Shell script for *nix command line driven
# archiving of a KGE File Set for downloading
#
# AWS command (can be tweaked if problematic, e.g. under Windows?)
if [[ "$OSTYPE" == "cygwin" ]]; then
        aws=`which aws.cmd`
else
        aws=`which aws`
fi

echo "Begin archiving..."
echo

# Knowledge Graph Identifier
kgid='semantic-medline-database'
# File Set Version of the Knowledge Graph
version=${1:-1.0}
# S3 bucket source where the file set is located
bucket='delphinai-kgea-test-bucket-2'
# Root S3 folder in the bucket, containing the knowledge graph -> file set
root='kge-data'
# Knowledge Graph S3 folder
knowledge_graph=$bucket'/'$root'/'$kgid
# Folder of given versioned file set of the Knowledge Graph
file_set=$knowledge_graph'/'$version
# Full S3 object key to the file set folder
s3='s3://'$file_set
# File Set tar archive
tarfile=$kgid"_$version.tar"

echo kgid = $kgid
echo version = $version
echo bucket = $bucket
echo root = $root
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
  $aws s3 cp $s3"/$file" .
  tar rf "$tarfile" "$file"
  rm "$file"
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