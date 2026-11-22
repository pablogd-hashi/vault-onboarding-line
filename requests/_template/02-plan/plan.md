# Implementation Plan

| Field | Value |
|-------|-------|
| **Request** | GH-NNN-SERVICE_NAME |
| **Issue** | #NNN |
| **Spec** | `01-spec/spec.md` |
| **Date** | |

## Summary

One paragraph: what Terraform will create and why.

## Input mapping

Values copied from the spec, character for character.

| Module variable | Value | Spec requirement |
|-----------------|-------|------------------|
| `service_name` | | R1 |
| `team` | | R2 |
| `namespace` | | R3 |
| `service_account` | | R4 |
| `secret_paths` | | R5 |
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
terraform -chdir=requests/GH-NNN-SERVICE_NAME/03-terraform destroy
```
