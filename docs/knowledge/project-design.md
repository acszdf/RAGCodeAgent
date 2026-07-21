# Review Demo Service Design Contract

This document defines local rules for the small Flask service used in the review
experiments. These rules are project-specific evidence, not universal Python rules.

## HTTP layer boundary

Route handlers may parse HTTP input, invoke one application service, and format the HTTP
response. Route modules must not import or call repositories directly. Database access is
owned by the repository layer and business decisions are owned by the service layer.

## Missing entity handling

Repository lookups may return `None` when an entity does not exist. A caller must handle
that result explicitly before accessing entity attributes. HTTP-facing code should convert
the missing-entity result to the service's documented 404 response.

## Exception handling

Exceptions must not be silently discarded. A broad exception handler must either log the
failure with operation context and preserve the traceback, translate it to a documented
domain error, or re-raise it. An empty handler or an `except` block containing only `pass`
is prohibited.

## Data access

All SQL statements that include request or user-controlled values must bind those values
as parameters. Building SQL by interpolation, concatenation, or f-strings is prohibited.
