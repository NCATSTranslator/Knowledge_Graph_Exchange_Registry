import hashlib
import csv
import tempfile
import os

# https://stackoverflow.com/questions/22058048/hashing-a-file-in-python
# NOTE: Use inside of file
def fileSha1(file):

    h = hashlib.sha1()
    b = bytearray(128*1024)
    mv = memoryview(b)
    # with open(file_path, 'rb', buffering=0) as f:
    for n in iter(lambda: file.readinto(mv), 0):
        h.update(mv[:n])
    return h.hexdigest()

# File -> Bool
def isArchive(file):
    return False

# { (File -> Code) | Archive.File } -> Map
def sha1Manifest(files):
    if type(files) is not list:
        files = [files]
    aggregation = []
    for file in files:
        code = fileSha1(file)
        aggregation.append((file.name, code))
    return dict(aggregation)

# Manifest -> TSV File
def manifestToFile(manifest, filename):
    projected_manifest_entries = [{'filename': key, 'sha1': manifest[key]} for key in manifest]
    with open(filename, 'w', newline='') as manifest_file:
        fieldnames = ['filename', 'sha1']
        manifest_writer = csv.DictWriter(manifest_file, delimiter='\t', fieldnames=fieldnames)
        manifest_writer.writeheader()
        for row in projected_manifest_entries:
            manifest_writer.writerow(row)
        return manifest_writer

# Files -> TSV File [ Filename, Code ]
def sha1ManifestFile(files, filename='manifest.tsv'):
    manifest_dict = sha1Manifest(files)
    return manifestToFile(manifest_dict, filename)

# Archive -> { (File -> Code) | Archive.File } -> Map
def archiveSha1Manifest(archive):
    if isArchive(archive):
        # TODO: extract files
        files = []
        return sha1Manifest(files)

# Archive -> Code
def archiveFileSha1(archiveFile):
    if isArchive(archiveFile):
        return fileSha1(archiveFile)

# Archive -> File (TSV)
def archiveSha1ManifestFile(archive, filename=None):
    manifest_dict = archiveSha1Manifest(archive)
    if filename:
        return manifestToFile(manifest_dict, filename)
    else:
        return manifestToFile(manifest_dict, archive.name + '.manifest' + '.tsv')

with tempfile.NamedTemporaryFile(suffix='.tsv', prefix=os.path.basename(__file__), buffering=0) as testfile:
    files = [testfile]
    manifestFile = sha1ManifestFile(files)
