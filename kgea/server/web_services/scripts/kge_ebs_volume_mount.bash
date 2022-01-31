#!/usr/bin/env bash
#
# Shell script for *nix command line driven for formatting and mounting
# of an attached, newly created, empty (unformatted) AWS EC2 EBS volume.
#
# The script currently assumes that the external EBS volume is
# identified by a volume id to be resolved to its internal NVME device path
#

usage () {
    echo
    echo "Usage:"
    echo
    echo "${0} <ebs_volume_id> <mount_point>"
    exit 1
}

nvme=$(which nvme)
if [[ ! -f ${nvme} ]]; then
  echo "Please install the nvme tool ('nvme-cli') before running this script."
  exit 2
fi

if [[ -z "${1}" ]]; then
    usage
else
    # External volume ID assigned to the EBS volume by AWS, the volume id string should
    # *NOT* have any embedded hyphen, since the 'nvme' command below doesn't expect it
    volume_id=${1}
fi

if [[ -z "${2}" ]]; then
    usage
else
    # Internal filing system mount point path assigned by application
    mount_point=${2}
fi

echo "Mounting EBS volume '${volume_id}' on mount point '${mount_point}'"

# Resolve the internal NVME device path from the EBS Volume ID.
# This version of the 'nvme' command emits a JSON string something like:
# {
#   "Devices" : [
#     {
#       "NameSpace" : 1,
#       "DevicePath" : "/dev/nvme0n1",
#       "Firmware" : "1.0",
#       "Index" : 0,
#       "ModelNumber" : "Amazon Elastic Block Store",
#       "ProductName" : "Non-Volatile memory controller: Amazon.com, Inc. Device 0x8061",
#       "SerialNumber" : "vol0866b68ead142e29e",
#       "UsedBytes" : 8589934592,
#       "MaximumLBA" : 16777216,
#       "PhysicalSize" : 8589934592,
#       "SectorSize" : 512
#     },
# ... other volume entries...
#   ]
# }
# Use Python to parse this JSON string for the NVME device assigned to the given EBS volume?
nvme_device=$(
sudo nvme list -o json | python -c "
import sys, json
nvme_json = json.load(sys.stdin)
nvme_devices = nvme_json['Devices']
the_device  = 'unknown'
for device_spec in nvme_devices:
    if device_spec['SerialNumber'] == '${volume_id}':
        the_device = device_spec['DevicePath']
        break
print(the_device)
")

echo "${nvme_device}"

exit 0

if [[ ! -f "${nvme_device}" ]]; then
    echo "EBS volumn '${volume_id}' is unknown? Cannot mount!"
    usage
    exit 1
else
    # Internal filing system mount point path assigned by application
    mount_point=${2}
fi

#  Format the new volume
sudo mkfs -t xfs $nvme_device

# Create a 'scratch' directory relative to the
# current working directory, if not otherwise available
if [[ ! -d $mount_point ]]; then
    mkdir $mount_point
fi

# Mount the volume  on the 'scratch' path
sudo mount $nvme_device $mount_point

# Fix user/group access permissions
sudo chown -R "$(id -u):$(id -g)" $mount_point

# We do NOT here add an entry for the volume_id to the /etc/fstab file
# to automatically mount an attached volume after reboot since this
# volume is assumed to be a temporary provisioning of EBS storage
# for data post-processing operations during a given application session
# then is subsequently unmounted, detached and deleted from EC2.
