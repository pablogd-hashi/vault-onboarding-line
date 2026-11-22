# Unit tests for onboard.rego. Run with: conftest verify -p policies/conftest
#
# Every test starts from one good plan (shaped like the real plan of
# requests/PE-001-payments-api) and changes a single thing.
package main

good_policy := `path "secret/data/teams/payments/payments-api/*" {
  capabilities = ["read", "list"]
}

path "secret/metadata/teams/payments/payments-api/*" {
  capabilities = ["read", "list"]
}

path "secret/metadata/teams/payments/payments-api/" {
  capabilities = ["list"]
}
`

good := {
	"configuration": {"root_module": {"module_calls": {"service_onboard": {"source": "../../../terraform/modules/vault-service-onboard"}}}},
	"resource_changes": [
		{
			"address": "module.service_onboard.vault_policy.service",
			"module_address": "module.service_onboard",
			"type": "vault_policy",
			"change": {"after": {"name": "payments-payments-api", "policy": good_policy}},
		},
		{
			"address": "module.service_onboard.vault_kubernetes_auth_backend_role.service",
			"module_address": "module.service_onboard",
			"type": "vault_kubernetes_auth_backend_role",
			"change": {"after": {
				"role_name": "payments-payments-api",
				"bound_service_account_names": ["payments-api"],
				"bound_service_account_namespaces": ["payments"],
				"token_policies": ["payments-payments-api"],
			}},
		},
		{
			"address": "module.service_onboard.vault_kv_secret_v2.paths[\"config\"]",
			"module_address": "module.service_onboard",
			"type": "vault_kv_secret_v2",
			"change": {"after": {"mount": "secret", "name": "teams/payments/payments-api/config"}},
		},
	],
}

# Helpers: change one value of the good plan, and look for a denial message.
with_policy(doc) := json.patch(good, [{"op": "replace", "path": "/resource_changes/0/change/after/policy", "value": doc}])

with_role(field, value) := json.patch(good, [{"op": "replace", "path": concat("/", ["/resource_changes/1/change/after", field]), "value": value}])

denied(plan, needle) if {
	some msg in deny with input as plan
	contains(msg, needle)
}

# ------------------------------------------------------------------ good plan

test_good_plan_passes if {
	count(deny) == 0 with input as good
}

test_exact_secret_paths_pass if {
	doc := `path "secret/data/teams/payments/payments-api/config" { capabilities = ["read"] }`
	count(deny) == 0 with input as with_policy(doc)
}

# --------------------------------------------------------------- policy paths

# The case the old policy let through.
test_whole_teams_tree_with_update_delete_denied if {
	plan := with_policy(`path "secret/data/teams/*" { capabilities = ["read", "update", "delete"] }`)
	denied(plan, "is not under secret/(data|metadata)/teams/<team>/<service>/")
	denied(plan, "must grant only read and list")
}

test_other_team_denied if {
	denied(with_policy(`path "secret/data/teams/billing/payments-api/*" { capabilities = ["read"] }`), "is not under")
}

test_sibling_service_denied if {
	denied(with_policy(`path "secret/data/teams/payments/payments-worker/*" { capabilities = ["read"] }`), "is not under")
}

test_whole_team_denied if {
	denied(with_policy(`path "secret/data/teams/payments/*" { capabilities = ["read"] }`), "is not under")
}

test_sys_path_denied if {
	denied(with_policy(`path "sys/policies/acl/*" { capabilities = ["read"] }`), "is not under")
}

test_other_mount_denied if {
	denied(with_policy(`path "kv/data/teams/payments/payments-api/*" { capabilities = ["read"] }`), "is not under")
}

test_glob_inside_segment_denied if {
	denied(with_policy(`path "secret/data/teams/payments/payments-api/+/admin" { capabilities = ["read"] }`), "is not under")
}

# One bad stanza among good ones is still caught: every stanza is judged.
test_second_stanza_is_checked if {
	doc := concat("\n", [good_policy, `path "secret/data/teams/*" { capabilities = ["read"] }`])
	denied(with_policy(doc), "is not under")
}

# -------------------------------------------------------------- capabilities

test_update_denied if {
	denied(with_policy(`path "secret/data/teams/payments/payments-api/*" { capabilities = ["read", "update"] }`), "must grant only read and list")
}

# The old rule only matched delete as the first entry with exact spacing.
test_delete_anywhere_in_list_denied if {
	denied(with_policy(`path "secret/data/teams/payments/payments-api/*" { capabilities=["list","delete"] }`), "must grant only read and list")
}

test_sudo_denied if {
	denied(with_policy(`path "secret/data/teams/payments/payments-api/*" { capabilities = ["sudo"] }`), "must grant only read and list")
}

test_empty_capabilities_denied if {
	denied(with_policy(`path "secret/data/teams/payments/payments-api/*" { capabilities = [] }`), "must grant only read and list")
}

test_extra_stanza_key_denied if {
	doc := `path "secret/data/teams/payments/payments-api/*" {
  capabilities = ["read"]
  min_wrapping_ttl = "1s"
}`
	denied(with_policy(doc), "must grant only read and list")
}

test_text_outside_stanzas_denied if {
	doc := concat("\n", [good_policy, `# path "x" is fine, trust me`])
	denied(with_policy(doc), "text that is not a path stanza")
}

test_empty_policy_denied if {
	denied(with_policy(""), "no readable path stanza")
}

# A policy document the plan does not know yet must not pass by absence.
test_unknown_policy_denied if {
	plan := json.patch(good, [{"op": "remove", "path": "/resource_changes/0/change/after/policy"}])
	denied(plan, "no readable path stanza")
}

# ----------------------------------------------------------------------- role

test_two_service_accounts_denied if {
	denied(with_role("bound_service_account_names", ["payments-api", "other"]), "exactly one named service account")
}

test_wildcard_service_account_denied if {
	denied(with_role("bound_service_account_names", ["*"]), "exactly one named service account")
}

test_two_namespaces_denied if {
	denied(with_role("bound_service_account_namespaces", ["payments", "default"]), "exactly one named namespace")
}

test_wildcard_namespace_denied if {
	denied(with_role("bound_service_account_namespaces", ["*"]), "exactly one named namespace")
}

test_missing_namespace_denied if {
	plan := json.patch(good, [{"op": "remove", "path": "/resource_changes/1/change/after/bound_service_account_namespaces"}])
	denied(plan, "exactly one named namespace")
}

test_extra_token_policy_denied if {
	denied(with_role("token_policies", ["payments-payments-api", "root"]), "must carry only its own policy")
}

test_foreign_token_policy_denied if {
	denied(with_role("token_policies", ["default"]), "must carry only its own policy")
}

test_role_name_must_match_policy if {
	denied(with_role("role_name", "payments-other"), "must equal policy name")
}

# ---------------------------------------------------------------- module only

test_inline_resource_denied if {
	inline := {
		"address": "vault_policy.extra",
		"type": "vault_policy",
		"change": {"after": {"name": "payments-payments-api", "policy": good_policy}},
	}
	plan := json.patch(good, [{"op": "add", "path": "/resource_changes/-", "value": inline}])
	denied(plan, "is declared outside module.service_onboard")
	denied(plan, "exactly one vault_policy")
}

test_other_resource_type_denied if {
	other := {
		"address": "module.service_onboard.vault_token.x",
		"module_address": "module.service_onboard",
		"type": "vault_token",
		"change": {"after": {}},
	}
	denied(json.patch(good, [{"op": "add", "path": "/resource_changes/-", "value": other}]), "is not allowed in a request")
}

test_other_module_source_denied if {
	plan := json.patch(good, [{"op": "replace", "path": "/configuration/root_module/module_calls/service_onboard/source", "value": "./my-own-module"}])
	denied(plan, "must use source")
}

test_second_module_call_denied if {
	plan := json.patch(good, [{"op": "add", "path": "/configuration/root_module/module_calls/extra", "value": {"source": "./x"}}])
	denied(plan, "unexpected module call")
}

test_no_role_denied if {
	plan := json.patch(good, [{"op": "remove", "path": "/resource_changes/1"}])
	denied(plan, "exactly one Kubernetes auth role")
}

test_empty_plan_denied if {
	denied({}, "exactly one vault_policy")
	denied({}, "must use source")
}

# --------------------------------------------------------------- KV scaffolds

test_secret_in_other_team_denied if {
	plan := json.patch(good, [{"op": "replace", "path": "/resource_changes/2/change/after/name", "value": "teams/billing/ledger/config"}])
	denied(plan, "is not under secret/teams/<team>/<service>/")
}

test_secret_path_traversal_denied if {
	plan := json.patch(good, [{"op": "replace", "path": "/resource_changes/2/change/after/name", "value": "teams/payments/payments-api/../../billing/x"}])
	denied(plan, "is not under secret/teams/<team>/<service>/")
}
