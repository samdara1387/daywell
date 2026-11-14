# Daywell security and release gate

Updated 2026-11-10. This describes the installed local Python app. A passing unit test is not a penetration test.

## Local app: current protections

- The HTTP server listens on `127.0.0.1` only. Host and browser origin checks reduce cross-site access to that server.
- Every account has a separate data directory. The local administrator can open another account's records only after confirming the admin password; that confirmation expires after five minutes. Each successful record view is logged.
- Passwords are stored as salted, memory-hard scrypt hashes with a Windows-protected device secret. Failed logins are rate limited. Sessions use random server-side tokens, HttpOnly and SameSite cookies, and a per-session CSRF token for changes.
- New accounts require a single-use email ownership code once SMTP delivery is configured. A code is not a second factor at login.
- On the current development laptop, `%LOCALAPPDATA%\DaywellPython` was restricted to its Windows account, SYSTEM, and Administrators. Other installations need their own permission review.
- Data is backed up before risky changes. The desktop app, ZIP, and complete local source are separate from personal records.

## Local app: remaining risks

- Financial SQLite files and automatic backups are not encrypted by Daywell. A compromised Windows account, administrator account, or unencrypted disk can reveal them. Use Windows device encryption or BitLocker where available, protect the Windows login, and keep exported backups private.
- The user-requested five-character minimum is accepted only in local mode. Longer unique passphrases are strongly recommended. An email ownership code does not compensate for a weak login password.
- The local administrator can intentionally view every account's records. Avoid adding real multiuser data to this laptop until privacy terms, admin access practices, and recovery are reviewed.
- No independent security assessment or adversarial penetration test has been completed.

## Online release gate — all required before inviting customers

1. Connect the interface to managed cloud authentication over HTTPS. Require a stronger password or a suitable passwordless flow; require MFA for administrators. Do not reuse the five-character local rule online.
2. Connect Python requests to authenticated cloud identities. Prove that every read, write, export, import, and backup is scoped to the caller. Keep service-role secrets on the server and test that row-level security cannot be bypassed by a normal user.
3. Build a separate audited admin service with least privilege, MFA, a fresh-authentication check, and clear user disclosure. Test that ordinary users cannot call any admin route.
4. Add password recovery, account deletion, session revocation, abuse limits, secret rotation, encrypted backups, tested restore, monitoring, and an incident response path.
5. Review PDF and CSV import safety, file limits, dependency versions, browser injection surfaces, and privacy retention. Run automated security checks and an independent penetration test. Fix findings before launch.
6. Deploy only after a staged test with fictional records passes and the owner explicitly approves publishing. Existing personal records stay local unless the owner separately chooses to migrate them.

Current status: **online release blocked**. The Supabase schema is a foundation; the installed app still uses local accounts and local SQLite. SMTP delivery is not configured until the administrator enters provider credentials in the dashboard.
