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

- _Username:_ Users can use a username and optionally multiple alternatives to sign up and sign in.
    - Also allow sign in with verified email address
    - Also allow sign in with verified phone number
    - Also allow sign in with preferred username (a username that your users can change)

### Login Attributes

For the moment, the following options for Archive client Login standard required attributes are specified:

- _email_
- _family_name_
- _given_name_
- _website_ 

with the addition of one required custom attributes:

- _Team_  # string 1..60 characters  # Translator clients will indicate their funded project name here, e.g. SRI, Molecular Data Provider, etc.
- _Affiliation_ # string 1..60 characters, Institutional affiliation
- _Contact_PI_  # string 1..20 characters, Team Principal Investigator (could be 'self')
- _User_Role_   # integer 0..4, where 0 is the default value and denotes the role of a data read-only general user of the system; 1 is "data curator" with knowledge graph and file set creation role privilege; 3 is reserved for KGE Owner roles; 4 defines a root "admin" role

### Custom "User Role" Attribute

The custom "User Role" attribute merits a quick discussion here. The basic meaning of the attribute is defined above. User_Role 0 (zero) is the baseline which only allows 'read only' access to the system (i.e. mainly just the 'home' (minus some buttons) and 'metadata' pages. 

All other Roles have "read/write" for data, although roles 3 and 4 don't have any special significance (yet).

The default role for users in the system is 0, if their custom User_Role is not set; however,  this default may be globally overridden (typically, to User Role == 1 (one)) by setting the environment variable **DEFAULT_KGE_USER_ROLE**.

A utility bash script '[set_user_role.bash](../scripts/set_user_role.bash)' is available to facilite the setting of KGEA system user roles, to one of (regular) **user**, (data) **curator**, **owner**, **admin** or **superuser**.

### Administrative Setting of Attributes  (including User Custom Attributes)

The AWS Cognito Dashboard allows the creation of custom attributes and initial settings by batch upload or user registration;  however,  resetting of attributes values can only be done via the AWS API's or various programmatic SDK's.

In the KGE Archive project, **kgea.aws.cognito** module may be run from the command line to view user details and (re-)set user  attributes.

### Login Policies

#### Password

Minimum length: 15 characters

- Require numbers
- Require special character
- Require uppercase letters
- Require lowercase letters

#### Account Sign-Up Policy

The AWS Cognito system of the KGE Archive "production" installation is now constrained to have "administrative" creation of user accounts (only).

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

### Registering Users

Although the KGE Archive "Cogito" subsystem was originally configured for user-initiated account registration, administrative registration of users is now the norm. There are several options: user-initiated but administratively vetted users; administrator registration of users one at a time using the dashboard; or batch loading of users (again, using the dashboard). 

Batch loading is the preferred channel (see [user loading with CSV files](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-using-import-tool.html) for details). Note the requirement to set up a [service role with CloudWatch log permissions](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-using-import-tool-cli-cloudwatch-iam-role.html). Viewing the Cloud Watch logs is very helpful  for debugging user records being uploaded. The CSV file needs to have the exact CSV headers (download as noted). One "gotcha" to avoid in user record fields are spurious commas in the values of the fields (they tend to be parsed as CSV delimiters!). Note that some fields need to have a boolean values properly set even if not directly used in the authentication (i.e. **cognito:mfa_enabled**, **emailed_verified**, **phone_number_verified**).

Note the

## Step 2 - Implement KGE Archive Web Site Login

The [AWS Cognito procedure for creating a client app login](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-configuring-app-integration.html) is our initial guide here.

### App Client Creation and Parameters

A new "App Client" is needed for each distinct website using a specified Cognito User Pool (which can be shared across web sites).   

There are two left-hand sidebar items relating to App Clients - one under **General Settings** and one under App Client integration. A working App Client requires inputs under both menu items, first, under the **General Settings..App Client** menu item, then under the  [App Client Integration](#app-client-integration) menu item.

#### Creating the App Client

First, under the **General Settings..App Client**, start by clicking the **Add another app client** link. A new App Client section will come up on the screen. Give the new client a unique name within the User Pool. 

#### Customizing the App Client

Most of the App Client default settings may be kept as is. However, read and write permissions for app client attributes need to be fixed.

##### User Attributes

Select, as a minimum, the following:

- **_Readable Attributes_**:
    - _scopes:_ only check the _Address_ and _Email_ scopes.
    - _mandatory selections:_ email, family name, given name, preferred username, custom:User Role
- **_Writeable Attributes_**:
    - _scopes:_ only check the _Address_ scope.
    - _mandatory selections:_ email, family name, given name, preferred username, custom:User Role

After checking the attributes, make sure to click the "**Save app client changes**" button.

Note that the custom:User Role is a custom KGE-specific attribute which must be created before it is visible to be checked (details  elsewhere in this README).

Now, with the App Client created and basically configurated, continue with _App Client Integration_ in the next section.

### App Client Integration

#### Enabled Identity Providers

Should select **Cognito User Pool**.

#### Sign in and Sign out URLs

A suitably active https-secured web server host needs to be deployed, live and visible, perhaps something like "**https://kgea.translator.ncats.io**" We point the `Callback URL` and `Sign out URL` to that host.

#### Allowed OAuth Flows 

Select `Authorization code grant`.

#### Allowed OAuth Scopes

Select `email`, `openid`, `aws.cognito.signin.user.admin` and `profile`.

#### Configure a Login Associated Domain

After setting up an app client, one can configure the address of one's sign-up and sign-in webpages. One can use an Amazon Cognito hosted domain and choose an available domain prefix (which added to one of the regio-specific AWS Cognito hostnames, becomes the "_Login Associated Domain_"), or one can use one's own web address as a custom domain (set as the "_Login Associated Domain_").  

In principle, the specified hostname of the live (https-secured) KGE Archive server will be designated in the future as a custom domain, following directives to obtain and record an associated certificate in the AWS Certificate Manager (ACM) and to add an alias record to the domain’s hosted zone after it’s associated with the given user pool.   However, for testing purposes, a request can be made to register and use an available AWS Cognito prefixed domain name prefix (connected with a the regio-specific AWS Cognito hostname).

#### Client Secret

Full access to the AWS Cognito managed ID token for a user (and  its attributes) will require a server-side managed  'client secret'. Click the checkbox to select for this.

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
