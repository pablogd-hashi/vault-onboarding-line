# Fix 1: the same rules as the old vault.rego and vault_module.rego, but in a
# shape conftest actually loads and runs: one file, `package main` (the
# namespace conftest evaluates by default) and current Rego syntax.
# Nothing is stricter yet. That is fix 2.
package main

deny contains msg if {
	some resource in input.planned_values.root_module.resources
	resource.type == "vault_policy"
	not startswith(resource.values.name, "test-")
	not contains(resource.values.policy, "teams/")
	msg := sprintf("Vault policy %s must scope paths under teams/", [resource.values.name])
}

deny contains msg if {
	some resource in input.planned_values.root_module.child_modules[_].resources
	resource.type == "vault_policy"
	contains(resource.values.policy, "capabilities = [\"create\"")
	msg := sprintf("Vault policy %s must not grant create capability on secret paths", [resource.values.name])
}

deny contains msg if {
	some resource in input.planned_values.root_module.child_modules[_].resources
	resource.type == "vault_policy"
	contains(resource.values.policy, "capabilities = [\"delete\"")
	msg := sprintf("Vault policy %s must not grant delete capability on secret paths", [resource.values.name])
}

deny contains msg if {
	some resource in input.planned_values.root_module.child_modules[_].resources
	resource.type == "vault_kubernetes_auth_backend_role"
	count(resource.values.bound_service_account_names) != 1
	msg := sprintf("K8s auth role %s must bind exactly one service account", [resource.values.role_name])
}
