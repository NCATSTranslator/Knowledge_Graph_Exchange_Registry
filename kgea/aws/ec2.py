#!/usr/bin/env python
#
# This CLI script will take  host AWS account id, guest external id and
# the name of a host account IAM role, to obtain temporary AWS service
# credentials to execute an AWS Secure Token Service-mediated access
# to a Simple Storage Service (S3) bucket given as an argument.
#

import json
from sys import argv, stderr
from os.path import sep, dirname, abspath
from asyncio import sleep
from pathlib import Path
from subprocess import Popen, PIPE

from pprint import PrettyPrinter
from urllib.request import urlopen
from urllib.error import URLError

from json import dumps
from typing import List, Optional, Dict

from botocore.config import Config
from botocore.exceptions import ClientError

from kgea import get_app_config
from kgea.aws.assume_role import AssumeRole, the_role

from kgea.server.kgea_file_ops import default_s3_region, run_script

import logging

logger = logging.getLogger(__name__)

pp = PrettyPrinter(indent=4, stream=stderr)


EC2_INSTANCE_IDENTITY_URL = "http://169.254.169.254/latest/dynamic/instance-identity/document"

# Opaquely access the configuration dictionary
_KGEA_APP_CONFIG: Dict = get_app_config()
aws_config: Dict = _KGEA_APP_CONFIG['aws']

# Default EBS dynamic provisioning parameters
ebs_config: Dict = aws_config.setdefault('ebs', dict())

# we assume that '/dev/sdb' is already in use?
_SCRATCH_DEVICE = f"/dev/{ebs_config.setdefault('scratch_device', 'sdc')}"
_SCRATCH_DIR = ebs_config.setdefault('scratch_dir', f"/opt/tmp")

# Probably will rarely change the name of these scripts, but changed once already...
_SCRIPTS = f"{dirname(abspath(__file__))}{sep}scripts{sep}"

_KGEA_EBS_VOLUME_MOUNT_AND_FORMAT_SCRIPT = f"{_SCRIPTS}kge_ebs_volume_mount.bash"


def scratch_dir_path():
    return _SCRATCH_DIR


def usage(err_msg: str = ''):
    """

    :param err_msg:
    """
    if err_msg:
        print(err_msg)
    print("Usage: ")
    print(
        "python -m kgea.aws." + Path(argv[0]).stem +
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


def get_ec2_instance_id() -> str:
    metadata = get_ec2_instance_metadata()
    if "instanceId" in metadata:
        return metadata["instanceId"]
    else:
        return ""


def get_ec2_instance_region() -> str:
    metadata = get_ec2_instance_metadata()
    if "region" in metadata:
        return metadata["region"]
    else:
        return ""


def get_ec2_instance_availability_zone() -> str:
    metadata = get_ec2_instance_metadata()
    if "availabilityZone" in metadata:
        return metadata["availabilityZone"]
    else:
        return ""


def ec2_client(
        assumed_role=None,
        config=Config(
            # EC2 region assumed to be set to the same as the
            # config.yaml S3, but not totally sure about this.
            region_name=default_s3_region
        )
):
    """
    :param assumed_role: assumed IAM role serving as authentication broker
    :param config: botocore.config.Config configuring the EC2 client
    :return: AWS EC2 client
    """
    if not assumed_role:
        assumed_role = the_role
    return assumed_role.get_client('ec2', config=config)


def ec2_resource(assumed_role=the_role, **kwargs):
    """
    :param assumed_role:
    :return: EC2 resource
    """

    if not assumed_role:
        assumed_role = the_role

    return assumed_role.get_resource('ec2', **kwargs)


###################################################################################################
# Dynamic EBS provisioning steps, orchestrated by the KgeArchiver.worker() task which
# direct calls methods using S3 and EC2 clients, plus an (steps 1.3, 1.4 plus 3.1) enhanced
# version of the (step 2.0) kgea/server/web_services/scripts/kge_archiver.bash script.
#
# object_folder_contents_size():
# 0.1 (S3 client) - Calculate EBS storage needs for target activity
# (step 2.0 - archiving.. see below), then proceed to step 1.1
#
# create_ebs_volume():
# 1.1 (EC2 client) - Create a suitably sized EBS volume, via the EC2 client
# 1.2 (EC2 client) - Associate the EBS volume with the EC2 instance running the application
# 1.3 (Popen() run bash script) - Mount the EBS volume inside the EC2 instance and format the volume
#     TODO: might try to configure and use a persistent EBS Snapshot in step 1 to accelerate this step?
#     TODO: what kind of unit testing can I attempt on the dynamic EBS provisioning subsystem?
#     TODO: in the DOCKER containers, you may need to map the dynamically provisioned EBS 'scratch' VOLUME
#     TODO: begs the question: why copy the source code into the docker container? Should it simply be a mapped volume?
#
# compress_fileset():
# 2.0 (Popen() run bash script) - Use the instance as the volume working space for target
#     application activities (i.e. archiving). Likely need to set or change to the
#     current working directory to one hosted on the target EBS volume.
#
# delete_ebs_volume():
# 3.1 (Popen() run bash script) - Cleanly unmount EBS volume after it is no longer needed.
# 3.2 (EC2 client) - Disassociate the EBS volume from the EC2 instance.
# 3.3 (EC2 client) - Delete the instance (to avoid economic cost).
###################################################################################################


def is_valid_initial_status(
        volume_status: str,
        initial_status: List[str]
):
    """
    This 'volume_status' is generally the result of a specific volume operation
    call, hence the expected range of EBS volume State values can be checked
    against a specific list of 'initial_status' states. This particular list of
    Such statements are often quite distinct from the target volume 'State' polled
    by the describe_volumes() call, inside await_target_volume_state() below.

    :param volume_status: string status being checked against initial status
    :param initial_status: the valid initial status list of States

    :raises: RuntimeError if the volume_status is invalid
    """
    if volume_status not in initial_status:
        raise RuntimeError(
            f"check_volume_status(): Volume 'State' has initial state {initial_status}? "
            f"Expected {' or '.join(initial_status)}"
        )


async def await_target_volume_state(
        client,
        volume_id: str,
        target_state: str,
        dry_run: bool,
        time_out: int = 30  # default time out for the await is 30 seconds?
):
    """
    Polls EBS describe_volumes status until target_status or error is signalled.

    :param client: EBS EC2 client to which the polling operation is targeted
    :param volume_id: string volume identifier
    :param target_state: should be one of 'creating', 'available', 'in-use', 'deleting', 'deleted'
    :param dry_run: True if polling done as a 'dry run' AWS operation
    :param time_out: approximate seconds before the polling operation will time out (default: ~30 seconds)

    :raise: TimeoutError if status polling operation exceeds specified time_out
    :raise: RuntimeError if volume reports an 'error' State
    """
    method = "await_target_volume_state"
    logger.debug(
        f"Entering {method}(" +
        f"volume_id: '{volume_id}', " +
        f"target_status: '{target_state}')"
    )

    def get_volume_status(response):
        volrec = response["Volumes"][0]
        return volrec['State']

    # monitor status for 'target_status' before proceeding
    volume_status = None
    tries = 0
    while volume_status not in [target_state, "error"]:

        # Wait a second before checking status
        await sleep(1)

        # ... then check status again
        dv_response = client.describe_volumes(
            Filters=[
                {
                    'Name': 'status',
                    'Values': [
                        'creating',
                        'available',
                        'in-use',
                        'deleting',
                        'deleted',
                        'error'
                    ]
                },
            ],
            VolumeIds=[volume_id],
            DryRun=dry_run
        )
        volume_status = get_volume_status(dv_response)

        logger.debug(f"{method}(): Status is now '{volume_status}'")

        tries += 1
        if tries > time_out:
            raise TimeoutError(f"{method}(): polling timeout encountered for volume '{volume_id}'?")

    if volume_status == "error":
        raise RuntimeError(f"{method}(): volume '{volume_id}' reporting an 'error' state")

    # Unless a timeout or error occurs, then the
    # volume_status should equal the target_state
    assert volume_status == target_state


async def create_ebs_volume(
        size: int,
        device: str = _SCRATCH_DEVICE,  # NOT the internal NVME device here, but an external device, e.g. '/dev/sdc'
        mount_point: str = scratch_dir_path(),
        dry_run: bool = False
) -> Optional[str]:
    """
    Allocates and mounts an EBS volume of a given size onto the EC2 instance running the application (if applicable).
    The EBS volume is formatted and mounted by default on the (Linux) directory '/scratch_data'

    Notes:
    * This operation can only be performed when the application is running inside an EC2 instance

    :param size: specified size (in gigabytes)
    :param device: external AWS EBS device name to be deleted (default: config.yaml designated 'scratch' device name)
    :param mount_point: OS mount point (path) to which to mount the volume (default: local 'scratch_data' mount point)
    :param dry_run: no operation test run if True

    :return: Tuple of EBS volume identifier and associated internal (NVME) device path
    """
    method = "create_ebs_volume():"

    # The application can only create an EBS volume if it is running
    # within an EC2 instance so retrieve the EC2 instance identifier
    instance_id = get_ec2_instance_id()
    if not (dry_run or instance_id):
        logger.warning(
            f"{method} not inside an EC2 instance? Cannot dynamically provision your EBS volume?"
        )
        return None

    id_msg = f"EBS volume of {size} GB, attached to device '{device}', " + \
             f"mounted on '{mount_point}', of instance '{instance_id}'"

    logger.info(f"{method} creating {id_msg}")

    ec2_region = get_ec2_instance_region()
    ec2_availability_zone = get_ec2_instance_availability_zone()

    try:
        logger.debug(f"{method} getting EC2 Client.")
        ebs_ec2_client = ec2_client(config=Config(region_name=ec2_region))

        # Create a suitably sized EBS volume, via the EC2 client
        # response == {
        #     'Attachments': [
        #         {
        #             'AttachTime': datetime(2015, 1, 1),
        #             'Device': 'string',
        #             'InstanceId': 'string',
        #             'State': 'attaching'|'attached'|'detaching'|'detached'|'busy',
        #             'VolumeId': 'string',
        #             'DeleteOnTermination': True|False
        #         },
        #     ],
        #     'AvailabilityZone': 'string',
        #     'CreateTime': datetime(2015, 1, 1),
        #     'Encrypted': True|False,
        #     'KmsKeyId': 'string',
        #     'OutpostArn': 'string',
        #     'Size': 123,
        #     'SnapshotId': 'string',
        #     'State': 'creating'|'available'|'in-use'|'deleting'|'deleted'|'error',
        #     'VolumeId': 'string',
        #     'Iops': 123,
        #     'Tags': [
        #         {
        #             'Key': 'string',
        #             'Value': 'string'
        #         },
        #     ],
        #     'VolumeType': 'standard'|'io1'|'io2'|'gp2'|'sc1'|'st1'|'gp3',
        #     'FastRestored': True|False,
        #     'MultiAttachEnabled': True|False,
        #     'Throughput': 123
        # }
        logger.debug(f"{method} creating EBS volume in '{ec2_availability_zone}'.")
        volume_info = ebs_ec2_client.create_volume(
            AvailabilityZone=ec2_availability_zone,
            Size=size,
            VolumeType='gp2',
            DryRun=dry_run,
        )
        logger.debug(f"{method} ec2_client.create_volume() response:\n{pp.pformat(volume_info)}")

        volume_id: str = volume_info["VolumeId"]

        volume_status: str = volume_info["State"]
        initial_states = ["creating", "available"]

        is_valid_initial_status(volume_status, initial_states)

        if not volume_status == "available":
            # if necessary, wait for the volume State transition to "available"
            await await_target_volume_state(
                ebs_ec2_client,
                volume_id,
                "available",
                dry_run
            )

    except Exception as ex:
        logger.error(f"{method} ec2_client.create_volume() exception: {str(ex)}")
        return None

    logger.debug(f"{method} executing ec2_resource().Volume({volume_id})")
    volume = ec2_resource(region_name=ec2_region).Volume(volume_id)

    # Attach the EBS volume to a device in the EC2 instance running the application
    try:
        # va_response == {
        #     'AttachTime': datetime(2015, 1, 1),
        #     'Device': 'string',
        #     'InstanceId': 'string',
        #     'State': 'attaching'|'attached'|'detaching'|'detached'|'busy',
        #     'VolumeId': 'string',
        #     'DeleteOnTermination': True|False
        # }
        logger.debug(
            f"{method} executing volume.attach_to_instance(Device={device}, InstanceId={instance_id}, DryRun={dry_run})"
        )
        va_response = volume.attach_to_instance(
            Device=device,
            InstanceId=instance_id,
            DryRun=dry_run
        )
        # Note that, at this point, the external device path is set to
        # the 'device' argument passed to the method, something like '/dev/sdc'
        # Note however, that on recent EC2 instances, this is mapped internally
        # to an internal NVME device, something like '/dev/nvme2n1'
        logger.debug(f"{method} volume.attach_to_instance() response:\n{pp.pformat(va_response)}")

        volume_status: str = va_response["State"]

        # not too sure about 'busy' but I'll hedge my bets here...
        is_valid_initial_status(volume_status, ["attaching", "attached", "busy"])

        if not volume_status == "attached":
            # await until the attaching volume State signals that it is "in-use"
            await await_target_volume_state(
                ebs_ec2_client,
                volume_id,
                "in-use",
                dry_run
            )

    except Exception as e:
        logger.error(
            f"{method} failed to attach {id_msg}: {str(e)}"
        )
        return None

    logger.debug(
        f"{method} mount and format {id_msg}."
    )

    # nvme_device is made visible and set as a
    # nonlocal variable is set within the output_parser()
    nvme_device = ""

    def output_parser(line: str):
        """
        :param line: bash script stdout line being parsed
        """
        nonlocal nvme_device  # important to declare this as nonlocal here!
        if not line.strip():
            return  # empty line?

        # logger.debug(f"Entering output_parser(line: {line})!")
        if line.startswith("nvme_device="):
            nvme_device = line.replace("nvme_device=", '')
            logger.debug(f"output_parser(): nvme_device={nvme_device}")

    try:
        if not dry_run:
            return_code = await run_script(
                script=_KGEA_EBS_VOLUME_MOUNT_AND_FORMAT_SCRIPT,
                args=(
                    # Locally remove the embedded hyphen,
                    # only here, for script compatibility
                    volume_id.replace('-', ''),
                    mount_point
                ),
                stdout_parser=output_parser
            )
            if return_code == 0:

                # 'nvme_device' should NOT be empty
                assert nvme_device

                logger.info(
                    f"{method} Successfully provisioned, formatted and mounted "
                    f"'{volume_id}' {id_msg} on the internal NVME device '{nvme_device}'"
                )
                # deprecated returning the NVME device ... don't really care?
                return volume_id
            else:
                logger.error(
                    f"{method} Failure to complete mounting and formatting of {id_msg}"
                )
                return None
        else:
            logger.debug(
                f"{method} 'Dry Run' skipping of the mounting and formatting of {id_msg}"
            )
            return None

    except Exception as e:
        logger.error(f"{method} {id_msg} mounting/formatting script exception: {str(e)}")
        return None


async def delete_ebs_volume(
        volume_id: str,
        device: str = _SCRATCH_DEVICE,  # NOT the internal NVME device here, but an external device, e.g. '/dev/sdc'
        mount_point: str = scratch_dir_path(),
        dry_run: bool = False
) -> None:
    """
    Detaches and deletes the previously provisioned specified volume.

    Notes:
    * This operation can only be performed when the application is running inside an EC2 instance

    :param volume_id: identifier of the EBS volume to be deleted
    :param device: external EBS device path name of volume to be deleted e.g. /dev/sdc
    :param mount_point: OS mount point (directory path) to unmount
    :param dry_run: no operation test run if True (default: False)
    """
    method = "delete_ebs_volume():"

    if not (volume_id or device or mount_point):
        logger.error(f"{method} empty 'volume_id', 'device' or 'mount_point' argument?")
        return

    id_msg = f"EBS volume '{volume_id}', attached to device '{device}' and mounted on '{mount_point}'."

    logger.info(f"{method} deleting {id_msg}")

    # The application can only create an EBS volume if it is running
    # within an EC2 instance so retrieve the EC2 instance identifier
    instance_id = get_ec2_instance_id()
    if dry_run or not instance_id:
        logger.warning(
            f"{method}  dry run or not inside an EC2 instance? Cannot dynamically provision your EBS volume?"
        )
        return

    ec2_region = get_ec2_instance_region()
    ebs_ec2_client = ec2_client(config=Config(region_name=ec2_region))

    # 3.1 (Popen() run sudo umount -d mount_point, then remove the mount point directory)
    #     Cleanly unmount EBS volume after it is no longer needed.
    try:
        if not dry_run:

            cmd = f"sudo umount -d {mount_point}; sudo rm -Rf {mount_point}"
            logger.debug(f"{method} running command '{cmd}'?")

            with Popen(
                    cmd,
                    bufsize=1,
                    universal_newlines=True,
                    stderr=PIPE,
                    shell=True
            ) as proc:
                for line in proc.stderr:
                    logger.debug(line)

            if proc.returncode == 0:
                logger.info(
                    f"{method} Successfully unmounted EBS volume '{volume_id}' from mount point '{mount_point}'"
                )
            else:
                logger.error(
                    f"{method} Failed to unmount of EBS volume '{volume_id}' on mount point '{mount_point}'"
                )
                return
        else:
            logger.debug(
                f"{method} 'Dry Run' skipping of the unmounting of " +
                f"EBS volume '{volume_id}' on mount point '{mount_point}'"
            )

    except Exception as e:
        logger.error(f"{method} EBS volume '{mount_point}' could not be unmounted? Exception: {str(e)}")
        return

    if dry_run and not volume_id:
        logger.warning(f"{method} volume_id is null.. skipping volume detach and deletion")
        return

    logger.debug(f"{method} accessing EC2 resource for volume {volume_id}?")
    volume = ec2_resource(region_name=ec2_region).Volume(volume_id)

    # 3.2 (EC2 client) - Detach the EBS volume on the scratch device from the EC2 instance.
    try:
        # vol_detach_response = {
        #     'AttachTime': datetime(2015, 1, 1),
        #     'Device': 'string',
        #     'InstanceId': 'string',
        #     'State': 'attaching'|'attached'|'detaching'|'detached'|'busy',
        #     'VolumeId': 'string',
        #     'DeleteOnTermination': True|False
        # }
        logger.debug(f"{method} detaching device '{device}' from EC2 instance '{instance_id}'?")

        await await_target_volume_state(
            ebs_ec2_client,
            volume_id,
            "in-use",
            dry_run
        )

        vol_detach_response = volume.detach_from_instance(
            Device=device,
            Force=True,
            InstanceId=instance_id,
            DryRun=dry_run
        )

        logger.debug(f"{method} volume.detach() response:\n{pp.pformat(vol_detach_response)}")

        # We want to wait until the detached volume State is again fully "available"
        await await_target_volume_state(
            ebs_ec2_client,
            volume_id,
            "available",
            dry_run
        )

        # 3.3 (EC2 client) - Delete the instance (to avoid incurring further economic cost).
        volume.delete(DryRun=dry_run)  # this operation returns no response but...

    except Exception as ex:
        logger.error(
            f"{method} cannot delete the EBS volume '{volume_id}' from instance '{instance_id}', exception: {str(ex)}"
        )

    logger.info(f"{method} successfully completed deletion of {id_msg}")

###########################################
# Run the EC2 module as a CLI applicatiom #
###########################################
if __name__ == '__main__':
    
    context: str = ""
    action: str = ""
    instance_ids: Optional[List[str]] = None
    keypair_name: str = ''
    
    # Prompt user for target and action for the EC2 service
    if len(argv) >= 3:
    
        context = argv[1].upper()
        action = argv[2].upper()
    
        if context == 'INSTANCE':
            instance_ids = argv[3:] if len(argv) > 3 else None
        elif context == 'KEYPAIR':
            keypair_name = argv[3] if len(argv) > 3 else None
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
