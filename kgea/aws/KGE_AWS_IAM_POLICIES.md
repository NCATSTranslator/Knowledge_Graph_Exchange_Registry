# Amazon Web Services (AWS) IAM Policy Configuration for Knowledge Graph Archive

The KGE Archive is currently designed for deployment to the AWS cloud. As such, it is configured  with certain resource access policy permissions essential to its operation.  This document attempts to document these [IAM policy requirements]().

# STS Assume Role

The server maybe configured for access to resources using an STS AssumedRole.  See also the [AWS README](README.md).

#  S3 Bucket

The KGE Archive stores data on an S3 bucket requiring the following permissions:

# TODO: fix this policy is overly permissive policy

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:*",
                "s3-object-lambda:*"
            ],
            "Resource": "*"
        }
    ]
}
```

# Cognito

See the [AWS README](README.md).

# Dynamic EBS Volume Provisioning

EC2 permissions mainly relate to the dynamic provisioning of Elastic Block Storage (EBS) volumes. Dynamic provisioning of EBS ensures that the EC2 instance can manage its disk storage for postprocessing huge  uploaded KGE file sets in a cost-effective "just-in-time, what-is-needed" basis, rather than static allocation and persistence of a "largest-common-denominator" storage (i.e. permament allocation of an EBS volume large enough for the largest KGX file set to be processed).

The required policy is as follows:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ec2:DetachVolume",
                "ec2:AttachVolume",
                "ec2:DeleteVolume",
                "ec2:DescribeAvailabilityZones",
                "ec2:DescribeVolumes",
                "ec2:CreateVolume"
            ],
            "Resource": "*"
        }
    ]
}
```