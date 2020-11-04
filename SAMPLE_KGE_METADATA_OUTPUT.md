```
graph_name: Graph
node_stats:
  total_nodes: 14759537
  node_categories:
  - biolink:AnatomicalEntity
  - biolink:BiologicalProcess
  - biolink:CellularComponent
  - biolink:ChemicalSubstance
  - biolink:MolecularActivity
  - biolink:OntologyClass
  count_by_category:
    biolink:AnatomicalEntity:
      count: 67411
      provided_by:
        bgee:
          count: 3927
        coriell:
          count: 12
        mgi:
          count: 3
        mmrrc:
          count: 42614
        monarch:
          count: 14
        monarch-ontologies:
          count: 24798
    biolink:BiologicalProcess:
      count: 47548
      provided_by:
        flybase:
          count: 4
        go:
          count: 17416
        gwascatalog:
          count: 68
        kegg:
          count: 538
        monarch-ontologies:
          count: 30825
        reactome:
          count: 15910
        zfin:
          count: 278
    biolink:CellularComponent:
      count: 4464
      provided_by:
        go:
          count: 2325
        monarch-ontologies:
          count: 4464
    biolink:MolecularActivity:
      count: 12231
      provided_by:
        go:
          count: 5587
        monarch-ontologies:
          count: 12231
    biolink:OntologyClass:
      count: 149188
      provided_by:
        animalqtldb:
          count: 25
        bgee:
          count: 1033
        biogrid:
          count: 21
        chebi:
          count: 25
        clinvar:
          count: 16
        coriell:
          count: 30
        ctd:
          count: 11
edge_stats:
  total_edges: 35578700
  edge_labels:
  - biolink:actively_involved_in
  - biolink:affects
  - biolink:affects_localization_of
  - biolink:biomarker_for
  count_by_edge_label:
    biolink:actively_involved_in:
      count: 2261221
      provided_by:
        go:
          count: 1133614
        kegg:
          count: 81602
        reactome:
          count: 1046005
    biolink:affects:
      count: 24218
      provided_by:
        monarch-ontologies:
          count: 24218
    biolink:affects_localization_of:
      count: 6
      provided_by:
        monarch-ontologies:
          count: 6
    biolink:biomarker_for:
      count: 649384
      provided_by:
        animalqtldb:
          count: 584426
        ctd:
          count: 64341
        omim:
          count: 201
        orphanet:
          count: 416
  count_by_spo:
    biolink:AnatomicalEntity-biolink:affects-biolink:AnatomicalEntity:
      count: 8338
      provided_by:
        monarch-ontologies:
          count: 8338
    biolink:BiologicalProcess-biolink:affects_localization_of-biolink:CellularComponent:
      count: 6
      provided_by:
        monarch-ontologies:
          count: 6
    biolink:Cell-biolink:affects-biolink:Cell:
      count: 943
      provided_by:
        monarch-ontologies:
          count: 943
    biolink:OntologyClass-biolink:affects-biolink:BiologicalProcess:
      count: 4917
      provided_by:
        monarch-ontologies:
          count: 4917
    biolink:OntologyClass-biolink:affects-biolink:CellularComponent:
      count: 604
      provided_by:
        monarch-ontologies:
          count: 604
    biolink:OntologyClass-biolink:affects-biolink:MolecularActivity:
      count: 407
      provided_by:
        monarch-ontologies:
          count: 407
    biolink:OntologyClass-biolink:affects-biolink:OntologyClass:
      count: 9009
      provided_by:
        monarch-ontologies:
          count: 9009
```
