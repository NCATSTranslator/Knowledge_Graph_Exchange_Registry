# Getting Started

The Translator Knowledge Graph Exchange Archive Web Server ("Archive") is an online host to share knowledge graphs formatted as KGX standard compliant formatted files that are indexed for access, complete with their metadata, in the Translator SmartAPI Registry.  This document mainly focuses on the practical activities for local development and production system deployment. For details on the more esoteric development details (e.g. of OpenAPI 3 code generation), see the complementary [Road Map](KGE_ARCHIVE_ROADMAP.md) and [Development Notes](DEVNOTES.md) documents.

## Table of Contents

- [Deployment for Development](#deployment-for-development)
    - [Cloning the Code](#cloning-the-code)
    - [Configuration](#configuration)
        - [`pipenv`](#pipenv)
            - [Upgrading or Adding to the System via `pipenv`](#upgrading-or-adding-to-the-system-via-pipenv)
        - [Amazon Web Services Configuration](#amazon-web-services-configuration)
        - [Project Configuration File](#project-configuration-file)
        - [Other Prerequisites](#other-prerequisites)
        - [Project Python Package Dependencies](#project-python-package-dependencies)
    - [Basic Operation of the Server during Development](#basic-operation-of-the-server-during-development)
    - [Running the Application within a Docker Container](#running-the-application-within-a-docker-container)
        - [Installation of Docker](#installation-of-docker)
            - [Testing Docker](#testing-docker)    
- [Deployment for Production](#deployment-for-production)
    - [Operating System](#operating-system)
    - [Cloud Deployment](#cloud-deployment)
        - [Docker Storage Considerations on the Cloud](#docker-storage-considerations-on-the-cloud)
        - [Configuration for Amazon Web Services](#configuration-for-amazon-web-services)
    - [Installing Docker and Compose](#installing-docker-and-compose)
        - [Testing Docker Compose](#testing-docker-compose)
    - [Site Configuration](#site-configuration)
        - [Configuring AWS](#configuring-aws)
        - [Domain and Hostname](#domain-and-hostname)
        - [NGINX Installation and Configuration](#nginx-installation-and-configuration)
        - [Securing the Site](#securing-the-site)
        - [User Authentication and Authorization](#user-authentication-and-authorization)
        - [Running the Production System as a Docker Compose System Daemon](#running-the-production-system-as-a-docker-compose-system-daemon)

# Deployment for Development

## Cloning the Code

Make sure that you have a copy of [git installed](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git). Then, in your chosen project workspace location, either Git clone project using HTTPS...

```shell
$ git clone https://github.com/NCATSTranslator/Knowledge_Graph_Exchange_Registry.git
```

... or with SSH

```shell
$ git clone git@github.com:NCATSTranslator/Knowledge_Graph_Exchange_Registry.git
```

## Configuration

We developed the project with the recent Python release (3.9 as of January 2021). If you have multiple Python releases on your machine, you can use the [update-alternatives](https://linuxconfig.org/how-to-change-from-default-to-alternative-python-version-on-debian-linux) to set your default to Python 3.9. Better yet, use `pipenv` to manage the Python version in its own virtual environment, as follows.

### Pipenv

**NOTE: Docker deployment of the system does not (currently) use the `pipenv` to manage dependencies but Dockerfile calls to `pip` using requirements.txt files in the root subdirectory, thus pipenv installation is not necessary. However, pipenv is useful for local development deployments (outside Docker containers).**

The project can use the [`pipenv` tool](https://pipenv-fork.readthedocs.io/en/latest/) to manage project dependencies and building, for bare metal development and testing. To install the tool (assuming a user-centric local installation), type:

```shell
python -m pip install pipenv
```

(note: we use the 'module' access to pip to ensure that we are installing our tools and dependencies under the correct Python installation on our system).  Sometimes, as needed, `pipenv` may be upgraded:

```shell
python -m pip install --upgrade pipenv
```

After `pipenv` is installed, it is used to create a virtual environment and install the required Python dependencies to the project (including the necessary Python release).  

Developers installing an existing Github clone of the project generally just want to install previously specified dependencies, in which case, a simple command may be run in the root project directory on one's own development machine:

```shell
pipenv install
```

This uses the existing `PipFile` project configuration in the root project directory, which is persisted in the project repository.  This also ensures installation and use of the required version of Python (3.9 as of January 2021).

#### Upgrading or Adding to the System via `pipenv`

Developers may sometimes wish or need to upgrade the project over time with updated versions of existing project Python package dependencies (including the Python release being used for the project) or add new package dependencies. This is once again easily accomplished using `pipenv`.

To upgrade the project to a specific Python release and set up a new virtual environment using it, the following is typed:

```shell
pipenv install --python 3.#
```

Where '#' is the number of the desired Python 3 release (e.g. perhaps '10', when it is stably released)

To update existing packages:

1. Want to upgrade everything? Just do ```pipenv update```
2. Want to upgrade packages one-at-a-time?  Do ```pipenv update <some-existing-python-package>``` for each outdated package.

To install new packages into the project.

```shell
pipenv install <some-new-python-package>
```

Note that pipenv, like pip, can install packages from various sources: local, pypi, github, etc. See the [`pipenv` documentation](https://pipenv-fork.readthedocs.io/en/latest/basics.html) for guidance.

Permanent package additions to the project should also be added to the project root directory `requirements.txt` (or `requirements-dev.txt` if only used for development builds) then added to the `pipenv` build by typing:

```
pipenv install -r requirements.txt
```

### Amazon Web Services Configuration

The KGE Archive uses various Amazon Web Services to perform its work, such as AWS S3 for storing KGX-formatted dumps of knowledge graphs with associated metadata.  When a user registers a **KGE File Set**, it reserves a location on S3, which the system uses to receive the (meta-)data files from the upload.  The system also leverages other AWS services like EC2 (the server it runs upon if in AWS), Cognito (for user authentication) and SNS (for user notification of KGE updates).

Access to these resources requires configuration of AWS credentials, consisting of an access key id and a secret key. However, storing and maintaining such credentials (i.e. cycling them, as best secure practice demands) is problematic overhead.

Therefore, the latest iteration of the Archive system manages system access to AWS by using a host AWS account IAM Role request temporary AWS credentials. This IAM Role needs to have a suitable AWS service access policies in place (e.g. [Identity and access management in Amazon S3](https://docs.aws.amazon.com/AmazonS3/latest/dev/s3-access-control.html)).

To configure this access management, the host AWS account number (`host_account`), a guest-specified (and host-managed IAM role recorded) `external_id` plus the name of the host role (`iam_role_name`), need to be recorded within the project configuration file (next section).  The `external_id` is not completely secret within the system, but it should be a relatively long (uuid4?) identifier kept relatively confidential between the host and guest account administrators.

NOTE: 'Development' deployments may rely on the existence of local .aws credentials of the developer, for the `AssumeRole` operation to work, whereas, production deployment on an EC2 server may be configured as a server-level IAM role.

### Project Configuration File

To configure the proper running of the Archive, a configuration file must be set up. It must be located in the `kgea/config` subdirectory of the project and be based on the `config.yaml-template` YAML project configuration template located at that location.  To apply a specific site configuration, make a copy of the template, rename it to simply `config.yaml` (without the `-template` suffix) then fill out the required deployment site-specific configuration parameters (comments provided in the template file).

The configuration file sets the target AWS S3 storage bucket name and user AWS Cognito authentication parameters. It also can contain (optional) AWS credential configuration (optional if another mode of [AWS Configuration](#amazon-web-services-configuration) is used):

```yaml
# the actual base URL of a deployed KGE Archive site
# should also be set as the base URI in the configuration
# of the 'redirect_uri' of the AWS Cognito User Pool app
site_hostname: 'https://kgea.translator.ncats.io'

aws:
  host_account: '<Host AWS Account Number>'
  guest_external_id: '<Guest-specified external identifier'
  iam_role_name: '<Host-specified IAM Role name>'
  s3:
    # Amazon S3 storage structure
    bucket: 'kgea-bucket'         # REQUIRED: the name of the S3 bucket that will host your kgea files
    archive-directory: 'kge-data' # REQUIRED: the name of the bucket subfolder containing the KGE Archive file sets
    
    # AWS Cognito OAuth2 transaction parameters
    # These parameters should match those set as 'app client' parameters in Cognito
    # i.e. in the  Dashboard at https://console.aws.amazon.com/cognito/users/
  cognito:
    host:      '<AWS Cognito URL>'
    client_id: '<myClientid>'     # get from AWS Cognito User Pool app
    client_secret: '<myClientSecret>'     # get from value set in the AWS Cognito User Pool app
    site_uri:  '<myArchiveSiteURL>' # get from AWS Cognito User Pool app
    login_callback:  '/oauth2callback'

github:
    token: ''

# Uncomment and set this configuration tag value to override
# hardcoded default of 3 KGX validation worker tasks
# No_KGX_Validation_Worker_Tasks: 3

# This parameter is automatically set by the system when
# EncryptedCookieStorage serves for user session management 
# secret_key: ''
```

Now when you run the Archive application, this file will be read in, and the specified AWS access parameters used to connect to S3 (and other required AWS operations). NOTE: `config.yaml` is in `.gitignore`, but its template is not. 

## Other Prerequisites

In development (DEVMODE=1), we use a local AIOHTTP Session management, that requires [installation of the `cryptography` Python package](https://cryptography.io/en/latest/installation.html).

## Project Python Package Dependencies

The project has several Python package dependencies.  Installing the required Python dependencies requires execution of the following from within the root directory, after the `pipenv` tool itself plus all other non-Python external software (see above) are installed:

```shell
pipenv install
```

NOTE: Dependencies only need to be installed on a local system during development. Production deployment of the system uses Docker (see below) which installs the required dependencies inside the container.

## Basic Operation of the Server during Development

During development, it may be convenient to simply run the application from the command line. We split the application into multiple components which are run in parallel (preferably each within their own Python virtual environment, to be safe):

- A web user interface (kgea/server/web_ui)
- A back end web services API (kgea/server/web_services)

With respect to command line execution, we start each component from within the root KGEA Archive project directory as independent Python module processes (e.g. as separate run configurations in your IDE, or in separate terminal shells).

Unless you expose your development server with a hostname to the internet, you would need to run the server with the DEV_MODE flag set (with a non-false value), so that the application does not attempt to authenticate externally using AWS Cognito (see below). Note that before running with the DEV_MODE flag, you must also install additional pip development package dependencies:

```
pip install -r requirements-dev.txt

# or the pipenv equivalent...
pipenv install -r requirements-dev.txt
```

### The Web User interface

```python
DEV_MODE=1 python -m kgea.server.web_ui
```

### Back End Web Services

```python
DEV_MODE=1 python -m kgea.server.web_services
```

# Running the Application within a Docker Container

The simpler way to deploy and run the application is within a Docker container.

## Installation of Docker

Note that you may first need to install `curl` before installing Docker:

```shell
$ sudo apt-get install curl
```

To run Docker, you'll obviously need to [install Docker first](https://docs.docker.com/engine/installation/) 
in your target Linux operating environment (bare metal server or virtual machine running Linux).

For our installations, we typically use Ubuntu Linux, for which there is an 
[Ubuntu-specific docker installation using the repository](https://docs.docker.com/engine/installation/linux/docker-ce/ubuntu/#install-using-the-repository). There is also a [post installation step with Linux](https://docs.docker.com/engine/install/linux-postinstall/) to allow the running of docker as a regular user (i.e. without `sudo`).

For other installations, please find instructions specific to your choice of Linux variant, on the Docker site.

### Testing Docker

In order to ensure that Docker is working correctly, run the following command:

```shell
$ docker run hello-world
```

This should result in something akin to the following output:

```shell
$ docker run hello-world

Hello from Docker!
This message shows that your installation appears to be working correctly.

To generate this message, Docker took the following steps:
 1. The Docker client contacted the Docker daemon.
 2. The Docker daemon pulled the "hello-world" image from the Docker Hub.
    (amd64)
 3. The Docker daemon created a new container from that image which runs the
    executable that produces the output you are currently reading.
 4. The Docker daemon streamed that output to the Docker client, which sent it
    to your terminal.

To try something more ambitious, you can run an Ubuntu container with:
 $ docker run -it ubuntu bash

Share images, automate workflows, and more with a free Docker ID:
 https://hub.docker.com/

For more examples and ideas, visit:
 https://docs.docker.com/get-started/
```

## Running the Application in Docker

After Docker is installed, running the container is easy. Here we add a few flags to run it as a daemon (the `-d` flag) and ensure that the container is removed after it is stopped (the `--rm` flag). We also expose it to port 80, the regular http port (using `-p 80:8080`).

```shell
$ cd kgea/server
$ docker build -t kge-test .
$ docker run --rm  --name kge-test-run -d -p 80:8080 kge-test

# check the logs
$ docker logs -f kge-test-run
```

The web services UI should now be visible at http://localhost/kge-archive/ui.

To shut down the server:

```shell
$ docker stop kge-test-run
```

# Deployment for Production

The KGE Archive can be run as a standalone application but for production deployments, the KGE Archive system is typically run within a **Docker** container when the application is run on a Linux server or virtual machine (e.g. on an AWS EC2 cloud server instance).

## Operating System

We primarily wrote the Archive web application in Python, so in principle, it can tested and run on various operating systems. Our main focus here will be a Linux production deployment (specifically, Ubuntu/Debian flavor of Linux), so production deployment details will be biased in that direction. We leave it to other members of the interested user community to adapt these deployment details to other operating system environments (e.g. Microsoft Windows 10, Mac OSX, etc.).

## Cloning the code

As above, we [git clone the Code](#cloning-the-code) for production as well, this time, into a newly created `/opt/projects` directory (with user account accessible permissions). Within the NGINX config file, we set the HTML `root` path to point to the path to the `.../kgea/server/web_ui/templates` subdirectory, where we maintain the static css and images (see below).

## Cloud Deployment

The production deployment of the Archive web application targets the Amazon Web Service (AWS) cloud, specifically, EC2 server instances and S3 network storage. We do not cover the basic details of AWS account, EC2 and S3 setup here, except with respect to details specific to the design and operation of the Archive. For those details, consult [AWS EC2 and related documentation](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/EC2_GetStarted.html). 

Pay attention to the need to set up a Virtual Private Cloud (VPC) with an Internet Gateway with suitable Routing Tables to enable internet access to the server. 

Here, we assume, as a starting point, a modest sized live instance AWS EC2 instance running Ubuntu 20.04 or better. A basic 'configuration' deployment targets a T3-Medium (2 CPU/4GB RAM) instance, which can be upsized later, as use case performance demands, perhaps to a T3-Large (4 CPU/4GB RAM) or better. with a Security Group configured for SSH and HTTPS internet access (see below). Installation of the Archive system on such a running server simply assumes developer (SSH) command line terminal access.

### Docker Storage Considerations on the Cloud

By default, the Docker image/volume cache (and other metadata) resides under **/var/lib/docker**. By default, this directory will end up being hosted on the root volume of a cloud image, which can sometimes be relatively small. To avoid "out of file storage" messages, which relate to limits in inode and actual byte storage, Ttere are two basic options:

#### Option 1

When creating the server (e.g. EC2 instance), ensure that the root volume is "_large enough_" (we don't have a hard number, but we generally aim for 50 gigabytes in size).

#### Option 2

You can remap the **/var/lib/docker** directory onto another larger (AWS EBS) storage volume (which should, of course, be configured to be automounted by _fstab_ configuration). Such a volume should generally be added to the cloud instance at startup but if necessary, added later (see [AWS EBS documentation](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/AmazonEBS.html) for further details).

In effect, it is generally useful to host the entire portal and its associated docker storage volumes on such an extra mounted volume. We generally use the **/opt** subdirectory as the target of the mount, then directly install various code and related subdirectories there, including the physical target of a symbolic link to the **/var/lib/docker** subdirectory. You will generally wish to set this latter symbolic link first before installing Docker itself.  Here, we assume that docker has _not_ yet been installed (let alone running). Attaching a suitably sized AWS EBS  volume (we used 50GB) to the server instance, then run the following CLI commands:

    # Verify the existence of the volume, in this case, xvdb
    $ lsblk
    NAME    MAJ:MIN RM  SIZE RO TYPE MOUNTPOINT
    ...
    xvda    202:0    0    8G  0 disk
    └─xvda1 202:1    0    8G  0 part /
    xvdb    202:16   0   50G  0 disk 

    # First, initialize the filing system on the new, empty, raw volume (assumed here to be on /dev/vdb)
    $ sudo mkfs -t ext4 /dev/xvdb 
   
    # Mount the new volume in its place (we assume that the folder '/opt' already exists)
    $ sudo mount /dev/xvdb /opt

    # Provide a symbolic link to the future home of the docker storage subdirectories
    $ sudo mkdir /opt/docker
    $ sudo chmod go-r /opt/docker
    
    # It is assumed that /var/lib/docker doesn't already exist. 
    # Otherwise, you'll need to delete it first,
    $ sudo rm -rf /var/lib/docker  # optional, if necessary

    # then create the symlink
    $ sudo ln -s /opt/docker /var/lib  
    
Now, you can proceed to install Docker and Docker Compose.

### Configuration for Amazon Web Services

Refer to [Amazon Web Services Configuration](#amazon-web-services-configuration) above.

## Installing Docker and Compose

After [Installing Docker](#installation-of-docker), you will then also need to [install Docker Compose](https://docs.docker.com/compose/install/) alongside Docker in your target Linux operating environment.

### Testing Docker Compose

In order to ensure Docker Compose is working correctly, issue the following command:

```shell
$ docker-compose --version
docker-compose version 1.29.2, build 5becea4c
```
Note that your particular version and build number may be different than what is shown here.
We don't currently expect that docker-compose version differences should have a significant
impact on the build, but if in doubt, refer to the release notes of the docker-compose site for advice.

## Site Configuration

### Configuring AWS

Refer to [Amazon Web Services Configuration](#amazon-web-services-configuration).  See also [IAM roles for Amazon EC2 instances](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_use_switch-role-ec2.html).

### Domain and Hostname

Set an 'A' DNS record to resolve to a suitable hostname prefix with your DNS pointing to the IP of the NGINX server. For performance reasons, a standard web server program (we use NGINX; see the next section) needs to be configured to serve as a proxy to the Archive web application running in the background.

### NGINX Installation and Configuration

NGINX can be operated directly as a program in the operating system or in a Docker container.
For now, we choose the direct installation option for simplicity of SSL/HTTPS management. On Ubuntu, typing:

```shell
sudo apt install nginx
```

installs the software.

Next, a copy of the `kgea_nginx.conf-template` file (located under the `deployment` subdirectory of the project) is made into the `/etc/nginx/sites-available` folder, then the **localhost** placeholder text replaced with the desired KGE Archive hostname.

Note that this virtual host configuration proxies to the KGE Archive web ui and service applications which are running in docker containers locally visible on http://localhost on ports 8090 and 8080, respectively.

The NGINX root locations for other static site files (e.g. css) may also be adjusted to site preferences. We provide some templated static files in the subdirectories of the project `.../kgea/server/web_ui/templates` subdirectory (like `css/styles.css-template`, `images`, etc.) that must be copied into the designated location and customized as desired. In particular, correct appearance of the Archive web pages requires the following:

1. The `.../templates/css/styles.css-template` should be copied into a `styles.css` file the NGINX `kge_nginx.conf` specified path for `/css/`
1. A suitable `banner.jpg` logo image should be placed, alongside other `.../templates/images` files (i.e. `help-icon.png`) into the NGINX `kge_nginx.conf` specified path for `/images/` 


Finally, a symlink is made to this `sites-available` file into the `/etc/nginx/sites-enabled` subdirectory:

```shell
cd /etc/nginx/sites-enabled
ln -s ../sites-available/kge_nginx.conf
```

It is a good idea to validate the `nginx.conf` configurations first by running the nginx command in '_test_' mode:

```shell
nginx -t
```

The NGINX server needs to be (re-)started for the changes to be applied. The administrative control of the NGINX server daemon is as follows:

```shell
sudo systemctl <cmd> nginx
```

where <cmd> can be 'status', 'start', 'stop' and 'restart'.

### Securing the Site

The KGE Archive enforces user authentication (using AWS Cognito). For this to properly work, the Archive needs to be hosted behind HTTPS / SSL. 

Suitable **https** SSL certification can be applied to the specified KGE server hostname onto the NGINX configuration file following the instructions - specific to NGINX under Linux -  for the [CertBot tool](https://certbot.eff.org/). Certbot is an open SSL configuration tool associated with [Lets Encrypt](https://letsencrypt.org/).  After installing the CertBot tool as recommended on their site, we run Certbot command as follows:

```shell
sudo certbot --nginx
```

Certbot easily sets up SSL/HTTPS for your NGINX configured hostname, that should be visible in the `/etc/nginx/sites-enabled` subdirectory (see above).

### User Authentication and Authorization

After we set up the server, the hostname particulars can be used to [configure AWS Cognito for OAuth2-based user authentication and authorization on the system](KGE_CLIENT_AUTHENTICATION_AUTHORIZATION.md). See also the [Project Configuration File](#project-configuration-file) above.

## Running the Production System as a Docker Compose System Daemon

After we build the Archive stack with `docker-compose build`, we deploy it as a service daemon on the system.
First, we copy the `deployment/kgea.service` template for `systemd` deployment of the Docker Compose managed image into `/etc/systemd/system/kgea.service`. Then, we enable it:

```
sudo systemctl enable kgea  # the root file name of the service
```

We can then now use the systemctl command to manage its execution:

``` 
$ sudo systemctl <command> kgea
```

where command may be `start`, `restart`, `stop` or `status`.
