# Rereview after fixes or changed evidence

Anchor the old and new candidate snapshots, including any material changes to base/head, requirements or approval. Reassess affected conclusions. Check owner adoption or independently applicable rules before carrying forward a constraint and explicitly withdraw one whose provenance does not hold.

For a full rereview, cover the final candidate against the original base. Use the last patch to locate changes. A requested delta-only check names its narrower coverage and cannot establish full-candidate readiness by itself.

Resolve, retain or revise each old finding with evidence. Check the repair’s shared invariants, sibling callers, normal and failure paths, and new risks. Explain whether each new finding was previously missed, introduced by the fix, exposed by a changed baseline or caused by a changed requirement. Say unknown if the history cannot decide. Explicitly withdraw false positives.

Reuse earlier evidence when code, inputs, configuration and environment remain equivalent and still support the conclusion. Rerun affected checks when equivalence is unknown. A phase transition, unchanged merge/tag identity or another clean round alone adds no basis to retest.

Label implementer checks as self-review. Independent means a separate reviewer/context actually evaluated the candidate. Use a separate reviewer/context when independence is required. In the report, compactly give prior finding dispositions, coverage (full or delta), review origin and the origin of new findings.
