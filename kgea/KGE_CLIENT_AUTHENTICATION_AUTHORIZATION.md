# KGE Archive client authentication and authorization

As outlined in the [KGE RoadMap](./KGE_ARCHIVE_ROADMAP.md) since the KGE Archive ("Archive") implementation is targeted for deployment on NCATS hosted Amazon Web Services (AWS) cloud infrastructure, in particular, with reference to the uploading, storage and downloading of KGE File Sets on AWS S3 network storage, the required level of client user authentication and authorization will be embedded in the system using off-the-shelf AWS services to manage it, in particular, [AWS Cognito](https://docs.aws.amazon.com/cognito/latest/developerguide/what-is-amazon-cognito.html)).

AWS Cognito is a system managing user and AWS service access authorization tokens in a manner fully integrated with other AWS services. The two core concepts here are those of a [User Pool](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-identity-pools.html) which is the catalog of users authorized to access a system using the pool, and an [Identity Pool](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-identity.html) which manages temporary access authorization to other AWS services.

For its functional needs, the Archive needs to implement the [Access AWS Services with a User Pool and an Identity Pool ](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-scenarios.html#scenario-aws-and-user-pool) scenario of Cognito service deployment.

# Deployment Procedure

## Step 1 - Create a User Pool

T.B.A.

### Specification of Login Identifier and Attributes

T.B.A.

## Step 2 - Create an Identity Pool

T.B.A.

### User Group Roles

T.B.A.

## Step 3 - Implement KGE Archive Web Site Login / Logout Forms

T.B.A.

## Step 4 - KGE Archive Web Site Business Logic to Manage Registered Client Authorized Access to Site Resources and Behavior

T.B.A.
