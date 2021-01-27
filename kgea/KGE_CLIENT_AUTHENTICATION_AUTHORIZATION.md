# KGE Archive client authentication and authorization

As outlined in the [KGE RoadMap](./KGE_ARCHIVE_ROADMAP.md) since the KGE Archive ("Archive") implementation is targeted for deployment on NCATS hosted Amazon Web Services (AWS) cloud infrastructure, in particular, with reference to the uploading, storage and downloading of KGE File Sets on AWS S3 network storage, the required level of client user authentication and authorization will be embedded in the system using off-the-shelf AWS services to manage it, in particular, [AWS Cognito](https://docs.aws.amazon.com/cognito/latest/developerguide/what-is-amazon-cognito.html)).

AWS Cognito is a system managing user and AWS service access authorization tokens in a manner fully integrated with other AWS services. The two core concepts here are those of a [User Pool](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-identity-pools.html) which is the catalog of users authorized to access a system using the pool, and an [Identity Pool](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-identity.html) which manages temporary access authorization to other AWS services.

For its functional needs, the Archive needs to implement the [Access AWS Services with a User Pool and an Identity Pool ](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-scenarios.html#scenario-aws-and-user-pool) scenario of Cognito service deployment.

# Deployment Procedure

## Step 1 - Create a User Pool

The Archive is need a User Pool to manage the identities of users in the community of clients given authorization to upload and download KGE File Sets.  To create such a User Pool, see https://docs.aws.amazon.com/cognito/latest/developerguide/tutorial-create-user-pool.html. Specific configuration decisions that need to be made during pool creation are discussed here in the following subsections.  

The identity of the User Pool should be a secure, external system configuration parameter, to allow for flexible reconfiguration of User Pool characteristics in the future.  The following User Pool profile is the one initially specified during Archive prototyping. The profile may change in Production.

### Login Identifiers

For the moment, the following options for Archive client Login identification are specified:

- Username: Users can use a username and optionally multiple alternatives to sign up and sign in.
    - Also allow sign in with verified email address
    - Also allow sign in with verified phone number
    - Also allow sign in with preferred username (a username that your users can change)

### Login Attributes

For the moment, the following options for Archive client Login standard required attributes are specified:

- email
- family name
- given name
- website # to capture the user's affiliation

with the addition of one required custom attributes:

- Team  # string 3..32 characters  # Translator clients will indicate their team name here, e.g. SRI, Molecular Data Provider, etc.

### Login Policies

#### Password

Minimum length: 12

- Require numbers
- Require special character
- Require uppercase letters
- Require lowercase letters

#### Account Sign-Up Policy

To facilitate usage in the short term (and given that the Archive will initially be experiment and have little data and will need to be quickly used in the February 2021 Translator Relay), the User Pool will be initially configured to "_Allow users to sign themselves up_".  Later, the more restrictive option of "_Only allow administrators to create users_" may be asserted to ensure security of the system for general project access.

### Multi-Factor Authentication (MFA) & Verifications ?

Optional MFA will be selected during developmental processes. A "Production" user pool may enforce MFA as a mandatory requirement(?) - to be discussed by NCATS and the Translator community. The "_Time-based One-time Password_" option for MFA is only selected for only since "_SMS text message_" has broader AWS SNS cost and management implications.

#### Password Recovery Process

Selected "_Email if available, otherwise phone, but don’t allow a user to reset their password via phone if they are also using it for MFA_".

#### Attributes to Verify

Selected "Email". [Best practices suggest that customers send emails through Amazon SES for production User Pools due to a daily email limit](https://docs.aws.amazon.com/cognito/latest/developerguide/signing-up-users-in-your-app.html). 

#### Role to allow Amazon Cognito to send SMS messages

Created or assigned during User Pool Creation as needed.

### Message & Tag Customizations

Not initially done but Production Archive needs should be reviewed.

### Devices

"_User Opt In_" for remembering user's devices?

### App Clients

None initially configured.

### Triggers

None initially configured. To be reviewed at a later date. Available options are:

- Pre sign-up
- Pre authentication
- Custom message
- Post authentication

## Step 2 - Create an Identity Pool

T.B.A.

### User Group Roles

T.B.A.

## Step 3 - Implement KGE Archive Web Site Login / Logout Forms

T.B.A.

## Step 4 - KGE Archive Web Site Business Logic to Manage Registered Client Authorized Access to Site Resources and Behavior

T.B.A.
