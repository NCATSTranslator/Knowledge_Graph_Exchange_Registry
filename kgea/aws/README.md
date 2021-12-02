# Deployment for the KGE Archive on the NCATS AWS Cloud

## Table of Contents

- [Overview](#overview)
- [IAM Configuration](#iam-configuration)
    - [Task 1: Create an IAM role in the Host account](#task-1-create-an-iam-role-in-the-host-account)
    - [Task 2: Give users in the "Guest" account permission to assume the role in the Host account](#task-2-give-users-in-the-guest-account-permission-to-assume-the-role-in-the-host-account)
    - [Task 3: Run the script to allow the user to sign into the Host account console](#task-3-run-the-script-to-allow-the-user-to-sign-into-the-host-account-console)
- [AWS Service Access Policies for the KGE Archive](#aws-service-access-policies-for-the-kge-archive)
    - [EC2 Configuration](#ec2-configuration)
        - [EC2 Access Policy for the KGE Archive Server](#ec2-access-policy-for-the-kge-archive-server)
        - [Launching the EC2 from the Command Line using STS AssumeRole permissions](#launching-the-ec2-from-the-command-line-using-sts-assumerole-permissions)
    - [Cognito Configuration](#cognito-configuration)
        - [Cognito Access Policy for the KGE Archive Server](#cognito-access-policy-for-the-kge-archive-server)
        - [Configuring Cognito from the Command Line, using STS AssumeRole permissions](#configuring-cognito-from-the-command-line-using-sts-assumerole-permissions)
    - [S3 Configuration](#s3-configuration)
        - [S3 Access Policy for the KGE Archive Server](#s3-access-policy-for-the-kge-archive-server)
        - [Configuring S3 from the Command Line, using STS AssumeRole permissions](#configuring-s3-from-the-command-line-using-sts-assumerole-permissions)
    - [SNS Configuration](#sns-configuration)
        - [SNS Access Policy for the KGE Archive Server](#sns-access-policy-for-the-kge-archive-server)
        - [Configuring SNS from the Command Line, using STS AssumeRole permissions](#configuring-sns-from-the-command-line-using-sts-assumerole-permissions)
- [KGE AWS Utility Modules](#kge-aws-utility-modules)
    - [S3 Script](#s3-script)
    - [Cognito Script](#cognito-script)

## Overview

We designed the Knowledge Graph Exchange Archive ("KGE") to run on Amazon Web Services ("AWS") cloud infrastructure. During development, local deployment of the system leveraged AWS services  - Elastic Compute Cloud ("EC2") , Simple Storage Service ("S3"),  Cognito (the AWS service implementation of OAuth2) and perhaps, other AWS services in the future. The AWS Dashboard, AWS credentials and relatively liberal AWS Identify and Access Management ("IAM") security policies available to the developer formed the basis for system configuration.

With the need to re-deploy the system onto a NCATS-hosted AWS account, the direct use of the AWS Dashboard with relatively unconstrained IAM policies and developer-issued user credentials is not suitable.  Instead, we require the following changes to deployment process:

1. AWS services need to be indirectly accessed by IAM Role, rather than by IAM User.
   
1. Restricted IAM security policies permissions need to be specified as minimally needed for the requirements of deployment and operation of the system, and added to the aforementioned IAM Role.
   
1. Service access needs to be by temporary AWS credentials via an AWS Secure Token Service ("STS") _AssumeRole_ service calls, that is a best practice for 'cross-account' AWS access. Furthermore, the _AssumeRole_ requests will be made using a developer/consultant specified External ID.

This document complements the [main technical README docs discussing configuration of the KGE Archive system](../../README.md) by enumerating the step-by-step procedure for deploying AWS services for a production instance of the KGE Archive software, to a NCATS-hosted AWS account.

## IAM Configuration

A [cross-account tutorial](https://docs.aws.amazon.com/IAM/latest/UserGuide/tutorial_cross-account-with-roles.html) describes the basic AWS Dashboard procedure for AWS access using IAM Roles. We adapt this procedure here with the minor modification that we initially defer assigning IAM policies to the role to subsequent KGE Archive AWS service configuration steps. 

Here, we designate the NCATS AWS account as the "Host" AWS account. The AWS account of the developer/consultant' deploying the KGE Archive system for NCATS, is denoted as the "Guest" account.

### Task 1: Create an IAM role in the Host account

This initial step is most easily accomplished on the AWS Dashboard in the Host account.

Once logged into the AWS Dashboard, go to IAM console. Next, select the role view from sidebar menu, then click "Create Role". Select "Another AWS Account" as the "Type of Trusted Entity". This brings up the appropriate workflow for this mode of role configuration.

During role creation, we first specify the identifier of the "Guest" AWS account (which is to be given access to the role within the "Host" AWS account). We also select the checkbox to _"require an external id"_. This brings up a text box for entering the external id itself, which should requested from the "Guest" account representative.  The checkbox for use of multi-factor authentication (MFA) is left unselected (if desired, the requirements of the MFA should be reviewed with the "Guest" representative). Then, click "_Next: Permissions_"

We skip the assignment of a policy to the role until later (see below), by clicking "_Next: Tags_". Since the assignment of tags is also optional here, once in the Tag entry page of the workflow, we also click "_Next: Review_". 

At this point, we give our role its name (perhaps something like _translator-sri-access_) and add a basic description of the purpose of the role for future reference. Then, we finalize creation of the role using by clicking the "_Create Role_" button.

At this point, we have established trust between the Guest and Host accounts. We did this by creating a role in the Host account that identifies the Guest account as a trusted principal. Later, when we add security policies to the new role, we will also define what users who switch to the (_translator-sri-access_) role can do.

We take note, here, of the ARN of the role, for subsequent tasks. It will be something like:

```
arn:aws:iam::HOST-ACCOUNT-ID:role/translator-sri-access
```

Where `translator-sri-access` is the name of the role we created and HOST-ACCOUNT-ID is, again, the AWS account id of the "Host" organization (i.e. NCATS).

### Task 2: Give users in the "Guest" account permission to assume the role in the Host account

Once we created the role, we need to assign an IAM permissions to users in the "Guest" account, to access the "Host" role. Here, we assume that the "Guest" account has created a user group called `KgeaDeployer` within which designated users who will be involved with the deployment will be assigned.

1. Sign in as an administrator of the "Guest" AWS account, and open the IAM console.

1. Choose the specific "Guest" IAM User group to be given Trusted Host access.

1. Choose the `Permissions` tab, choose **Add permissions**, and then choose **Create inline policy**.

1. Choose the **JSON** tab.

Add the following policy statement to allow the `AssumeRole` action on the `translator-sri-access` role in the "Host" account. Be sure that we set the HOST-ACCOUNT-ID in the Resource element to the actual AWS account ID of the "Host" account.

```json
{
  "Version": "2012-10-17",
  "Statement": {
    "Effect": "Allow",
    "Action": "sts:AssumeRole",
    "Resource": "arn:aws:iam::HOST-ACCOUNT-ID:role/translator-sri-access"
  }
}
```

The `Allow` effect explicitly allows the designated user group access to the `translator-sri-access` role in the Production account. Any developer who tries to access the role will succeed.

Note that, as necessary for due diligence, one can also set trust policies for other groups to `Deny` instead of `Allow` the above `Action`.

### Task 3: Run the script to allow the user to sign into the Host account console

A [basic STS-enabled Python script (console.py)](./console.py) here is adapted and updated from a [sample script in AWS documents](https://aws.amazon.com/blogs/security/how-to-enable-cross-account-access-to-the-aws-management-console/). This script provides a working STS **Assume Role** service transaction, based on user-provided "Host" AWS account id, a configured external id and target role parameters. From within the project repository's root directory, run the console access script as a Python module:

```shell
$ python -m kgea.aws.console
Usage:
console.py
 <host_account_id> <external_id> <iam_role_name>
```

The usage help of the script specifies the requirement for three command line arguments associated with the configuration of the IAM role: the guest account id, the associated external id and the 'host' IAM role (e.g. _translator-sri-access_).  Given those command line arguments, the script should then load the AWS Console into the user's default web browser.

Running the script gives access to the specified IAM Role in the "Host" AWS account with all the AWS service operations that its IAM security policies allow.  We initially designed and tested this script within a non-NCATS account, but it is being iteratively refined to serve the needs of a NCATS deployment workflow, as further detailed below.

## AWS Service Access Policies for the KGE Archive

At this point, since the newly defined (_translator-sri-access_) role has no security policy permissions associated with it, any attempt to access and configure AWS services of the Dashboard will fail. We will resolve this issue next (here below), for each one of the AWS services used by the KGE Archive system.

### EC2 Configuration

The KGE Archive is essentially a Dockerized Python language based web user interface and web service application stack. As such, it runs within an EC2 server. Although the application can be substantially tested under Microsoft Windows and Mac OSX, the recipe for production deployment will target an Ubuntu Linux EC2 server environment. We outline the specific details for Docker and web server deployment in the [KGE Archive project README](../../README.md). Here, we mainly focus on the configuration, launching and accessing of the host AWS EC2 server. This proceeds through suitably constrained IAM securities policies, to be associated with the new _translator-sri-access_ IAM Role defined above.

#### EC2 Access Policy for the KGE Archive Server

T.B.A

#### Launching the EC2 from the Command Line using STS AssumeRole permissions

T.B.A

### Cognito Configuration

KGE Archive use cases currently restricts data access to authorized human users. A system component for user authentication and authorization therefore needs to manage data access. We have used the features of the AWS Cognito service to satisfy use cases for this requirement. We have previously configured Cognito using the AWS Dashboard console interface.  Here, we review the IAM security policy required to enable the  _translator-sri-access_ IAM Role to enable proper configuration of Cognito for the NCATS Translator deployment of the KGE Archive system.

#### Cognito Access Policy for the KGE Archive Server

T.B.A

#### Configuring Cognito from the Command Line, using STS AssumeRole permissions

T.B.A

### S3 Configuration

The KGE Archive persists its KGX data files and associated metadata in an AWS S3 storage bucket. Here, we review the IAM security policy and procedures required to enable the _translator-sri-access_ IAM Role to properly configure S3 for the NCATS operation of the KGE Archive system. Once again, this IAM policy configuration complements application configuration discussed in the [KGE Archive project README](../../README.md) and related documents.

#### S3 Access Policy for the KGE Archive Server

T.B.A

#### Configuring S3 from the Command Line, using STS AssumeRole permissions

T.B.A

### SNS Configuration

Community notification of new data set uploads to the KGE Archive is a suggested future use case. We will like use the Simple Notification Service (SNS) for this use case.  We will elaborate IAM policy requirements once we implement this use case for deployment.

#### SNS Access Policy for the KGE Archive Server

T.B.A

#### Configuring SNS from the Command Line, using STS AssumeRole permissions

T.B.A

# KGE AWS Utility Modules

Various utility AWS CLI modules (available in the **kgea.aws** package of the project) may be used the KGEA config.yaml configurations for AWS IAM, S3, EC2, Cognito, etc. operations, to access a given KGE Archive site.  

## S3 Script

The [S3 module](s3.py) is a well-developed script that provides administrative access the back end KGE archive bucket contents. To generally see all the available commands, type:

```shell
python -m kgea.aws.s3 --help
```

Additional usage help on subcommands is provided in a similar fashion.  For example, for the `copy` command:

```shell
python -m kgea.aws.s3 copy --help
```

## Cognito Script

The [Cognito script](cognito.py) can help administrative maintenance of the KGE user auth/auth system  (e.g. to (re-)set User_Role attributes of registered users). See usage by:

```shell
python -m kgea.aws.cognito --help
```
