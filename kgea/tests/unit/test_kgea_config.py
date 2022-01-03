from typing import Dict
from sys import stderr
from pprint import pprint
from kgea.aws.ec2 import get_ec2_instance_metadata

import logging
logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")


def test_instance_metadata():
    logger.debug("Testing Instance Metadata Access")
    metadata: Dict = get_ec2_instance_metadata()
    assert "instanceId" in metadata
    assert "region" in metadata
    assert "availabilityZone" in metadata
    pprint(metadata)
