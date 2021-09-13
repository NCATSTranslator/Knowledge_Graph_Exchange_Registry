$kgid = 'sri-reference-graph'
$version=''

$bucket = 'kgea-test-bucket'
$root = 'kge-data'

$knowledge_graph = $bucket+'/'+$root+'/'+$kgid+'/'+$version
$s3 = 's3://'+$knowledge_graph

$tarfile_name = $kgid+'.'+$version+'.tar'
#TODO
$tarfile_dir = $HOME+'\'+$tarfile_name

function Get-ScriptDirectory {
    Split-Path -Parent $PSCommandPath
}

echo $s3

cd (Get-ScriptDirectory)

# use awk to get the keys for files
$output = aws s3 ls $s3  | awk '{print $4}'
# iterate over file keys
foreach ($file in $output) {
    # example command:
    # aws s3 cp s3://kgea-test-bucket/kge-data/sri-reference-graph/1.0/content_metadata.json . | tar rf sri-reference-graph.1.0.tar content_metadata.json
    # use `rf` for tar to create if not exists, append files if existing
    aws s3 cp $s3$file . | tar rf $tarfile_dir $file
}

# after archiving all of the files, compress them
# note that `z` is incompatible with `r`, so we couldn't compress as we go
tar czf $tarfile_dir'.gz' $tarfile_dir

# copy the new archive file to s3
aws s3 cp $tarfile_dir'.gz' $s3'archive/'$tarfile_name'.gz'

# cleanup the files
# both the local copies of the tar file and gz files
rm $tarfile_dir'.gz' $tarfile_dir

echo "Done"