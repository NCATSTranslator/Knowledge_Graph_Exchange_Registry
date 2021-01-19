# Knowledge Graph Exchange Archive Web Server

The Translator Knowledge Graph Exchange Archive Web Server ("Archive") is an online host to share knowledge graphs formatted as KGX standard compliant formatted files that are indexed for access, complete with their metadata, in the Translator SmartAPI Registry.  

# Architecture & Functions

![KGE Archive Architecture](../docs/KGE_Archive_Architecture.png?raw=true "KGE Archive Architecture")

The core functions of the Archive are:

1. to provide a client interface (web form and KGX(?) command line interface modality) to upload KGX format compliant files of knowledge graphs, with partial or complete metadata.
2. if complete content metadata is not already uploaded with these files, to infer missing content metadata for the KGX files by processing those files again through KGX (?)
3. to manage the storage of such files into a suitable (cloud?) network storage location
4. to publish Translator SmartAPI Registry ("Registry") entries pointing to (meta-)data access details for these files, one per distinct knowledge graph.
5. to serve as a gateway to download such files using the API information in the Registry.
    
Note that the details and implementation of the indexing and accessing of KGE entries in the Registry are within the technical scope of the Registry, not the Archive.

To implement
The Knowledge Graph Exchange Archive API (KGEA API) defines a web service for providing metadata indexed access to KGX formatted Translator Knowledge Graph files.

# Application Programming Interface Specification

The [`api` subdirectory](../api) contains the OpenAPI 3 specification of the web service API.

# Implementation

The KGE Archive implements the KGEA API as a Python-based web service wrapping a cloud storage archive containing KGX standard compliant formatted files with their associated Translator Registry metadata.

## Dependencies

Aside from basic Python, this project uses the [openapitools openapi-generator-cli](https://www.npmjs.com/package/@openapitools/openapi-generator-cli) module to generate its server code.



## Build & Tests

T.B.A.

## Deployment

T.B.A.

# Developer Details

T.B.A.
