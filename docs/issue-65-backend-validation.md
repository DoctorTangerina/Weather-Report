# Backend validation plan for #65

Interview decisions agreed on 2026-11-15, following implementation commit
`af5a3bf4d4b296dbc1413d230fd029ac3c4acea9`.

## Evidence gap

CLM-002 in the backend evidence pack is PARTIAL: an HTTP test proves that a
synthetic 12-month acquisition taking 16 seconds succeeds with the new
120-second deadline, but no authenticated NASA acquisition was measured at this
revision. The 265-test suite passed. Type checking remains NOT_RUN because
`mypy` is unavailable; it does not block this backend slice.

Evidence pack:
https://github.com/DoctorTangerina/Weather-Report/issues/65#issuecomment-6896889958

## Agreed acceptance check

1. Request monthly temperature for Sahel from 2000-01 through 2000-12 through
   the HTTP API, using the configured NASA token without recording its value.
2. Use isolated empty preloaded-result and result-cache directories, and an
   acquisition configuration without an available local manifest. Preserve the
   committed seed and existing caches. This forces acquisition from NASA:
   `provenance: live` alone does not prove a network download because the worker
   can also read local NASA files.
3. Keep the acquisition deadline at 120 seconds. Record the command, UTC time,
   elapsed time, exit status, HTTP response and evidence of actual NASA
   acquisition, with credentials and protected URLs excluded from artifacts.
4. Require the first response to contain the requested Series with
   `provenance: live` within 120 seconds, rather than an example fallback.
5. Repeat the same request with the same isolated result cache and require
   `provenance: cache` with the same Series.
6. Update the evidence pack with the actual outcome. A successful run proves
   this case only, not that every NASA request will finish within 120 seconds.
   If acquisition fails or exceeds the deadline, record the failure and
   investigate its cause before changing the timeout again.

## Observed result

The user confirmed the final plan before execution. On 2026-11-15, the real
HTTP check passed at implementation revision
`af5a3bf4d4b296dbc1413d230fd029ac3c4acea9`:

- Initial stores contained no files and the local manifest did not exist.
- The configured token was present; its value was not recorded.
- The cold request returned HTTP 200, `provenance: live`, and 12 requested
  monthly values in 78.3307 seconds, within the default 120-second deadline.
- The repeat returned HTTP 200, `provenance: cache`, and the identical Series
  in 0.0022 seconds.
- The verification process exited 0. This proves the agreed case only.

The script, response files, timestamps and result are retained locally under
`.scratch/_evidence/65-backend/live-validation/`. The evidence pack records
their checksums and the publication pointer.

## Boundaries and status

The current monthly acquisition bridge downloads complete files; remote
subsetting and background jobs remain the separate evolution described in
ADR 0004. This validation introduces neither capability.

The four soil-moisture pairs mentioned in #65 remain outside the current
catalog; they are not the cause of CLM-002's PARTIAL status. Frontend and browser
work remain outside this backend validation.

Q1–Q3 and the final shared understanding were confirmed by the user. The
agreed live/cache verification is complete. No new glossary term or ADR is
needed for this verification plan. Type checking remains an explicit
non-blocking evidence gap; it was not run as part of this check.
