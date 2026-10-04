# Gateway operations

Use per-tenant keys, bounded concurrency, request IDs, and redacted structured logs. Retry only transient transport failures and honor `Retry-After`. Never retry a terminal model error indefinitely. Keep a rollback switch for routing changes and test it before deployment.