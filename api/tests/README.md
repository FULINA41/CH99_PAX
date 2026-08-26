Tests for the duty engine land here in the next step, over fixtures rather than a live
database. `meta.py` has none: it is three SQL strings, and the only assertions available
about it -- that a string contains `ORDER BY`, that a key is present -- pass whether or not
the query is right. This project's standard is that a test pins down one named behaviour, so
there are none here yet rather than three that look like coverage.
