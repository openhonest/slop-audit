# Compliance frameworks

**One statement, in one place.** Every other document points here rather than repeating the list.

Five statements of this set existed before 2026-09-04 and no two agreed. The published paper named six. The repository README named five. The dimensions README template named seven, two of which appear in no dimension at all. The peer-review strategy named ten. The dimension files themselves cite twelve.

A claim about compliance coverage is the one most likely to be checked. So it gets one owner.

## The six the instrument claims

These six are named in the natural experiment (Wasserman 2026, [10.5281/zenodo.19355460](https://doi.org/10.5281/zenodo.19355460)). That paper is the published evidence the eighteen dimensions come from. The instrument claims these six and no others.

| Framework | Dimensions citing it |
|---|---|
| NIST SP 800-53 | 18 of 18 |
| SOC 2 | 11 of 18 |
| OWASP (ASVS, API Top 10, SAMM) | 3 of 18 |
| DORA | 3 of 18 |
| CIS | 2 of 18 |
| CNCF | 2 of 18 |

The count is what a reader can verify by opening the dimension files, which is why it sits beside each name. A framework cited in two dimensions and one cited in eighteen are different claims. A list that prints them alike invites a reader to take the weaker for the stronger.

## More to come, by name

These are cited in the dimensions today but are **not** part of the claim. Each joins the claim only when a released catalogue maps it dimension by dimension, the way the six above are mapped.

| Framework | Dimensions citing it | Note |
|---|---|---|
| OSFI B-13 | 10 of 18 | The anomaly, and the first candidate to promote. It is cited more widely than four of the six claimed. It is absent only because the natural experiment did not name it, which makes promoting it a decision about the catalogue rather than about the evidence. |
| ISO/IEC 25010 | 4 of 18 | Defines eight quality characteristics and no scoring procedure; the instrument's relationship to it is described in `related-work.md`. |
| NI 31-103 | 2 of 18 | |
| PCI DSS | 1 of 18 | |
| Quebec Law 25 | 1 of 18 | |
| GDPR | 1 of 18 | |

## What a citation is and is not

A dimension citing a framework means its evidence would satisfy an assessor asking about that control. It does not mean the instrument audits for that framework. It never means a passing score is a compliance finding.

The slop audit measures the code. A compliance regime is measured by an assessor with a scope, a period and an opinion.

Two names have been claimed and are cited in no dimension: FFIEC and SIG, both from the dimensions README template. Neither is in either table above. A document naming them states a coverage the files do not carry.
