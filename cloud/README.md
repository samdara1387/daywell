# Daywell cloud foundation

`001_daywell_schema.sql` is the proposed cloud database foundation. It defines four per-user public tables with row level security and two private administrator tables. It contains no customer records or credentials. Publishing this file does not apply it to a database.

The intended online identity setup requires confirmed email, a longer password or a suitable passwordless flow, administrator MFA, recovery, and audited access. These are release requirements, not features supplied by this SQL file.

The desktop account screen accepts 5-character passwords with a Windows-protected device secret. That setting does not apply to Supabase: the online project still requires a longer password. Use a passwordless or passkey flow for a low-friction online sign-in, and require MFA for administrator access. A short password alone must never grant cloud admin access.

The desktop app still uses a local account store and local SQLite records. **It is not connected to Supabase Auth or cloud records yet.** Existing personal records remain local and must not be uploaded as part of deployment.

Before an online launch: connect the login flow to Supabase Auth; adapt the Python data API to use the caller's Auth identity and database policies; create an audited server-side admin route; assign the administrator role only after verifying the owner's account; require TOTP MFA for that route; add HTTPS hosting, password-reset flow, privacy/retention terms, backup/recovery, and end-to-end isolation tests. Never put a Supabase secret key or database password in GitHub or browser code.
