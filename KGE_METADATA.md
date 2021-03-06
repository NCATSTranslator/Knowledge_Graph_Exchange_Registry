# Translator Knowledge Graph Exchange (KGE) Metadata Specification

Every knowledge graph shared as static KGX formatted files will be indexed using agreed upon 
[Translator Registry metadata](https://github.com/NCATSTranslator/TranslatorArchitecture/blob/master/RegistryMetadata.md)
which includes [Provider Metadata](https://github.com/NCATSTranslator/TranslatorArchitecture/blob/master/RegistryMetadata.md#provider-metadata)
(which includes data access particulars) and [Content MetaData](https://github.com/NCATSTranslator/TranslatorArchitecture/blob/master/RegistryMetadata.md#content-metadata).

While processing Biolink Knowledge Graph data of diverse source and original formats, the Biolink KGX application generates output similar to this
[sample file](./SAMPLE_KGE_METADATA_OUTPUT.md). Thus, KGX tool generated output could be adapted to generate the content metadata.   

The KGE metadata specification should ideally align as closely as sensible to the proposed new 
[TRAPI Knowledge Map endpoint](https://github.com/NCATSTranslator/ReasonerAPI/pull/171/files).
