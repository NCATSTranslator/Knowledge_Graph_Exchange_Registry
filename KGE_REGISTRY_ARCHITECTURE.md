# Translator Knowledge Graph Exchange Registry and Archive Architecture

This discussion document will strive to compile and review general options for KGE Registry and Archive architecture supporting the 
[use cases for community-wide exchange of Translator standards compliant knowledge graphs](https://github.com/NCATSTranslator/Knowledge_Graph_Exchange_Registry/blob/master/KGE_USE_CASES.md) captured or exported as as distinct sets of KGX-formatted text files ("KGE files"). 

KGX-compliant TSV or JSON formatted files and Neo4j database text file dumps are two examples of possible file formats which could be shared. However, it is generally anticipated that KGX tooling itself will enforce a uniform KGX file format within the Translator Knowledge Graph Exchange Archive itself, thus KGE submissions must be compatible and consumable as some format recognized by the KGX tooling. 

Note that we use the acronyms "KGX" and "KGE" somewhat interchangeably, where the former pertains more to standard formats and associated tooling for interconverting Biolink Model compliant graphs in various format; the latter, more commonly designates distinct knowledge graphs being shared in the form of a metadata documented set KGX formatted files, within the Translator community and information system.
 
## Landscape of Translator Sharing of Knowledge Products

KGX formatted files are one of three channels with which Knowledge Providers (KP) implementations can share knowledge graphs, the other two channels being an implementation of the Translator Reasoner Application Programming Interface ("TRAPI") or possibly, of a non-TRAPI SmartAPI-registered bespoke APIs.  Autonomous Relay Agents (ARA) serving novel knowledge may also publish them either through KGE file sets.

The first general requirement is the ability to locate and describe such KGE files. For this purpose, [indexing of such KGE files within the SmartAPI-based Translator registry with Translator standardized metadata](https://github.com/NCATSTranslator/TranslatorArchitecture) is now a Translator community agreed requirement.

The second general requirement notes that since by design, the SmartAPI registry only records and publishes metadata about its indexed resources, for human or programmatic lookup, as OpenAPI 3 compliant Application Programming Interfaces, it has been concluded that from the standpoint of SmartAPI, **all** resources registered in the Translator Registry **must** be "API-like" in nature, both by specification and by the implementation of a live web service access.  

In alignment with this vision, all KGE files of interest will need to be wrapped behind some other implemented ("live") SmartAPI OpenAPI 3 API endpoint.  The KGE Archive API is proposed to be that specification and (by default) a NCATS-hosted Translator KGE Archive implementing the KGE Archive API is also proposed for implementation and deployment.

### General Types of KGE File Sets to be Shared

The KGE files to be shared could be the full or a partial subset of knowledge graph contents representing their underlying knowledge sources: TRAPI-wrapped KP (or possibly, ARA-embedded KP) or non-KP (non-ARA) knowledge set (e.g. of Biolink Model compliant Semantic Medline Database knowledge graph). There may also be the potential to cache knowledge graph results from KP or ARA queries as KGE files for further reuse in later queries or knowledge workflow integration.

### Translator KGE Archive

The results of a community survey some months ago suggested that all Translator teams would avail of the option to host all the KGE file sets that they generate in a common Translator community location. This is purpose of specifying a central "Translator KGE Archive" as a reference implementation of a [KGE Archive API](https://github.com/NCATSTranslator/Knowledge_Graph_Exchange_Registry/blob/master/api/kgea_api.yaml), although in principle, additional specialised KGE Archives could be implemented by teams for independent management of their KGE files.

The current concept of the Translator Archive Archive is not prescriptive about exactly where the KGE files themselves will be hosted: they may reside within the web server running the Archive or perhaps to a NCATS-hosted cloud storage site).

### Metadata Access

Some mechanism will be required to publish ([Translator standard metadata](https://github.com/NCATSTranslator/TranslatorArchitecture/blob/master/RegistryMetadata.md) to describe the contents of KGE files. Given that discussions are underway to add a new [TRAPI Knowledge Map endpoint](https://github.com/NCATSTranslator/ReasonerAPI/pull/171/files), that will serve publish knowledge graph content metadata for TRAPI wrapped resources, such content metadata will be dynamically updated as the KP (or ARA) evolves with time.  Although KGE file metadata may be more static in nature, it is now the consensus of the Working Group that the KGE Archive API can implement an equivalent `/knowledge_map` endpoint to remain harmonized with the TRAPI standard for serving such metadata to the users of the system.  Further design discussions is required to discern the precise overlap in functionality between the TRAPI and KGE Archive API implementation, and to discern what additional endpoints may be useful in the KGE Archive in addition to the `/knowledge_map` endpoint.

The proposed use of such an endpoint is not currently prescriptive about how the KGE Archive itself will manage such metadata in files or in a database.

## KGE File Registry

Irrespective of the how the metadata is transmitted and its specific composition, it is apparent that the KGE Archive will host an arbitrary number of distinct TRAPI and and non-TRAPI KGE file sets to be indexed for sharing.  There appears to be a consensus that the indexing of such distinct KGE file sets will be the responsibility of the Translator SmartAPI Registry ("the Registry") and that the Registry will ideally be represented each distinct KGE File Set as an independent entry within the Registry, even if the base URIs of these entries simply resolve into a set of distinct REST URI paths on a single Translator Archive web server, to provide access the specific metadata for each KGE files instance, primarily through the channel of a `/knowledge_map` endpoint, one per distinct KGE file set. One example of this design concept is the https://automat.renci.org.

How the KGE Archive will publish the existence of uploaded KGE file sets, to the Registry, is a design detail to be specified.
