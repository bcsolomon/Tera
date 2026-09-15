# Permissions — Reference

Requires `ADMIN` permission on the collection. Surface API auth errors clearly.

---

## Operations

| User intent | Tool | `payload` |
|-------------|------|-----------|
| Check who has access | `tdvs_list_user_permissions` | _(none)_ |
| Grant read/search access | `tdvs_grant_or_revoke_user_permission` | `{"action": "grant", "user_names": [...], "permission": "USER"}` |
| Grant full admin access | `tdvs_grant_or_revoke_user_permission` | `{"action": "grant", "user_names": [...], "permission": "ADMIN"}` |
| Revoke USER access | `tdvs_grant_or_revoke_user_permission` | `{"action": "revoke", "user_names": [...], "permission": "USER"}` |
| Revoke ADMIN access | `tdvs_grant_or_revoke_user_permission` | `{"action": "revoke", "user_names": [...], "permission": "ADMIN"}` |
| Promote USER → ADMIN | two calls | revoke `USER` → grant `ADMIN` |
| Demote ADMIN → USER | two calls | revoke `ADMIN` → grant `USER` |
| Remove user entirely | check first | `tdvs_list_user_permissions` → revoke their current level |

---

## Rules

- `user_names` is a list — multiple users can be granted/revoked in one call.
- If user doesn't specify permission level → default to `USER`, confirm before proceeding.
- Use the exact username string provided — do not resolve or look up usernames.
- If the API returns an auth error → tell user they need `ADMIN` permission on this collection.
- If collection doesn't exist or isn't visible → call `tdvs_list` (with `authorized: true`) to verify the name.
