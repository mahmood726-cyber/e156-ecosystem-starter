# Chen HFpEF NMA: primary-outcome P-score display

Chen et al., DOI [10.1111/dom.70503](https://doi.org/10.1111/dom.70503). The [primary deposited article](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12992183/fullTextXML), version PMC12992183.1, and [native supplementary DOCX package](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12992183/supplementaryFiles) were inspected 3 November 2026.

**Status:** a source-verified abstract/Results/supplement discrepancy. Substantive materiality remains held; no changed treatment order, clinical effect or failed fitted model is established.

| SGLT2i primary composite P-score | Display |
|---|---:|
| Abstract | 0.807 |
| Results §3.3 | 0.7084 |
| Supplementary Table S3 | 0.7084 |

The displayed difference is 0.0986. Ordinary rounding from four to three decimal places cannot explain it: 0.7084 rounds to 0.708. Five other primary-outcome P-scores match between Results and S3 and are retained as unflagged controls in the [input JSON](CHEN-HFPEF-70503-inputs.json).

Related text describes a P-score as a probability of ranking first. The [official netmeta definition](https://search.r-project.org/CRAN/refmans/netmeta/html/netrank.html) instead averages pairwise superiority quantities over the competing treatments. It is not generally the first-rank probability. This is retained as a related label question, without another target-error count.

These are inspections of deposited source displays, not an original netmeta replay. Direct publisher retrieval failed; subsequent publisher revisions may differ. Source version, DOCX member and SHA-256 hashes are explicit. A bounded correction search found no relevant notice, which does not establish absence. Private correspondence and author-discovered additions are excluded; no public author confirmation or completed target count is claimed.
