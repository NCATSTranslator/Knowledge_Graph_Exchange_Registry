#!/usr/bin/env python
#
# This CLI script will take  host AWS account id, guest external id and
# the name of a host account IAM role, to obtain temporary AWS service
# credentials to execute an AWS Secure Token Service-mediated access
# to a Simple Storage Service (S3) bucket given as an argument.
#
import json
import sys
from pathlib import Path

from urllib.request import urlopen
from urllib.error import URLError

from json import dumps
from typing import List, Optional, Dict

from botocore.exceptions import ClientError

from kgea.aws.assume_role import AssumeRole

import logging
logger = logging.getLogger(__name__)

EC2_INSTANCE_IDENTITY_URL = "http://169.254.169.254/latest/dynamic/instance-identity/document"


def usage(err_msg: str = ''):
    """

    :param err_msg:
    """
    if err_msg:
        print(err_msg)
    print("Usage: ")
    print(
        "python -m kgea.aws." + Path(sys.argv[0]).stem +
        " <host_account_id> <guest_external_id> <target_iam_role_name>" +
        " <context> <action> (<Key Pair Name> | <EC2 instance_id>*)"
    )
    print(
        "Where the (case insensitive) 'context' is either 'instance' or 'keypair'"
        " and the corresponding 'action' is either"
        "\n\tone of 'describe', 'start', 'stop' or 'reboot' for an 'instance' context, or"
        "\n\tone of 'create' or 'delete' for a 'keypair' context" +
        "\nNote[*]: for instance actions other than 'describe', one or more EC2 instance id arguments must be provided."
    )
    exit(0)


_instance_details: Dict = dict()


# Should return the following dictionary of tags  (values given are just examples)
# {
#     "devpayProductCodes" : null,
#     "privateIp" : "10.1.2.3",
#     "region" : "us-east-1",
#     "kernelId" : "aki-12345678",
#     "ramdiskId" : null,
#     "availabilityZone" : "us-east-1a",
#     "accountId" : "123456789abc",
#     "version" : "2010-08-31",
#     "instanceId" : "i-12345678",
#     "billingProducts" : null,
#     "architecture" : "x86_64",
#     "imageId" : "ami-12345678",
#     "pendingTime" : "2014-01-23T45:01:23Z",
#     "instanceType" : "m1.small"
# }
def get_ec2_instance_metadata() -> Dict:
    """
    Returns dictionary of EC2 instance metadata
    """
    global _instance_details
    if not _instance_details:
        try:
            resp = urlopen(
                url=EC2_INSTANCE_IDENTITY_URL,
                timeout=10  # 10 seconds timeout
            )
            if resp.status == 200:
                data = resp.read()
                _instance_details = json.loads(data)
            else:
                raise URLError(f"Response status: {str(resp.status)}")
        except URLError as ue:
            logger.warning(
                "get_instance_metadata(): instance metadata is inaccessible..." +
                f" perhaps you are not inside a running EC2 instance: {str(ue)}"
            )
    return _instance_details


async def get_ec2_instance_id() -> str:
    metadata = await get_ec2_instance_metadata()
    if "instanceId" in metadata:
        return metadata["instanceId"]
    else:
        return ""


async def get_ec2_instance_region() -> str:
    metadata = await get_ec2_instance_metadata()
    if "region" in metadata:
        return metadata["region"]
    else:
        return ""


async def get_ec2_instance_availability_zone() -> str:
    metadata = await get_ec2_instance_metadata()
    if "availabilityZone" in metadata:
        return metadata["availabilityZone"]
    else:
        return ""


# Run the module as a CLI
if __name__ == '__main__':

    context: str = ""
    action: str = ""
    instance_ids: Optional[List[str]] = None
    keypair_name: str = ''

    # Prompt user for target and action for the EC2 service
    if len(sys.argv) >= 3:
        
        context = sys.argv[1].upper()
        action = sys.argv[2].upper()
        
        if context == 'INSTANCE':
            instance_ids = sys.argv[3:] if len(sys.argv) > 3 else None
        elif context == 'KEYPAIR':
            keypair_name = sys.argv[3] if len(sys.argv) > 3 else None
        else:
            usage("Unrecognized context argument: '" + context + "'")
    
        assumed_role = AssumeRole()
    
        ec2_client = assumed_role.get_client('ec2')
    
        if context == 'KEYPAIR':
            if keypair_name:
                if action == 'CREATE':
                    # Do a dryrun first to verify permissions
                    try:
                        response = ec2_client.create_key_pair(KeyName=keypair_name, DryRun=True)
                    except ClientError as e:
                        if 'DryRunOperation' not in str(e):
                            usage(str(e))
        
                    # Dry run succeeded, run start_instances without dryrun
                    try:
                        response = ec2_client.create_key_pair(KeyName=keypair_name, DryRun=False)
                        #
                        # Response is something like:
                        # {
                        #     'KeyFingerprint': 'string',
                        #     'KeyMaterial': 'string',
                        #     'KeyName': 'string',
                        #     'KeyPairId': 'string',
                        #     'Tags': [
                        #         {
                        #             'Key': 'string',
                        #             'Value': 'string'
                        #         },
                        #     ]
                        # }
                        #
                        # where, in particular:
                        #
                        # KeyFingerprint (string) -- The SHA-1 digest of the DER encoded private key.
                        # KeyMaterial (string) -- An unencrypted PEM encoded RSA private key.
                        # KeyName (string) -- The name of the key pair.
                        # KeyPairId (string) -- The ID of the key pair.
                        #
                        print(response)
                        # TODO: maybe should save this in a file somewhere?
                        
                    except ClientError as e:
                        usage(str(e))
                    
                elif action == 'DELETE':
                    # Do a dryrun first to verify permissions
                    try:
                        response = ec2_client.delete_key_pair(KeyName=keypair_name, DryRun=True)
                    except ClientError as e:
                        if 'DryRunOperation' not in str(e):
                            usage(str(e))
                            
                    # Dry run succeeded, run start_instances without dryrun
                    try:
                        response = ec2_client.delete_key_pair(KeyName=keypair_name, DryRun=False)
                    except ClientError as e:
                        usage(str(e))
    
                else:
                    usage("Unrecognized 'Keypair' Action: " + action)
                    
                exit(0)
            else:
                usage("Missing key pair name for key pair action?")
        
        if context == 'INSTANCE':
            if action == 'DESCRIBE':
                # Do a dryrun first to verify permissions
                try:
                    response = ec2_client.describe_instances()
                    print(dumps(response))
                except ClientError as e:
                    if 'DryRunOperation' not in str(e):
                        usage(str(e))
        
            elif not instance_ids:
                usage("One or more EC2 instance identifiers are needed" +
                      " for all EC2 actions other than 'Describe'")
                
            else:
                if action == 'START':
                
                    # Do a dryrun first to verify permissions
                    try:
                        ec2_client.start_instances(InstanceIds=instance_ids, DryRun=True)
                    except ClientError as e:
                        if 'DryRunOperation' not in str(e):
                            usage(str(e))
                
                    # Dry run succeeded, run start_instances without dryrun
                    try:
                        response = ec2_client.start_instances(InstanceIds=instance_ids, DryRun=False)
                        print(dumps(response))
                    except ClientError as e:
                        usage(str(e))
                        
                elif action == 'STOP':
                    # Do a dryrun first to verify permissions
                    try:
                        ec2_client.stop_instances(InstanceIds=instance_ids, DryRun=True)
                    except ClientError as e:
                        if 'DryRunOperation' not in str(e):
                            usage(str(e))
                
                    # Dry run succeeded, call stop_instances without dryrun
                    try:
                        response = ec2_client.stop_instances(InstanceIds=instance_ids, DryRun=False)
                        print(dumps(response))
                    except ClientError as e:
                        usage(str(e))

                elif action == 'REBOOT':
                    try:
                        ec2_client.reboot_instances(InstanceIds=instance_ids, DryRun=True)
                    except ClientError as e:
                        if 'DryRunOperation' not in str(e):
                            print("You don't have permission to reboot instances.")
                            usage(str(e))

                    try:
                        response = ec2_client.reboot_instances(InstanceIds=instance_ids, DryRun=False)
                        print('Success', response)
                    except ClientError as e:
                        usage(str(e))

                elif action == 'CREATE_VOLUME':
                    try:
                        ec2_client.create_volume(
                            AvailabilityZone='string',
                            # Encrypted=True | False,
                            # Iops=123,
                            # KmsKeyId='string',
                            # OutpostArn='string',
                            # Size=123,
                            # SnapshotId='string',
                            
                            
                            VolumeType='st1',  # 'standard' | 'io1' | 'io2' | 'gp2' | 'sc1' | 'st1' | 'gp3',
                            # DryRun=True | False,
                            # TagSpecifications=[
                            #     {
                            #         'ResourceType': 'capacity-reservation' | 'client-vpn-endpoint' | \
                            #         'customer-gateway' | 'carrier-gateway' | 'dedicated-host' | 'dhcp-options' | \
                            #         'egress-only-internet-gateway' | 'elastic-ip' | 'elastic-gpu' | \
                            #         'export-image-task' | 'export-instance-task' | 'fleet' | 'fpga-image' | \
                            #         'host-reservation' | 'image' | 'import-image-task' | 'import-snapshot-task' | \
                            #         'instance' | 'instance-event-window' | 'internet-gateway' | 'ipv4pool-ec2' | \
                            #         'ipv6pool-ec2' | 'key-pair' | 'launch-template' | 'local-gateway' | \
                            #         'local-gateway-route-table' | 'local-gateway-virtual-interface' | \
                            #         'local-gateway-virtual-interface-group' | \
                            #         'local-gateway-route-table-vpc-association' | \
                            #         'local-gateway-route-table-virtual-interface-group-association' | \
                            #         'natgateway' | 'network-acl' | 'network-interface' | \
                            #         'network-insights-analysis' | 'network-insights-path' | 'placement-group' | \
                            #         'prefix-list' | 'replace-root-volume-task' | 'reserved-instances' | \
                            #         'route-table' | 'security-group' | 'security-group-rule' | 'snapshot' | \
                            #         'spot-fleet-request' | 'spot-instances-request' | 'subnet' | \
                            #         'traffic-mirror-filter' | 'traffic-mirror-session' | 'traffic-mirror-target' | \
                            #         'transit-gateway' | 'transit-gateway-attachment' | \
                            #         'transit-gateway-connect-peer' | 'transit-gateway-multicast-domain' | \
                            #         'transit-gateway-route-table' | 'volume' | 'vpc' | 'vpc-endpoint' | \
                            #         'vpc-endpoint-service' | 'vpc-peering-connection' | 'vpn-connection' | \
                            #         'vpn-gateway' | 'vpc-flow-log',
                            #         'Tags': [
                            #             {
                            #                 'Key': 'string',
                            #                 'Value': 'string'
                            #             },
                            #         ]
                            #     },
                            # ],
                            # MultiAttachEnabled=True | False,
                            # Throughput=123,
                            # ClientToken='string'
                            DryRun=True
                        )
                    except ClientError as e:
                        if 'DryRunOperation' not in str(e):
                            print("You don't have permission to create volumes.")
                            usage(str(e))

                    try:
                        response = ec2_client.create_volume(
                            AvailabilityZone='string',
                            InstanceIds=instance_ids,
                            DryRun=False
                        )
                        print('Success', response)
                    except ClientError as e:
                        usage(str(e))
        
                else:
                    print("Unrecognized EC2 'Instance' Action: " + action)
    else:
        usage()
