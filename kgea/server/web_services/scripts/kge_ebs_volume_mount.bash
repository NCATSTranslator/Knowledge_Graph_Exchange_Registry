#!/usr/bin/env bash
#
# Shell script for *nix command line driven for formatting and mounting
# of an attached, newly created, empty (unformatted) AWS EC2 EBS volume.
#

usage () {
    echo
    echo "Usage:"
    echo
    echo "${0} <device_path> <mount_point>"
    exit 1
}

if [[ -z "${1}" ]]; then
    usage
else
    # EBS Device Path (assigned by AWS)
    device_path=${1}
fi

if [[ -z "${2}" ]]; then
    usage
else
    # EBS Device Path (assigned by AWS)
    mount_point=${2}
fi

#  Format the new volume
sudo mkfs -t xfs $device

# Create a 'scratch' directory relative to the
# current working directory, if not otherwise available
if [[ ! -d $mount_point ]]; then
    mkdir $mount_point
fi

# Mount the volume  on the 'scratch' path
sudo mount $device $mount_point

# Fix user/group access permissions
sudo chown -R "$(id -u):$(id -g)" $mount_point

# We dw NOT here add an entry for the device to the /etc/fstab file
# to automatically mount an attached volume after reboot since this
# volume is assumed to be a temporary provisioning of EBS storage
# for data post-processing operations during a session.
