# Knowledge Graph Exchange Archive Web Server

The Translator Knowledge Graph Exchange Archive Web Server ("Archive") is an online host to share knowledge graphs formatted as KGX standard compliant formatted files that are indexed for access, complete with their metadata, in the Translator SmartAPI Registry.  

# Architecture & Functions

![KGE Archive Architecture](./docs/KGE_Archive_Architecture.png?raw=true "KGE Archive Architecture")

The core functions of the Archive are:

1. to provide a client interface (web form and KGX(?) command line interface modality) to upload KGX format compliant files of knowledge graphs, with partial or complete metadata.
2. if complete content metadata is not already uploaded with these files, to infer missing content metadata for the KGX files by processing those files again through KGX (?)
3. to manage the storage of such files into a suitable (cloud?) network storage location
4. to publish Translator SmartAPI Registry ("Registry") entries pointing to (meta-)data access details for these files, one per distinct knowledge graph.
5. to serve as a gateway to download such files using the API information in the Registry.
    
Note that the details and implementation of the indexing and accessing of KGE entries in the Registry are within the technical scope of the Registry, not the Archive.

# Design Overview

The proposed implementation of the Archive is as a Python web application consisting of components running within a Docker Compose coordinated set of Docker containers, hosted on a (Translator hosted AWS EC2 cloud?) server instance and accessing suitable (Translator hosted AWS S3 or EBS cloud) storage.

Client communication with the web application will generally be through an OpenAPI 3 templated web service [specified in kgea_api.yaml](../api/kgea_api.yaml). A human browser accessible web form and/or a (KGX-based?) command line interface will be implemented to upload KGX files to the Archive web server, for further processing.

Once on the server, if the associated [Translator Resource "Content Metadata"](https://github.com/NCATSTranslator/TranslatorArchitecture/blob/master/RegistryMetadata.md#content-metadata) of the KGE files is incomplete, KGX may be run (as a background, asynchronous task) to generate the required content metadata.  To the resulting (uploaded or generated) metadata, suitable additional [Translator Resource "Provider Metadata"](https://github.com/NCATSTranslator/TranslatorArchitecture/blob/master/RegistryMetadata.md#provider-metadata) will be added.

The web application will publish KGE SmartAPI entries to the Translator SmartAPI Registry through an outgoing (web service?) automated protocol to be negotiated with the SmartAPI team.  Provider Metadata will generally be hard-coded into the API yaml file uploaded to SmartAPI (which will be similar to the kgea_api.yaml but rather, based on a [KGE file set parameterized kge_smartapi.yaml template](../api/kge_smartapi.yaml)); access to Content Metadata will be deferred to the API's "knowledge_map" endpoint published in the entry (see below). Clients (likely different from the clients which uploaded the original KGE files) will access KGE SmartAPI entries through the normal modalities of Translator SmartAPI site access.

Using accessed KGE SmartAPI metadata, clients will connect to the Archive to read the available Content Metadata, then access the files themselves though some link or protocol of file data transfer from the remote network storage (by a protocol to be further specified), for their intended local computational use.

# Getting Started

## Cloning the Code

In your code workspace, either Git clone project using HTTPS...

```shell
$ git clone --recursive https://github.com/NCATSTranslator/Knowledge_Graph_Exchange_Registry.git
```

... or with SSH

```shell
$ git clone --recursive git@github.com:NCATSTranslator/Knowledge_Graph_Exchange_Registry.git
```

# Docker Deployment of KBA

KBA is typically run within a **Docker** container when the application is run on a Linux server or 
virtual machine. Some preparation is required.

The following steps also assume that you have already run the *gradle clean build* on the project (see above) 
from within the */opt/kba/beacon-aggregator* directory of your server) to generate the requisite 
JAR file for Docker to use.

## Installation of Docker

To run Docker, you'll obviously need to [install Docker first](https://docs.docker.com/engine/installation/) 
in your target Linux operating environment (bare metal server or virtual machine running Linux).

For our installations, we typically use Ubuntu Linux, for which there is an 
[Ubuntu-specific docker installation using the repository](https://docs.docker.com/engine/installation/linux/docker-ce/ubuntu/#install-using-the-repository). There is also a [post installation step with Linux](https://docs.docker.com/engine/install/linux-postinstall/) to allow the running of docker as a regular user (i.e. without `sudo`).

Note that you may need to install `curl` first before installing Docker:

```shell
$ sudo apt-get install curl
```

For other installations, please find instructions specific to your choice of Linux variant, on the Docker site.

## Testing Docker

In order to ensure that Docker is working correctly, run the following command:

```shell
$ docker run hello-world
```

This should result in something akin to the following output:

```shell
Unable to find image 'hello-world:latest' locally
latest: Pulling from library/hello-world
ca4f61b1923c: Pull complete
Digest: sha256:be0cd392e45be79ffeffa6b05338b98ebb16c87b255f48e297ec7f98e123905c
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
 https://cloud.docker.com/

For more examples and ideas, visit:
 https://docs.docker.com/engine/userguide/
```

## Installing Docker Compose

You will then also need to [install Docker Compose](https://docs.docker.com/compose/install/) alongside Docker in your target Linux operating environment.

## Testing Docker Compose

In order to ensure Docker Compose is working correctly, issue the following command:

```shell
$ docker-compose --version
docker-compose version 1.18.0, build 8dd22a9
```
Note that your particular version and build number may be different than what is shown here. We don't currently expect that docker-compose version differences should have a significant impact on the build, but if in doubt, refer to the release notes of the docker-compose site for advice.

## Installing Project Library Dependencies

Aside from basic Python, this project uses the [openapitools openapi-generator-cli](https://www.npmjs.com/package/@openapitools/openapi-generator-cli) module to generate its server code.

## Build & Tests

T.B.A.

## Deployment

T.B.A.

# Developer Details

T.B.A.
