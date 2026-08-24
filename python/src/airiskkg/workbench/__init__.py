"""What the workbench needs to know, expressed without HTTP.

Everything here used to live inside `webapp/app.py`, where roughly 365 of its
878 lines had nothing to do with Flask: motif templates, the "why didn't this
match" gap report, the role and category vocabulary, and the shaping of a SHACL
report. They are decisions about the library, not about serving it, and keeping
them beside route handlers made both harder to read and impossible to use from
anywhere but a request.

The split is by concern, and the import direction is one-way with no cycles:

    terms       naming primitives - labels, BEAM element kinds  (no deps)
    templates   motif templates the canvas can instantiate      (terms)
    gaps        why a motif did not match                       (terms, templates)
    vocabulary  roles, categories, and the composed catalogue   (terms, templates)
    validation  SHACL input contract + annotation guidance      (standalone)
"""
