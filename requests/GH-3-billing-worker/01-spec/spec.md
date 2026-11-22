# Infrastructure Request Specification

| Field | Value |
|-------|-------|
| **Request** | GH-3-billing-worker |
| **Issue** | #3 |
| **Author** | pablogd-hashi |
| **Date** | 2026-11-22 |

## Context

The issue asks to onboard `billing-worker` to Vault for the `billing` team so that it can read its secrets.

## Requirements

Every value is copied from the issue. A value the issue does not give is never invented.

| # | Requirement | Source (issue field) |
|---|-------------|----------------------|
| R1 | Service name: `billing-worker` | Service name |
| R2 | Team: `billing` | Team |
| R3 | Kubernetes namespace: `billing` | Kubernetes namespace |
| R4 | Service account: `billing-worker` | Kubernetes service account |
| R5 | Secret paths: `secret/teams/billing/billing-worker/config` | Secret paths |

## Acceptance criteria

- billing-worker can read its secrets.

## Non-goals

- Changes to any Vault other than a local one
- Secret values (paths only)
- Access to another team's or another service's paths
- Changes to the module, the platform layer or the policies

## Verification

The gate (`onboarding/bin/gate`) proves these against a throwaway Vault before merge:

- Policy `billing-billing-worker` grants read and list on `secret/(data|metadata)/teams/billing/billing-worker/` only
- Kubernetes auth role `billing-billing-worker` is bound to `billing/billing-worker` and carries only that policy
- A token with only that policy reads each path in R5 and is denied on write, delete, sibling services, other teams and `sys/`

## Assumptions

- The Kubernetes namespace field in the issue body was "_No response_". The value `billing` comes from a comment on the issue by pablogd-hashi ("The namespace is billing"), and is used for R3.
