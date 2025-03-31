# KGE Data Sharing Use Cases

This document provides a clearing house for KGE Registry "big picture" use cases. These use cases are not
specifically prescriptive about exactly where the shared sources should be physically be located (i.e. they could
be sitting on the same server or some proxied cloud storage location, e.g. in an Amazon Web Services S3 bucket)

**DECISION:** *In the KGE Working Group Meeting of January 6, 2021, it was the consensus that only Use Cases 1.1 and 2.1 
(i.e. upload and indexing of KGE File Sets in the "Translator KGE Archive" are the only two relevant use cases for 
implementation. TRAPI web interfaces will not be used to convey such KGE file sets to end users).*

## Use Case 1.1

Variant of Use Case 1 - KP/ARA/TRAPI resource related Knowledge Graphs - in which
the generated set of files are uploaded to, and persisted within, a central Translator KGX file Archive.

## Use Case 2.1

Variant of Use Case 2 - KGX formatted file is created by an offline data curation activity - in which
the generated set of files are uploaded to and persisted within, a central Translator KGX file Archive.

# DEPRECATED ORIGINAL USE CASES

## Use Case 1: Downloadable TRAPI Knowledge Graph Results

When a client of a TRAPI-wrapped resource (ARA or KP) responds to a query, the resulting Knowledge Graph
could be exported into KGX formatted file that is persisted behind an endpoint of the server running the
TRAPI implementation.

## Use Case 2: Downloadable 3rd Party Generated Knowledge Graph

A Knowledge Graph represented in KGX formatted file is created by an offline data curation activity 
then persisted behind a designated Translator subproject-specific endpoint.
