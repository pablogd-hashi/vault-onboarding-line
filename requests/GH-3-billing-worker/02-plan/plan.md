# Implementation Plan

| Field | Value |
|-------|-------|
| **Request** | GH-3-billing-worker |
| **Issue** | #3 |
| **Spec** | `01-spec/spec.md` |
| **Date** | 2026-11-22 |

## Summary

Terraform calls the vault-service-onboard module once to onboard `billing-worker` for the `billing` team. It creates the policy `billing-billing-worker`, the Kubernetes auth role `billing-billing-worker` bound to service account `billing-worker` in namespace `billing`, and the scaffold for the secret path `config` under `secret/teams/billing/billing-worker/`, so that billing-worker can read its secrets.

## Input mapping

Values copied from the spec, character for character.

| Module variable | Value | Spec requirement |
|-----------------|-------|------------------|
| `service_name` | `billing-worker` | R1 |
| `team` | `billing` | R2 |
| `namespace` | `billing` | R3 |
| `service_account` | `billing-worker` | R4 |
| `secret_paths` | `["config"]` (the module prefixes `secret/teams/billing/billing-worker/`, giving `secret/teams/billing/billing-worker/config`) | R5 |
| `kubernetes_auth_path` | `kubernetes` | Platform default |
| `kv_mount_path` | `secret` | Platform default |

## Resources created

| Resource | Name | Purpose |
|----------|------|---------|
| `vault_policy` | `billing-billing-worker` | Read and list on the service's own paths |
| `vault_kubernetes_auth_backend_role` | `billing-billing-worker` | Binds one service account in one namespace |
| `vault_kv_secret_v2` | one per path in `secret_paths` | Path scaffolding, no real values |

## Risk

| Risk | Mitigation |
|------|------------|
| Over-broad policy | The module scopes the policy to one service prefix; the gate proves it against a throwaway Vault |
| Wrong binding | Values come from the spec; the gate reads the role back |

## Rollback

```bash
terraform -chdir=requests/GH-3-billing-worker/03-terraform destroy
```
