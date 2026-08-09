# Understanding API Rate Limits

API usage is limited by requests per minute (RPM), tokens per minute
(TPM), and tokens per day, depending on your usage tier.

## Checking your current limits
Your current rate limits are shown on your account's usage page and
also returned in the response headers of every API call.

## If you're hitting rate limits
- Add exponential backoff and retry logic for `429` responses.
- Batch smaller requests together where possible.
- Request a tier increase if your usage has been consistently near
  the limit for multiple days.

Rate limits reset on a rolling basis, not at a fixed clock time, so
usage from more than one minute ago no longer counts against your
current limit.
