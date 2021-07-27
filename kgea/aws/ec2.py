#!/usr/bin/env python
#
# This CLI script will take  host AWS account id, guest external id and
# the name of a host account IAM role, to obtain temporary AWS service
# credentials to execute an AWS Secure Token Service-mediated access
# to a Simple Storage Service (S3) bucket given as an argument.
#
import sys
from pathlib import Path

from json import dumps
from typing import List, Optional

from botocore.exceptions import ClientError

from kgea.aws.assume_role import AssumeRole


def usage(err_msg: str = ''):
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
        
        if context == 'instance':
            instance_ids = sys.argv[3:] if len(sys.argv) > 3 else None
        elif context == 'keypair':
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
                
                else:
                    print("Unrecognized EC2 'Instance' Action: " + action)
    else:
        usage()
