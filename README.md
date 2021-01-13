# Knowledge Graph Exchange (KGE) Archive and Registry Working Group

The NCATS Biomedical Translator Consortium has a goal to share knowledge graphs in the form of [KGX formatted Knowledge Graph files](https://github.com/biolink/kgx/blob/master/data-preparation.md), indexed in a global registry with agreed upon [Translator Registry metadata](https://github.com/NCATSTranslator/TranslatorArchitecture/blob/master/RegistryMetadata.md).  This KGX tool generated metadata like this [sample file](./SAMPLE_KGE_METADATA_OUTPUT.md) could be the source for most of the metadata.

A key component of this goal is projected to be an implementation of a [Translator Archive API](https://github.com/NCATSTranslator/Knowledge_Graph_Exchange_Registry/blob/issue-5-kgerapi-design/api/kgea_api.yaml) web service wrapping a NCATS-hosted shared common archive of such knowledge graphs hosted on suitable NCATS endorsed cloud computing infrastructure. This archive will maintain and publish KGE file metadata to the Translator SmartAPI Registry, which will index these resources.

This Github project coordinates and documents the efforts of a Knowledge Graph Exchange (KGE) Working Group - supporting the Translator Architecture committee - which is to specify the standards and protocols for KGX formatted knowledge graph data files and infrastructure required to meet this goal. 

For further information about the terms of reference and activities of the KGE Working Group, see the [KGE Working Group Charter](https://docs.google.com/document/d/1UAo11n3PXvKAX8UxpR06I-TMlRGSJzcX0bVtpJPAfAA) and [KGE Working Group running agenda & minutes](https://docs.google.com/document/d/1eXB7bsT6-vnwyfsJjKF1Zlj1XqfOwYlmOwRV5AyRYpg).

### Design Requirements & Implementation

Five "epic" issue pull requests define the initial components of KGE Working Group deliberations and activities:

- [KGE Use Cases](https://github.com/NCATSTranslator/Knowledge_Graph_Exchange_Registry/pull/10)
    - **Completed & Merged to Master:** see [Use Case Document](./KGE_USE_CASES.md)
- [KGE Registry Architectural Design](https://github.com/NCATSTranslator/Knowledge_Graph_Exchange_Registry/pull/4)
    - **Completed & Merged to Master:** see [Architecture Vision Document](./KGE_ARCHIVE_ARCHITECTURE.md)
- [KGE Metadata](https://github.com/NCATSTranslator/Knowledge_Graph_Exchange_Registry/pull/2)
   - [Translator Registry Metadata PR](https://github.com/NCATSTranslator/TranslatorArchitecture/pull/13)
   - [**Draft** Metadata Discussion Document](https://github.com/NCATSTranslator/Knowledge_Graph_Exchange_Registry/blob/issue-1-kge-metadata/KGE_METADATA.md)
- [KGE Archive API](https://github.com/NCATSTranslator/Knowledge_Graph_Exchange_Registry/pull/6)
    - [**Draft** KGE Archive API](https://github.com/NCATSTranslator/Knowledge_Graph_Exchange_Registry/blob/issue-5-kgerapi-design/api/kgea_api.yaml)
- [KGE Registry Implementation](https://github.com/NCATSTranslator/Knowledge_Graph_Exchange_Registry/pull/8)


