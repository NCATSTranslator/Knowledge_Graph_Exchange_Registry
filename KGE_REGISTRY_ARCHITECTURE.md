# Translator Knowledge Graph Exchange Registry and Archive Architecture

This discussion document will strive to compile and review general options for KGE Registry and Archive architecture supporting the 
[use cases for community-wide exchange of Translator standards compliant knowledge graphs](https://github.com/NCATSTranslator/Knowledge_Graph_Exchange_Registry/blob/master/KGE_USE_CASES.md) captured or exported as as distinct sets of KGX-formatted text files ("KGE files"). 

KGX-compliant TSV or JSON formatted files and Neo4j database text file dumps are two examples of possible file formats which could be shared. However, it is generally anticipated that KGX tooling itself will enforce a uniform KGX file format within the Translator Knowledge Graph Exchange Archive itself. 

Note that we use the acronyms "KGX" and "KGE" somewhat interchangeably, where the former pertains more to standard formats and associated tooling for interconverting Biolink Model compliant graphs in various format; the latter, more commonly designates distinct knowledge graphs being shared in the form of a metadata documented set KGX formatted files, within the Translator community and information system.
 
## Landscape of Translator Sharing of Knowledge Products

KGX formatted files are one of three channels with which Knowledge Providers (KP) implementations can share knowledge graphs, the other two channels being an implementation of the Translator Reasoner Application Programming Interface ("TRAPI") or possibly, of a non-TRAPI SmartAPI-registered bespoke APIs.  Autonomous Relay Agents (ARA) serving novel knowledge may also publish them either through KGE file sets.

The first general requirement is the ability to locate and describe such KGE files. For this purpose, [indexing of such KGE files within the SmartAPI-based Translator registry with Translator standardized metadata](https://github.com/NCATSTranslator/TranslatorArchitecture) is now a Translator community agreed requirement.

The second general requirement notes that since by design, the SmartAPI registry only records and publishes metadata about its indexed resources, for human or programmatic lookup, as OpenAPI 3 compliant Application Programming Interfaces, it has been concluded that from the standpoint of SmartAPI, **all** resources registered in the Translator Registry **must** be "API-like" in nature, both by specification and by the implementation of a live web service access.  

In alignment with this vision, all KGE files of interest will need to be wrapped behind some other implemented ("live") SmartAPI OpenAPI 3 API endpoint.  The KGE Archive API is proposed to be that specification and (by default) a NCATS hosted implementation and deployment of a reference KGE Archive is also proposed.

## Architectural Options for a KGE File Sharing

Again, with reference to [KGE files Sharing Use Cases](https://github.com/NCATSTranslator/Knowledge_Graph_Exchange_Registry/blob/master/KGE_USE_CASES.md), 
the following architectural could be envisioned:

### TRAPI Indexing Option

Many of the KGE files to be shared may actually be full or partial static knowledge graph contents exported from TRAPI-wrapped KP (or possibly, ARA-embedded KP).

Alternately (or concurrently?), standards-defined "Content Metadata" could be stored at the URL location. Such ([Translator standard metadata](https://github.com/NCATSTranslator/TranslatorArchitecture/blob/master/RegistryMetadata.md) would catalog and qualify the contents of the KGE file archive location. In any case, such metadata would have to be REST accessible with a standard file name.  This option assumes a one-to-one relationship between each collection of KGE files and their owner KP (or ARA) described by the SmartAPI entry.

The TRAPI hosting option is not prescriptive about exactly where the KGE files themselves sit: this could be any internet location accessible by REST protocols, perhaps not even within the given TRAPI implementation site of the KP (i.e. the link may point elsewhere, perhaps to a NCATS-hosted cloud storage site).

However, the use case of simply accessing metadata to locate and describe such KGE files for web access suggests that a simpler API may suffice. This is the purpose of the proposed [KGE Archive API](https://github.com/NCATSTranslator/Knowledge_Graph_Exchange_Registry/blob/master/api/kgea_api.yaml) in this project.

### Translator Central KGE File Archive

The results of a community survey some months ago suggested that Translator teams generally prefer to host all the KGE file sets that they generate on a common Translator community location. This is purpose of specifying a central "Translator KGE Archive" as a reference implementation of a KGE Archive API, although in principle, specialised KGE Archives could be implemented by teams for independent management of their KGE files.

### Metadata Access

Discussions are underway to add a new [TRAPI Knowledge Map endpoint](https://github.com/NCATSTranslator/ReasonerAPI/pull/171/files), that will serve publish knowledge graph content metadata. For full TRAPI implementations, such content metadata may be dynamically updated as the KP (or ARA) evolves with time.  It is the consensus of the Working Group that the KGE Archive API can implement an equivalent `/knowledge_map` endpoint to remain harmonized with the TRAPI standard for serving such metadata to the users of the system. Further design discussions is required to discern the precise overlap in functionality between the TRAPI and KGE Archive API implementation.

## KGE File Registry

Irrespective of the how the metadata is transmitted and its specific composition, it is likely that there will be multiple distinct TRAPI and and non-TRAPI KGE file sets to be indexed for sharing. There appears to be a consensus that the indexing will be within the Translator SmartAPI Registry ("the Registry") and will ideally be represented as multiple distinct entries in the Registry, even if the base URIs of these entries simply resolve into separate REST URI paths on a single Translator Archive web server, to access the specific metadata for each instance, primarily at the end of a `/knowledge_map` endpoint.
