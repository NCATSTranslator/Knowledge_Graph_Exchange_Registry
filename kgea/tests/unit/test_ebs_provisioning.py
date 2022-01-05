from os.path import exists
from pathlib import Path
import pytest

from kgea.aws.ec2 import get_ec2_instance_id
from kgea.server.web_services.kgea_file_ops import create_ebs_volume, scratch_dir_path, delete_ebs_volume

import logging
logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")


@pytest.mark.asyncio
async def test_create_ebs_volume():

    # Full test only valid inside an EC2 instance
    instance_id = get_ec2_instance_id()
    if instance_id:
        dry_run = False
    else:
        dry_run = True

    # Create, attach, format and mount a 'tiny' test EBS volume
    test_volume_id = await create_ebs_volume(1, dry_run=dry_run)
    if not dry_run:
        assert test_volume_id

    # If not a 'Dry Run', check if you can access the resulting scratch directory
    test_file = f"{scratch_dir_path()}/testfile"
    if not dry_run:
        Path(test_file).touch()
        assert exists(test_file)

    # Delete the test volume
    delete_ebs_volume(test_volume_id, dry_run=dry_run)

    if not dry_run:
        assert not exists(test_file)