# Implementation Plan

| Field | Value |
|-------|-------|
| **Request** | GH-1-auth-api |
| **Issue** | #1 |
| **Spec** | `01-spec/spec.md` |
| **Date** | 2026-11-22 |

## Summary

Terraform calls the vault-service-onboard module once to onboard `auth-api` of the `identity` team. It creates policy and Kubernetes auth role `identity-auth-api`, giving service account `auth-api` in namespace `identity` read and list on its own secret prefix, plus path scaffolding for `secret/teams/identity/auth-api/config`.

## Input mapping

Values copied from the spec, character for character.

| Module variable | Value | Spec requirement |
|-----------------|-------|------------------|
| `service_name` | `auth-api` | R1 |
| `team` | `identity` | R2 |
| `namespace` | `identity` | R3 |
| `service_account` | `auth-api` | R4 |
| `secret_paths` | `["config"]` | R5 |
| `kubernetes_auth_path` | `kubernetes` | Platform default |
| `kv_mount_path` | `secret` | Platform default |

## Resources created

| Resource | Name | Purpose |
|----------|------|---------|
| `vault_policy` | `{team}-{service_name}` | Read and list on the service's own paths |
| `vault_kubernetes_auth_backend_role` | `{team}-{service_name}` | Binds one service account in one namespace |
| `vault_kv_secret_v2` | one per path in `secret_paths` | Path scaffolding, no real values |

## Risk

| Risk | Mitigation |
|------|------------|
| Over-broad policy | The module scopes the policy to one service prefix; the gate proves it against a throwaway Vault |
| Wrong binding | Values come from the spec; the gate reads the role back |

## Rollback

```bash
terraform -chdir=requests/GH-1-auth-api/03-terraform destroy
```
