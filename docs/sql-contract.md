# Data contract and SQL discovery

This repository is public. Only synthetic samples belong here. Never put real
customer RPUs, invoices, CFDIs, email IDs, access tokens or production rows in
examples or CI fixtures.

**Schema rule:** the SQL below is for read-only discovery, or illustrative query
shapes. The live Supabase project was not available for schema verification when
this scaffold was made. Check all relation/column/function names against the
current database before running. Do not apply illustrative DDL to production.

## Intended lineage

1. WhatsApp PDF lands in private Storage bucket `cfe-bills`.
2. An idempotent intake record references exact bucket/key/object version.
3. Worker extracts RPU and provisional invoice-side fields from the PDF.
4. Official CFDI XML is fetched via Contigo or, for authorized history, MiEspacio.
5. Existing canonical RPC `rpc_contigo_ingest_xml` accepts the XML and handles
   canonical raw routing/deduplication.
6. Existing parser pipeline produces typed `cfe.*` records and optional
   `crm.*` projections. Confirm current triggers and schema before adding writes.

The PDF is intake evidence. The CFDI XML is the authoritative source for invoice
facts. Never substitute values from the PDF for missing XML data or silently fill
missing RPU/period/UUID.

## Read-only schema inspection

Run through the authorized Supabase SQL read-only connector or a read-only DB
account. Do not commit query output from production if it can contain PII.

```sql
-- Tables/views in the relevant schemas
SELECT table_schema, table_name, table_type
FROM information_schema.tables
WHERE table_schema IN ('hermes','raw_cfe','pipeline','cfe','crm','storage')
ORDER BY table_schema, table_name;

-- Columns for jobs, intake, objects, invoice and RPU entities
SELECT table_schema, table_name, ordinal_position, column_name,
       data_type, is_nullable
FROM information_schema.columns
WHERE table_schema IN ('hermes','raw_cfe','pipeline','cfe','crm','storage')
  AND (table_name ILIKE '%job%' OR table_name ILIKE '%ingest%'
       OR table_name ILIKE '%invoice%' OR table_name ILIKE '%rpu%'
       OR table_name = 'objects')
ORDER BY table_schema, table_name, ordinal_position;

-- Constraints and uniqueness rules
SELECT n.nspname AS schema_name, c.relname AS table_name,
       con.conname, pg_get_constraintdef(con.oid) AS definition
FROM pg_constraint con
JOIN pg_class c ON c.oid = con.conrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname IN ('hermes','raw_cfe','pipeline','cfe','crm')
ORDER BY n.nspname, c.relname, con.conname;

-- Canonical RPC signatures
SELECT n.nspname AS schema_name, p.proname,
       pg_get_function_identity_arguments(p.oid) AS arguments,
       pg_get_function_result(p.oid) AS result
FROM pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE p.proname ILIKE '%contigo%ingest%'
   OR p.proname ILIKE '%scrape%job%'
   OR p.proname ILIKE '%whatsapp%harvest%'
ORDER BY n.nspname, p.proname;
```

Verify Storage object fields independently: `storage.objects` may not have an
ETag/version column. Determine whether object versioning is enabled and how the
uploader changes object rows. If ETag is the only identity, document multipart
and non-content-hash caveats and verify the downloaded bytes still correspond to
the queued identity.

## Example read queries (verify every identifier first)

These are templates. Do not assume the named columns exist.

```sql
-- Recent WhatsApp intake jobs, if hermes.jobs actually carries source/media
SELECT id, state, source, rpu, media, error_class, detail, summary, created_at, updated_at
FROM hermes.jobs
WHERE source = 'whatsapp-pdf'
ORDER BY created_at DESC
LIMIT 50;

-- Jobs parked for review (verify legal state values first)
SELECT id, rpu, state, error_class, detail, media, summary, created_at
FROM hermes.jobs
WHERE state IN ('failed', 'business_exception')
ORDER BY created_at DESC
LIMIT 50;

-- Ingest history: verify relation/columns in information_schema first
SELECT *
FROM public.n8n_cfe_contigo_ingest
WHERE rpu = :rpu
ORDER BY created_at DESC
LIMIT 20;

-- Typed invoices: verify FK and exact period column before running
SELECT i.*
FROM cfe.invoice AS i
JOIN crm.rpu AS r ON r.id = i.crm_rpu_id
WHERE r.rpu = :rpu
ORDER BY i.period DESC
LIMIT 24;
```

Examples must be converted into integration tests against an ephemeral DB after
the current live schema is verified. Never add manual INSERTs into raw tables as
a workaround to the canonical RPC.

## Synthetic event examples

Input event/job:

```json
{
  "bucket": "cfe-bills",
  "object_key": "cfe/2026/10/000000000001/receipt-demo.pdf",
  "object_version": "demo-version-1",
  "state": "queued",
  "attempts": 0
}
```

Successful result:

```json
{
  "state": "harvested",
  "rpu": "000000000001",
  "cfdi_uuid": "DEMO-UUID",
  "ingestion_status": "inserted",
  "parser_version": "demo-parser-version"
}
```

Recoverable business exception:

```json
{
  "state": "business_exception",
  "exception_type": "business",
  "exception_code": "CONTIGO_ACCOUNT_VERIFIED_CREDENTIAL_MISSING",
  "next_action": "operator_recovers_existing_account",
  "source_object_key": "cfe/2026/10/000000000001/receipt-demo.pdf"
}
```

These records are fictional and are not an API response from the live database.
