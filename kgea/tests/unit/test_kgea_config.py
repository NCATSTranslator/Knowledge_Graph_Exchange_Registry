from typing import Dict
from sys import stderr
import pytest
from pprint import pprint
from kgea.aws.ec2 import get_ec2_instance_metadata


@pytest.mark.asyncio
async def test_instance_metadata():
    metadata: Dict = await get_ec2_instance_metadata()
    assert "instanceId" in metadata
    assert "region" in metadata
    assert "availabilityZone" in metadata
    pprint(metadata,  stream=stderr)
