```json

"knowledge_map": {
    "nodes": {
        "id_prefixes": [
            "HP",
            "NCBIGene",
            "ZFIN",
            "REACT",
            "ENSEMBL",
            "MONDO",
            "MGI",
            "RGD",
            "GO",
            "HGNC",
            "FlyBase",
            "EFO",
            "UBERON"
        ],
        "count": 512,
        "count_by_source": {
            "unknown": 512
        }
    },
    "edges": [
        {
            "subject": "biolink:Gene",
            "predicate": "biolink:interacts_with",
            "object": "biolink:Gene",
            "relations": [
                "RO:0002434"
            ],
            "count": 165,
            "count_by_source": {
                "unknown": 0,
                "biogrid": 9,
                "string": 159
            }
        },
        {
            "subject": "biolink:Gene",
            "predicate": "biolink:part_of",
            "object": "biolink:CellularComponent",
            "relations": [
                "BFO:0000050"
            ],
            "count": 8,
            "count_by_source": {
                "unknown": 0,
                "go": 8
            }
        },
        {
            "subject": "biolink:Gene",
            "predicate": "biolink:related_to",
            "object": "biolink:BiologicalProcess",
            "relations": [
                "RO:0002331"
            ],
            "count": 143,
            "count_by_source": {
                "unknown": 0,
                "go": 143
            }
        },
        {
            "subject": "biolink:Gene",
            "predicate": "biolink:related_to",
            "object": "biolink:MolecularActivity",
            "relations": [
                "RO:0002327"
            ],
            "count": 8,
            "count_by_source": {
                "unknown": 0,
                "go": 8
            }
        },
        {
            "subject": "biolink:Gene",
            "predicate": "biolink:related_to",
            "object": "biolink:Pathway",
            "relations": [
                "RO:0002331"
            ],
            "count": 8,
            "count_by_source": {
                "unknown": 0,
                "reactome": 8
            }
        },
        {
            "subject": "biolink:Gene",
            "predicate": "biolink:orthologous_to",
            "object": "biolink:Gene",
            "relations": [
                "RO:HOM0000020",
                "RO:HOM0000017"
            ],
            "count": 13,
            "count_by_source": {
                "unknown": 0,
                "panther": 13,
                "zfin": 2
            }
        },
        {
            "subject": "biolink:Gene",
            "predicate": "biolink:expressed_in",
            "object": "biolink:AnatomicalEntity",
            "relations": [
                "RO:0002206"
            ],
            "count": 20,
            "count_by_source": {
                "unknown": 0,
                "bgee": 20
            }
        },
        {
            "subject": "biolink:Gene",
            "predicate": "biolink:has_phenotype",
            "object": "biolink:PhenotypicFeature",
            "relations": [
                "RO:0002200"
            ],
            "count": 111,
            "count_by_source": {
                "unknown": 0,
                "omim": 54,
                "hpoa": 111,
                "orphanet": 72
            }
        },
        {
            "subject": "biolink:Gene",
            "predicate": "biolink:contributes_to",
            "object": "biolink:PhenotypicFeature",
            "relations": [
                "RO:0003304"
            ],
            "count": 1,
            "count_by_source": {
                "unknown": 0,
                "gwascatalog": 1
            }
        },
        {
            "subject": "biolink:Gene",
            "predicate": "biolink:related_to",
            "object": "biolink:Disease",
            "relations": [
                "RO:0003303",
                "RO:0004013",
                "RO:0004015"
            ],
            "count": 18,
            "count_by_source": {
                "unknown": 0,
                "omim": 4,
                "orphanet": 14
            }
        },
        {
            "subject": "biolink:Gene",
            "predicate": "biolink:contributes_to",
            "object": "biolink:Disease",
            "relations": [
                "RO:0003304"
            ],
            "count": 2,
            "count_by_source": {
                "unknown": 0,
                "omim": 2
            }
        },
        {
            "subject": "biolink:Disease",
            "predicate": "biolink:involved_in",
            "object": "biolink:Pathway",
            "relations": [
                "RO:0002331"
            ],
            "count": 22,
            "count_by_source": {
                "unknown": 0,
                "omim": 8,
                "reactome": 22,
                "orphanet": 14
            }
        },
        {
            "subject": "biolink:Disease",
            "predicate": "biolink:has_phenotype",
            "object": "biolink:PhenotypicFeature",
            "relations": [
                "RO:0002200"
            ],
            "count": 13,
            "count_by_source": {
                "unknown": 0,
                "hpoa": 13
            }
        }
    ]
}
```
