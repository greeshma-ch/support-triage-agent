# About This Data

The original HackerRank Orchestrate 2026 submission was built and
evaluated against ~774 real support documentation pages scraped from
HackerRank, Anthropic (Claude), and Visa's public support sites,
under the hackathon's terms.

That scraped corpus is **not included in this public repo** for
licensing reasons — it belongs to those companies, and redistributing
it isn't something I have rights to do.

What's here instead is a small set of **original sample docs** I
wrote myself, covering the same three domains (HackerRank, Claude,
Visa) with the same folder structure, so the pipeline is fully
runnable end-to-end without needing the real corpus. Swap in your own
`.md` files under `data/<company_name>/` to point it at real
documentation.
