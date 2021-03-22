# Getting Started

The Translator Knowledge Graph Exchange Archive Web Server ("Archive") is an online host to share knowledge graphs formatted as KGX standard compliant formatted files that are indexed for access, complete with their metadata, in the Translator SmartAPI Registry.  This document mainly focuses on the practical activities for local development and production system deployment. For details on the more esoteric development details (e.g. of OpenAPI 3 code generation), see the complementary [Road Map](KGE_ARCHIVE_ROADMAP.md) and [Development Notes](DEVNOTES.md) documents.

## Table of Contents

- [Development Deployment](#development-deployment)
    - [Cloning the Code](#cloning-the-code)
    - [Configuration](#configuration)
        - [`pipenv`](#pipenv)
            - [Upgrading or Adding to the System via `pipenv`](#upgrading-or-adding-to-the-system-via-pipenv)
        - [Amazon Web Services Configuration](#amazon-web-services-configuration)
            - [AWS Configuration Files](#aws-configuration-files)
            - [AWS Environment Variables](#aws-environment-variables)
        - [Project Configuration File](#project-configuration-file-recommended)
        - [Other Prerequisites](#other-prerequisites)
        - [Project Python Package Dependencies](#project-python-package-dependencies)
    - [Basic Operation of the Server](#basic-operation-of-the-server)
    - [Running the Application within a Docker Container](#running-the-application-within-a-docker-container)
        - [Installation of Docker](#installation-of-docker)
            - [Testing Docker](#testing-docker)    
- [Production Deployment](#production-deployment)
    - [Operating System](#operating-system)
    - [Cloud Deployment](#cloud-deployment)
        - [Docker Storage Considerations on the Cloud](#docker-storage-considerations-on-the-cloud)
        - [Configuration for Amazon Web Services](#configuration-for-amazon-web-services)
    - [Installing Docker Compose](#installing-docker-compose)
        - [Testing Docker Compose](#testing-docker-compose)
    - [Site Configuration](#site-configuration)
        - [Domain and Hostname](#domain-and-hostname)
        - [Securing the Site](#securing-the-site)
            - [NGINX Installation and Configuration](#nginx-installation-and-configuration)
            - [Configuring NGINX for HTTPS](#configuring-nginx-for-https)
        - [WSGI Deployment](#wsgi-deployment)
    - [Client User Authentication](#client-user-authentication)
    - [Configure AWS](#configure-aws)
    - [Running the Production System](#running-the-production-system)

# Development Deployment

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

The project is developed in the latest Python release (3.9 as of January 2021). If you have multiple Python releases on your machine, you can use the [update-alternatives](https://linuxconfig.org/how-to-change-from-default-to-alternative-python-version-on-debian-linux) to set your default to Python 3.9. Better yet, use `pipenv` to manage the Python version in its own virtual environment, as follows.

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

The KGE Archive uses AWS S3 for storing KGX-formatted dumps of knowledge graphs with associated metadata.  When a user registers a **KGE File Set**, it reserves a location on S3, which can then be used to receive the (meta-)data files from the upload. 

Access to these resources requires configuration of AWS credentials consisting of an access key id and a secret key. These AWS credentials need to be associated with an IAM user with a suitable S3 access policy in place (see [Identity and access management in Amazon S3](https://docs.aws.amazon.com/AmazonS3/latest/dev/s3-access-control.html)).

There are three options to configure AWS credentials for the KGE Archive system: in AWS configuration files, using environment variables, or, using this project's configuration template.

#### AWS Configuration Files

On Ubuntu Linux, the `awscli` can be installed to facilitate administration (plus _ad hoc_ access to AWS services). Type:

```shell
sudo apt install awscli
```

after which time, aws credentials can be specified and stored on the system using the command:

```shell
aws configure
```

This command will record the requested parameters inside of `~/.aws/credentials` or `~/.aws/config` which, by default, KGE will take as its AWS credentials. This is a convention inherited from [boto3](https://boto3.amazonaws.com/v1/documentation/api/1.12.1/index.html), which you can read about in [here](https://boto3.amazonaws.com/v1/documentation/api/1.12.1/guide/quickstart.html#configuration). 

Note that the Docker option of launching the application, currently assumes that $HOME/.aws exists, whose contents can be bound into the container as a volume binding, for use by the web application.

#### AWS Environment Variables

If you don't really want to store your keys outside the project root directory, [Boto can use AWS environment variables](https://boto3.amazonaws.com/v1/documentation/api/1.12.1/guide/configuration.html?highlight=environment#environment-variables). 

### Project Configuration Files

To configure the proper running of the Archive, a configuration file must be set up. It must be located in the `kgea/server/config` subdirectory of the project and be based on the `config.yaml-template` YAML project configuration template located at that location.  To apply a specific site configuration, make a copy of the template, rename it to simply `config.yaml` (without the `-template` suffix) then fill out the required deployment site-specific configuration parameters (comments provided in the template file).

The configuration file sets the target AWS S3 storage bucket name and user AWS Cognito authentication parameters. It also can contain (optional) AWS credential configuration (optional if another mode of [AWS Configuration](#amazon-web-services-configuration) is used):

```yaml
oauth2:
  host:      '<AWS Cognito URL>'
  client_id: '<myclientid>'     # get from AWS Cognito User Pool app
  site_uri:  '<ArchiveSiteURL>' # get from AWS Cognito User Pool app
  login_callback:  '/oauth2callback'

bucket: 'kgea-bucket'   # REQUIRED: the name of the S3 bucket that will host your kgea files

# Either fill out `credentials_file` and `credentials_mode`, OR fill out `credentials:aws_access_key_id` and `credentials:aws_secret_access_key`
credentials_file: ''                # if not specified, by default it should be in your home folder under `~/.aws/credentials`, formatted like a .ini file
credentials_mode: 'default'         # the part of the credentials to use. Allows for multiple setups, e.g. [dev], [production], [default]
# these local keys are used to specify access key and secret key for the project
# otherwise, the credentials file can be overridden using these local keys
credentials:
  aws_access_key_id: '...'         # the 20 character AWS access key id
  aws_secret_access_key: '...'     # the 40 character AWS secret key
```

Now when you run the Archive application, this file will be read in, and the specified AWS access parameters used to connect to S3 (and other required AWS operations).

NOTE: `config.yaml` is in `.gitignore`, but its templates not. That said, if you are worried about your AWS keys getting into source control, you may use one of the two other available [AWS Configuration](#amazon-web-services-configuration) approaches.

## Other Prerequisites

In development, we use a local AIOHTTP Session management, that requires [installation of the `cryptography` Python package](https://cryptography.io/en/latest/installation.html).

## Project Python Package Dependencies

The project has several Python package dependencies, but these are actually already recorded in the Pipfile which `pipenv` manages. Therefore, installing the required Python dependencies merely requires execution of the following from within the root directory, after the `pipenv` tool itself plus all other non-Python external software (see above) are installed :

```shell
pipenv install
```

## Basic Operation of the Server

During development, it may be convenient to simply run the application from the command line. The application is currently split into multiple components running in parallel (preferrably each within their own Python virtual environment, to be safe):

- A web user interface (kgea/server/web_ui)
- A back end web services API (kgea/server/web_services)
- A KGX validation tool (T.B.A.)

With respect to command line execution, each component may be started from within the root KGEA Archive project directory as independent Python module processes (e.g. as separate run configurations in your IDE, or in separate terminal shells).

Run with the DEV_MODE flag set, the application does not attempt to authenticate externally using AWS Cognito, see below. Note that before running with the DEV_MODE flag, you must also install the pip development package dependencies, namely

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
$ sudo docker run hello-world
Unable to find image 'hello-world:latest' locally
latest: Pulling from library/hello-world
0e03bdcc26d7: Pull complete
Digest: sha256:31b9c7d48790f0d8c50ab433d9c3b7e17666d6993084c002c2ff1ca09b96391d
Status: Downloaded newer image for hello-world:latest

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

# Production Deployment

The KGE Archive can be run as a standalone application but for production deployments, the KGE Archive system is typically run within a **Docker** container when the application is run on a Linux server or virtual machine (e.g. on an AWS EC2 cloud server instance). Some preparation is required.

## Operating System

The Archive web application is mainly written in Python, so in principle, can tested and run on various operating systems. Our main focus here will be a Linux production deployment (specifically, Ubuntu/Debian flavor of Linux), so production deployment details will be biased in that direction. We leave it to other members of the interested user community to adapt these deployment details to other operating system environments (e.g. Microsoft Windows 10, Mac OSX, etc.).

## Cloud Deployment

The production deployment of the Archive web application targets the Amazon Web Service (AWS) cloud, specifically, EC2 server instances and S3 network storage. We do not cover the basic details of AWS account, EC2 and S3 setup here, except with respect to details specific to the design and operation of the Archive. For those details, consult [AWS EC2 and related documentation](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/EC2_GetStarted.html). Pay attention to the need to set up a Virtual Private Cloud (VPC) with an Internet Gateway with suitable Routing Tables to enable internet access to the server. 

Here, we assume, as a starting point, a modest sized live instance AWS EC2 instance running Ubuntu 20.04 or better. We started installations on a live T2-Micro, to be upsized later as use case performance demands)  properly secured for SSH and HTTPS internet access. Installation of the Archive system on such a running server simply assumes developer (SSH) command line terminal access.

Note that AWS has several complementary options for (Flask) web application deployment, such as [Elastic Beanstalk](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/create-deploy-python-flask.html). The utility of deploying the KGE Archive within one of these frameworks could be revisited in the future.

### Docker Storage Considerations on the Cloud

By default, the Docker image/volume cache (and other metadata) resides under **/var/lib/docker** which will end up being hosted on the root volume of a cloud image, which is generally of relatively modest size. To avoid "out of file storage" messages, which related to limits in inode and actual byte storage, it is advised that you remap the **/var/lib/docker** directory onto another larger (AWS EBS) storage volume (which should, of course, be configured to be automounted by _fstab_ configuration). Such a volume should generally be added to the cloud instance at startup but if necessary, added later (see [AWS EBS documentation](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/AmazonEBS.html) for further details).

In effect, it is generally useful to host the entire portal and its associated docker storage volumes on such an extra mounted volume. We generally use the **/opt** subdirectory as the target of the mount, then directly install various code and related subdirectories there, including the physical target of a symbolic link to the **/var/lib/docker** subdirectory. You will generally wish to set this latter symbolic link first before installing Docker itself (here we assume that docker has _not_ yet been installed (let alone running). Assuming that a suitable (AWS EBS)  volume is attached to the server instance, then:

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

Refer to [Amazon Web Services Configuration](#amazon-web-services-configuration).

## Installing Docker Compose

You will then also need to [install Docker Compose](https://docs.docker.com/compose/install/) alongside Docker in your target Linux operating environment.

### Testing Docker Compose

In order to ensure Docker Compose is working correctly, issue the following command:

```shell
$ docker-compose --version
docker-compose version 1.18.0, build 8dd22a9
```
Note that your particular version and build number may be different than what is shown here. We don't currently expect that docker-compose version differences should have a significant impact on the build, but if in doubt, refer to the release notes of the docker-compose site for advice.

## Site Configuration

### Domain and Hostname

The set an 'A' DNS record to resolve to a suitable hostname prefix on an available domain to the (AWS EC2) web server's real public or have Translator proxy a hostname to the (private?) hostname or IP of the machine running on the private subnet.

### Securing the Site

The KGE Archive has client user authentication (using AWS Cognito). For this to properly work, the Archive needs to be hosted behind HTTPS / SSL.

If the server is proxied through a suitable **https** (Translator) hostname, then HTTPS/SSL access will be handled by the NGINX instance running on the core Translator server. If an independent Archive deployment is being implemented, then the Archive web application access will generally need to proxied through a locally installed copy of NGINX (next section).

#### NGINX Installation and Configuration

NGINX can be operated directly as a program in the operating system or in a Docker container. For now, we choose the direct installation option for simplicity of SSL/HTTPS management. On Ubuntu, typing:

```shell
sudo apt install nginx
```

installs the software.

Next, a copy of the `kge_nginx.conf-template` file (located under the `config` subdirectory) is made into the `/etc/nginx/sites-available` folder, then the **localhost** placeholder text replaced with the desired KGE Archive hostname.
Note that this virtual host configuration proxies to the KGE Archive web application which is assumed locally visible on http://localhost:8080 (modified this proxy insofar necessary).  

The NGINX root locations for other static site files (e.g. css) may also be adjusted to site preferences. Templated static files in the subdirectories of the project `config/static` subdirectory (like `css/styles.css-template`, `images`, etc.) should be copied into the designated location and may also be customized as desired.

Finally, a symlink is made to this 'sites-enabled' file into the `/etc/nginx/sites-enabled` subdirectory:

```shell
cd /etc/nginx/sites-enabled
ln -s ../sites-available/kge_nginx.conf
```

It is a good idea to validate the `nginx.conf` configurations first by running the nginx command in '_test_' mode:

```shell
nginx -t
```

The NGINX server needs to be (re-)started for the changes to be applied. The NGINX server daemon is generally controlled by the following:

```shell
sudo systemctl <cmd> nginx
```

where <cmd> can be 'status', 'start', 'stop' and 'restart'.

#### Configuring NGINX for HTTPS

Afterwards, **https** SSL certification can be applied to the specified KGE server hostname onto the NGINX configuration file following the instructions - specific to NGINX under Linux - for using [CertBot tool](https://certbot.eff.org/) , the SSL configuration tool associated with [Lets Encrypt](https://letsencrypt.org/).  After installing the CertBot tool as recommended on their site, following the prompts of the Certbot command will easily configure SSL/HTTPS (your NGINX configured hostname should be visible in the Certbot list (after it was linked into the `/etc/nginx/sites-enabled` subdirectory, see above):

```shell
sudo certbot --nginx
```

### WSGI Deployment

Looking at the Flask server log (using `docker-compose log`), the following start-up message will be noted:

```
kge_1  |  * Serving Flask app "__main__" (lazy loading)
kge_1  |  * Environment: production
kge_1  |    WARNING: This is a development server. Do not use it in a production deployment.
kge_1  |    Use a production WSGI server instead.
kge_1  |  * Debug mode: off
kge_1  |  * Running on http://0.0.0.0:8080/ (Press CTRL+C to quit)
```

While lightweight and easy to use, Flask’s built-in server is not suitable for production as it doesn’t scale well.  For this reason, one needs to consider WSGI servers. The [deployment options for WSGI](https://flask.palletsprojects.com/en/1.1.x/deploying/), accordingly, suggest suitable adjustments to the production NGINX and KGE Archive Python application installation and configuration.

## Client User Authentication

The [Archive system leverages AWS Cognito for its client user authentication](KGE_CLIENT_AUTHENTICATION_AUTHORIZATION.md). The  HHTPS schema-prefixed hostname needs to be specified as the login URL's callback endpoint, through the Archive software site configuration.

### Configure AWS

Refer to [Amazon Web Services Configuration](#amazon-web-services-configuration).

## Running the Production System

T.B.A.
