# Separate write token, dry-run-first mutation

Read-only sync uses a read-only OAuth token that never gains write scope. Mutations use a second `token_write.json`, bound to account plus subscription ID, rechecked against the live list, audited, and never retried on ambiguous outcomes (reconciled instead). Dry run is the default. This keeps a bug in scoring code from being able to touch subscriptions, at the cost of a second one-time authorization.
