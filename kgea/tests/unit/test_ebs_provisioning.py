from os.path import exists
from pathlib import Path
import pytest

from kgea.aws.ec2 import get_ec2_instance_id
from kgea.server.web_services.kgea_file_ops import create_ebs_volume, delete_ebs_volume, is_valid_initial_status

import logging
logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")

_TEST_DEVICE = "/dev/sdc"
_TEST_MOUNT_POINT = "/opt/ebs_test_dir"


def test_is_initial_volume_status_validation():
    volume_status = "creating"
    initial_states = ["creating", "available"]

    is_valid_initial_status(volume_status, initial_states)

    try:
        volume_status = "something_else"
        is_valid_initial_status(volume_status, initial_states)
    except RuntimeError:
        assert True


@pytest.mark.asyncio
async def test_create_ebs_volume():

    # Full test only valid inside an EC2 instance
    instance_id = get_ec2_instance_id()
    if instance_id:
        dry_run = False
    else:
        dry_run = True

    # Create, attach, format and mount a 'tiny' test EBS volume
    mounted_volume = await create_ebs_volume(
        size=1,
        device=_TEST_DEVICE,
        mount_point=_TEST_MOUNT_POINT,
        dry_run=dry_run
    )
    # should not be None but rather, a Tuple of
    # the volume identifier and (NVME) device
    # corresponding to the _TEST_DEVICE
    assert mounted_volume

    # extract 'em'
    test_volume_id, test_volume_device = mounted_volume

    if not dry_run:
        assert test_volume_id

    # If not a 'Dry Run', check if you can access the resulting scratch directory
    test_file = f"{_TEST_MOUNT_POINT}/testfile"
    if not dry_run:
        Path(test_file).touch()
        assert exists(test_file)

    # # Delete the test volume
    # delete_ebs_volume(
    #     volume_id=test_volume_id,
    #     device=test_volume_device,
    #     mount_point=_TEST_MOUNT_POINT,
    #     dry_run=dry_run
    # )
    #
    # if not dry_run:
    #     assert not exists(test_file)
