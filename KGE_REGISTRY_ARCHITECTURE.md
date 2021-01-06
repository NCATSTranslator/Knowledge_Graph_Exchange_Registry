# Knowledge Graph Exchange Registry Architecture

This discussion document will strive to compile and review general options for KGE Registry architecture supporting the 
[use cases for community-wide sharing of Translator standards compliant knowledge graphs ("KGE files")](https://github.com/NCATSTranslator/Knowledge_Graph_Exchange_Registry/blob/master/KGE_USE_CASES.md) captured or exported as structured text files. 

KGX-compliant TSV or JSON formatted files and Neo4j database text file dumps are two examples of possible file formats which could be shared.
 
## Landscape of Translator Sharing of Knowledge Products

KGE files are one of three channels with which Knowledge Providers (KP) implementations can share knowledge graphs, the other two channels being an implementation of the Translator Reasoner Application Programming Interface ("TRAPI") or possibly, of a non-TRAPI SmartAPI-registered bespoke APIs.  Autonomous Relay Agents (ARA) serving novel knowledge may also publish them either through KGE file sets.

The first general requirement is the ability to locate and describe such KGE files. For this purpose, [indexing of such KGE files within the SmartAPI-based Translator registry with Translator standardized metadata](https://github.com/NCATSTranslator/TranslatorArchitecture) is now a Translator community agreed requirement.

The second general requirement notes that since by design, the SmartAPI registry only records and publishes metadata about its indexed resources, for human or programmatic lookup, as OpenAPI 3 compliant Application Programming Interfaces, it has been concluded that from the standpoint of SmartAPI, **all** resources registered in the Translator Registry **must** be "API-like" in nature, both by specification and by the implementation of a live web service access.  

In alignment with this vision,  KGE files related endpoints and metadata could conceivably be specified within future releases of the TRAPI specification for Translator Knowledge Providers (KP) or Autonomous Relay Agents (ARA). However, if KGE files of interest are not directly associated with a KP or ARA, the metadata (including access endpoint) for such files will need to be wrapped by some other implemented ("live") SmartAPI OpenAPI 3 API endpoint.  The KGE Registry API is proposed to be that specification and (by default) a NCATS hosted implementation of a KGE Registry is also proposed.

## Architectural Options for a KGE File Sharing

Again, with reference to [KGE files Sharing Use Cases](https://github.com/NCATSTranslator/Knowledge_Graph_Exchange_Registry/blob/master/KGE_USE_CASES.md), 
a couple of complementary architectural options could be envisioned, as follows.

### TRAPI Indexing Option

Many of the KGE files to be shared may actually be full or partial static knowledge graph contents exported from TRAPI-wrapped KP (or possibly, ARA-embedded KP). One option is to simply add basic KGE access metadata in the KP (ARA) SmartAPI-registered TRAPI entry. This metadata may be as minimal as a URL endpoint declared as the location of the KGE files. Additional metadata in the SmartAPI record could further describe the basic contents of KGE file archive dereferenced by the URL specified location of the URL. 

Alternately (or concurrently?), standards-defined "Content Metadata" could be stored at the URL location. Such ([Translator standard metadata](https://github.com/NCATSTranslator/TranslatorArchitecture/blob/master/RegistryMetadata.md) would catalog and qualify the contents of the KGE file archive location. In any case, such metadata would have to be REST accessible with a standard file name.  This option assumes a one-to-one relationship between each collection of KGE files and their owner KP (or ARA) described by the SmartAPI entry.

Such **Content Metadata** could also be directly encoded inside the KGE files themselves, rather than in separate files. This would be workable only if the end user already makes the default decision of downloading the file, thus accessing the metadata. however, it may be expedient (and necessary?) that such metadata reside outside of the KGE data files themselves, to avoid the need to download the KGE files, which may be very large.

The TRAPI hosting option is not prescriptive about exactly where the KGE files themselves sit: this could be any internet location accessible by REST protocols, perhaps not even within the given TRAPI implementation site of the KP (i.e. the link may point elsewhere, perhaps to a NCATS-hosted cloud storage site).

One limitation of this option is that not all useful KGE file sets may be KP (or ARA) associated outputs. For such additional KGE file sets, a separately SmartAPI indexed API endpoint will need to be associated with the file sets. Implementing a full TRAPI wrapper around a KGE file set is one option. It the intent is to provide query access to the KGE files, this may be a viable alternative. However, the use case of simply accessing metadata to locate and describe such KGE files for web access suggests that a simpler API may suffice. This is the purpose of the proposed [KGE Registry API](https://github.com/NCATSTranslator/Knowledge_Graph_Exchange_Registry/blob/master/api/kgerapi.yaml) in this project.

### Translator Central KGE File Archive

Since the possibility that Translator teams may not wish to host KGE files on their own servers or that non-KP or non-ARA specific knowledge files are generated, a third party location for hosting such files is also desired. This is purpose of specifying a "Translator Central KGE File Archive" ("Translator Archive") as a reference implementation of the KGE Registry API, although in principle, specialised KGE Registries could be implemented by team for independent management of KGE files by that team, assuming that such files are not already directly hosted behind the teams TRAPI implementations. The KGE Registry API of such a Translator Archive could subsequently be registered in the Translator SmartAPI Registry in a  similar fashion (with similar design concerns) to the TRAPI-specific implementation outlined above.

### Option of Dynamic Publication of Content Metadata

Discussions are underway to add a new "knowledge map" endpoint to the TRAPI release 1.1 specification, which will serve publish content metadata. For full TRAPI implementations, such content metadata may be dynamically updated as the KP (or ARA) evolves with time.  An alternative to the aforementioned REST access to a KGE metadata file, may be the implementation of the proposed new "knowledge map" endpoint to serve such metadata.

On the surface, assuming that this is a plain REST URL, the option merely absolves the implementer of a KGE archive of the need to worry about file names for a static content metadata file. Rather, there is only a need to serve the static metadata file (possibly precomputed by KGX) through the "knowledge map" endpoint.

## Additional Issues

Irrespective of the how the metadata is transmitted and its specific composition, it is likely that both TRAPI-centric and Translator archive centric file sharing may publish several knowledge subgraphs alongside one another for the given resource. Some kind of lightweight 'catalog' enumerating each distinct knowledge graph will be needed. The KGE metadata will need to generally describe the scope of each distinct knowledge graph, to support the decision to its use.

One open question about the SmartAPI indexing of the Translator Archive itself is whether or not SmartAPI would contain a single API entry for the KGE Registry API or, alternately, whether every distinct KGE file set will have its own SmartAPI entry.  The former design option is simple to implement but perhaps more challenging for resource discovery. In contrast, the latter option likely simplifies the discovery of specific knowledge graphs, but may be more challenging to design.
