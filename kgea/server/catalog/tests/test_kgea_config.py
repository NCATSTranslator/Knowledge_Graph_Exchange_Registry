from typing import Dict
from pprint import pprint
from kgea.aws.ec2 import get_ec2_instance_metadata

import logging
logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")


def test_instance_metadata():

    logger.debug("test_instance_metadata():")

    metadata: Dict = get_ec2_instance_metadata()

    if metadata:
        assert "instanceId" in metadata
        assert "region" in metadata
        assert "availabilityZone" in metadata
        pprint(metadata)
    else:
        logger.debug("No EC2 metadata? This test likely not running inside an AWS EC2 instance...Skipping test!")
