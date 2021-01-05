# KGE Data Sharing Use Cases

This document provides a clearing house for KGE Registry "big picture" use cases. These use cases are not
specifically prescriptive about exactly where the shared sources should be physically be located (i.e. they could
be sitting on the same server or some proxied cloud storage location, e.g. in an Amazon Web Services S3 bucket)

## Use Case 1: Downloadable TRAPI Knowledge Graph Results

When a client of a TRAPI-wrapped resource (ARA or KP) responds to a query, the resulting Knowledge Graph
could be exported into KGX formatted file that is persisted behind an endpoint of the server running the
TRAPI implementation. 

## Use Case 1.1

Variant of Use Case 1 in which the KGX data file generated as in Use Case 1 
but is copied over to, and persisted within, a central Translator KGX file archive.

## Use Case 2: Downloadable 3rd Party Generated Knowledge Graph

A Knowledge Graph represented in KGX formatted file is created by an offline data curation activity 
then persisted behind a designated Translator subproject-specific endpoint.

## Use Case 2.1

Variant of Use Case 2 in which the KGX data file generated as in Use Case 2 but is 
copied over to, and persisted within, a central Translator KGX file archive.
