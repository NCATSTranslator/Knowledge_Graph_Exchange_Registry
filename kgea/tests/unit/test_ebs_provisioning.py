from os.path import exists
from pathlib import Path
import pytest

from kgea.aws.ec2 import get_ec2_instance_id
from kgea.server.web_services.kgea_file_ops import create_ebs_volume, scratch_dir_path, delete_ebs_volume

import logging
logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")

_TEST_DEVICE = "sdc"
_TEST_MOUNT_POINT = "/opt/ebs_test_dir"


@pytest.mark.asyncio
async def test_create_ebs_volume():

    # Full test only valid inside an EC2 instance
    instance_id = get_ec2_instance_id()
    if instance_id:
        dry_run = False
    else:
        dry_run = True

    # Create, attach, format and mount a 'tiny' test EBS volume
    test_volume_id = await create_ebs_volume(
        size=1,
        device=_TEST_DEVICE,
        mount_point=_TEST_MOUNT_POINT,
        dry_run=dry_run
    )
    if not dry_run:
        assert test_volume_id

    # If not a 'Dry Run', check if you can access the resulting scratch directory
    test_file = f"{_TEST_MOUNT_POINT}/testfile"
    if not dry_run:
        Path(test_file).touch()
        assert exists(test_file)

    # Delete the test volume
    delete_ebs_volume(
        volume_id=test_volume_id,
        device=_TEST_DEVICE,
        mount_point=_TEST_MOUNT_POINT,
        dry_run=dry_run
    )

    if not dry_run:
        assert not exists(test_file)
