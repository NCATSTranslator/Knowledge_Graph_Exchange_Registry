import hashlib
import csv
import tempfile
import os

RUN_TESTS = os.getenv('RUN_TESTS', default=True)


# https://stackoverflow.com/questions/22058048/hashing-a-file-in-python
# NOTE: Use inside of file
def file_sha1(file):
    """

    :param file:
    :return:
    """
    buffer_length = 128*1024
    h = hashlib.sha1()
    b = bytearray(buffer_length)
    mv = memoryview(b)
    for n in iter(lambda: file.readinto(mv), 0):
        h.update(mv[:n])
    digest = h.hexdigest()
    return digest


# File -> Bool
def is_archive(file):
    """

    :param file:
    :return:
    """
    return False


# { (File -> Code) | Archive.File } -> Map
def sha1_manifest(file_list):
    """

    :param file_list:
    :return:
    """
    if type(file_list) is not list:
        file_list = [file_list]
    aggregation = []
    for file in file_list:
        code = file_sha1(file)
        aggregation.append((file.name, code))
    return dict(aggregation)


# Manifest -> TSV File
def manifest_to_file(manifest, filename):
    """

    :param manifest:
    :param filename:
    :return:
    """
    projected_manifest_entries = [{'filename': key, 'sha1': manifest[key]} for key in manifest]
    manifest_file = open(filename, 'w', newline='')
    fieldnames = ['filename', 'sha1']
    manifest_writer = csv.DictWriter(manifest_file, delimiter='\t', fieldnames=fieldnames)
    manifest_writer.writeheader()
    for row in projected_manifest_entries:
        manifest_writer.writerow(row)
    manifest_file.close()
    return manifest_file


# Files -> TSV File [ Filename, Code ]
def sha1_manifest_file(file_list, filename='manifest.tsv'):
    """

    :param file_list:
    :param filename:
    :return:
    """
    manifest_dict = sha1_manifest(file_list)
    return manifest_to_file(manifest_dict, filename)


# Archive -> { (File -> Code) | Archive.File } -> Map
def archive_sha1_manifest(archive):
    """

    :param archive:
    :return:
    """
    if is_archive(archive):
        # TODO: extract files
        file_list = []
        return sha1_manifest(file_list)


# Archive -> Code
def archive_file_sha1(archive_file):
    """

    :param archive_file:
    :return:
    """
    if is_archive(archive_file):
        return file_sha1(archive_file)


# Archive -> File (TSV)
def archive_sha1_manifest_file(archive, filename=None):
    """

    :param archive:
    :param filename:
    :return:
    """
    manifest_dict = archive_sha1_manifest(archive)
    if filename:
        return manifest_to_file(manifest_dict, filename)
    else:
        return manifest_to_file(manifest_dict, archive.name + '.manifest' + '.tsv')


if __name__ == '__main__':

    if RUN_TESTS:
        with open(os.path.abspath('./test/data/somedata.csv'), 'rb') as test_file:
            sha1 = sha1_manifest(test_file)
        with tempfile.NamedTemporaryFile(suffix='.tsv', prefix=os.path.basename(__file__), buffering=0) as testfile:
            files = [testfile]
            manifestFile = sha1_manifest_file(files)
