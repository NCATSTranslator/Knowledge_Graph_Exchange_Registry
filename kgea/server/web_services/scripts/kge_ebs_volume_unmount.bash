#!/usr/bin/env bash
#
# Shell script for *nix command line driven
# Mounting and Formatting script for a
# newly created, unassociated AWS EC2 EBS volume.
#


usage () {
    echo
    echo "Usage:"
    echo
    echo "${0} <volume_id> <mount_point>"
#    exit -1  bash exits 0-255
    exit 1
}

if [[ -z "${1}" ]]; then
    usage
else
    # EBS Volume Identifier (assigned by AWS)
    volume_id=${1}
fi

if [[ -z "${2}" ]]; then
    usage
else
    # Linux file path mount point path for volume
    mount_point=${2}
fi

