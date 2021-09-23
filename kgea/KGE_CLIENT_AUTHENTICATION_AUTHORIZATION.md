# KGE Archive client authentication and authorization

As outlined in the [KGE RoadMap](./KGE_ARCHIVE_ROADMAP.md) since the KGE Archive ("Archive") implementation is targeted for deployment on NCATS hosted Amazon Web Services (AWS) cloud infrastructure, in particular, with reference to the uploading, storage and downloading of KGE File Sets on AWS S3 network storage, the required level of client user authentication and authorization will be embedded in the system using off-the-shelf AWS services to manage it, in particular, [AWS Cognito](https://docs.aws.amazon.com/cognito/latest/developerguide/what-is-amazon-cognito.html)).

**Contents:**

- [Overview](#overview)
- [Deployment Procedure](#deployment-procedure)
    - [Step 1 - Create a User Pool](#step-1---create-a-user-pool)
    - [Step 2 - Implement KGE Archive Web Site Login](#step-2---implement-kge-archive-web-site-login)
    - [Step 3 - Create a Identity Pool](#step-3---create-an-identity-pool)
    - [Step 4 - Client Authorized Access to Site Resources](#step-4---client-authorized-access-to-site-resources)

# Overview

AWS Cognito is a system managing user and AWS service access authorization tokens in a manner fully integrated with other AWS services. The two core concepts here are those of a [User Pool](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-identity-pools.html) which is the catalog of users authorized to access a system using the pool, and an [Identity Pool](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-identity.html) which manages temporary access authorization to other AWS services.

For its functional needs, the Archive needs to implement the [Access AWS Services with a User Pool and an Identity Pool ](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-scenarios.html#scenario-aws-and-user-pool) scenario of Cognito service deployment.

# Deployment Procedure

## Step 1 - Create a User Pool

An [AWS Cognito User Pool needs to be created](https://docs.aws.amazon.com/cognito/latest/developerguide/tutorial-create-user-pool.html) to manage the identities of users in the community of clients given authorization to upload and download KGE File Sets.  Specific configuration decisions that need to be made during pool creation are discussed here in the following subsections.  

The specific identity of the User Pool should be a secure, external system configuration parameter, to allow for flexible reconfiguration of User Pool characteristics in the future.  The following User Pool profile is the one initially specified during Archive prototyping. The profile may change in Production.

### User Pool Region

Given that NCATS resides in Maryland, we host  Cognito IDP host in the AWS **us-east-1** Region.

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

- Team  # string 1..60 characters  # Translator clients will indicate their funded project name here, e.g. SRI, Molecular Data Provider, etc.
- Affiliation # string 1..60 characters, Institutional affiliation
- Contact_PI  # string 1..20 characters, Team Principal Investigator (could be 'self')
- User_Role   # integer 0..4, where 0 is the default value and denotes the role of a data read-only general user of the system; 1 is "data curator" with knowledge graph and file set creation role privilege; 3 is reserved for KGE Owner roles; 4 defines a root "admin" role

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

None initially configured. See separate app client configuration step below.

### Triggers

None initially configured. To be reviewed at a later date. Available options are:

- Pre sign-up
- Pre authentication
- Custom message
- Post authentication

## Step 2 - Implement KGE Archive Web Site Login

The [AWS Cognito procedure for creating a client app login](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-configuring-app-integration.html) is our initial guide here.

### App Client Integration

#### Enabled Identity Providers

Should select **Cognito User Pool**.

#### Sign in and sign out URLs

A suitably active https-secured web server host needs to be deployed, live and visible, perhaps something like "**https://kgea.translator.ncats.io**" We point the `Callback URL` and `Sign out URL` to that host.

#### Allowed OAuth Flows 

Select `Authorization code grant`.

#### Allowed OAuth Scopes

Select `email`, `openid`, `aws.cognito.signin.user.admin` and `profile`.

#### Configure a Login Associated Domain

After setting up an app client, one can configure the address of one's sign-up and sign-in webpages. One can use an Amazon Cognito hosted domain and choose an available domain prefix (which added to one of the regio-specific AWS Cognito hostnames, becomes the "_Login Associated Domain_"), or one can use one's own web address as a custom domain (set as the "_Login Associated Domain_").  

In principle, the specified hostname of the live (https-secured) KGE Archive server will be designated in the future as a custom domain, following directives to obtain and record an associated certificate in the AWS Certificate Manager (ACM) and to add an alias record to the domain’s hosted zone after it’s associated with the given user pool.   However, for testing purposes, a request can be made to register and use an available AWS Cognito prefixed domain name prefix (connected with a the regio-specific AWS Cognito hostname).

#### Client Secret

Full access to the AWS Cognito managed ID token for a user (and  its attributes) will require a server-side managed  'client secret' to select for this.

#### Using the login interface

Basic operation of the AWS Cognito hosted login UI is obtained by going to the following URL (with site-specific details included as required):

```
https://<Login_Associated_Domain>/login?response_type=code&client_id=<your_app_client_id>&redirect_uri=<your_callback_url>
```

This URL is wrapped by the `login_url` function in the `kgea.server.web_ui.kgea_users` (`kgea_users`) module in the `login_url`  function, called by the `kge_login` handler. 

See Step 4 below for further details about subsequent authorization steps.

## Step 3 - Create an Identity Pool

[Creating an AWS Cognito Identity Pool](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-identity.html)

### User Group Roles

T.B.A.

## Step 4 - Client Authorized Access to Site Resources

After the user provides their [credentials to the AWS Cognito managed login dialog](#using-the-login-interface), then Cognito returns an authorization 'code' back to the `redirect_uri` noted above.  This URL is processed in the   `kge_client_authentication` handler in the `kgea.server.web_ui.kgea_ui_handlers` (`kgea_ui_handlers`) module, which in turn, delegates to the `authenticate_user` function  in `kgea_users`  to retrieve the User ID Token user attributes.
