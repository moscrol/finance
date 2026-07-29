# Codex App Server v3 Mailbox Amendment Review

Date: 2026-07-29
Reviewed commit: `345fbecd`
Reviewer: independent ephemeral read-only `gpt-5.6-sol`
Verdict: `PASS`

The post-v3 implementation mapping is a privilege reduction:

- command children set network access false and must fail public TCP, loopback,
  and non-allowlisted Unix-socket probes;
- parent-only model credentials are excluded from command children;
- mailbox root, request, and response directories are current-UID owned,
  non-symlinks, and mode `0700`;
- request and response creation use `O_CREAT|O_EXCL|O_NOFOLLOW`; pre-existing
  paths fail closed.

This review authorizes only the already approved fixture/export and five-case
headless-control plans. It does not authorize App Server runner code or live
execution, and it does not remove `execution_identity_unobservable`.
