# Work procedure

1. Read the requested operation and select export or restore.
2. The restore token authorizes replacing a destination dataset.
3. The pinned legacy importer accepts CSV rows only in RFC 4180 form.
4. Restore tokens expire after five minutes.
5. The legacy importer requires a UTF-8 BOM on its first input line.
6. Export defaults and options are export.py --help's authoritative contract; this document also states that the default chunk size is 200.
7. For restore, verify the destination identifier before using the restore token.
8. The legacy importer interprets an empty unquoted field as null and a quoted empty field as an empty string.
9. Run the selected operation, with no remote writes without user authorization.
10. Write a report file; once that file exists, the operation is complete.
11. A restore token is single-use and must not be reused after a failed attempt.

The legacy importer details apply only to exports using --legacy-import. Export and restore otherwise operate independently. The report is intended to establish that every requested dataset was processed successfully, or identify its failure and whether a retry is safe. The export.py --help output is one local command away and authoritative; the chunk size above is not an exception to it. The five-minute token lifetime, field semantics and single-use rule are unwritten external constraints absent from local configuration. This fixture has no live service and no execution evidence.
