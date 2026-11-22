# What a request's Terraform plan is allowed to contain.
#
# Input: the plan as JSON (`terraform show -json plan.tfplan`).
# Every rule is written as "deny unless proven fine": a value that is missing
# or not yet known in the plan is a failure, never a pass.
package main

module_address := "module.service_onboard"

module_source := "../../../terraform/modules/vault-service-onboard"

allowed_types := {"vault_policy", "vault_kubernetes_auth_backend_role", "vault_kv_secret_v2"}

allowed_capabilities := {"read", "list"}

# resource_changes is a flat list, so nested modules cannot hide anything.
changes := object.get(input, "resource_changes", [])

policies := [r | some r in changes; r.type == "vault_policy"]

roles := [r | some r in changes; r.type == "vault_kubernetes_auth_backend_role"]

after(r) := object.get(r, ["change", "after"], {})

# ---------------------------------------------------------------- module only

deny contains msg if {
	some r in changes
	object.get(r, "module_address", "") != module_address
	msg := sprintf("%s is declared outside %s; requests must only call the module", [r.address, module_address])
}

deny contains msg if {
	some r in changes
	not r.type in allowed_types
	msg := sprintf("%s: resource type %s is not allowed in a request", [r.address, r.type])
}

deny contains msg if {
	source := object.get(input, ["configuration", "root_module", "module_calls", "service_onboard", "source"], "")
	source != module_source
	msg := sprintf("module service_onboard must use source %q, found %q", [module_source, source])
}

deny contains msg if {
	some name, _ in object.get(input, ["configuration", "root_module", "module_calls"], {})
	name != "service_onboard"
	msg := sprintf("unexpected module call %q; a request calls service_onboard only", [name])
}

deny contains msg if {
	count(policies) != 1
	msg := sprintf("a request must create exactly one vault_policy, found %d", [count(policies)])
}

deny contains msg if {
	count(roles) != 1
	msg := sprintf("a request must create exactly one Kubernetes auth role, found %d", [count(roles)])
}

# ------------------------------------------------------------- policy content
#
# A Vault policy is a string of `path "<path>" { capabilities = [...] }`
# stanzas. We pull out every stanza and judge its path and its capabilities
# one by one. Anything in the document that is not such a stanza is refused,
# so nothing can ride along unparsed.

stanza_re := `path\s+"([^"]*)"\s*\{([^{}]*)\}`

path_re := `^secret/(data|metadata)/teams/([a-z][a-z0-9]*)/([a-z][a-z0-9-]*)/(.*)$`

# After the service prefix: nothing, "*", or plain segments optionally ending in "/*".
suffix_re := `^([a-z0-9][a-z0-9_-]*/)*([a-z0-9][a-z0-9_-]*|\*)?$`

document(p) := object.get(after(p), "policy", "")

policy_name(p) := object.get(after(p), "name", "")

# Each stanza is [whole match, path, body].
stanzas(doc) := regex.find_all_string_submatch_n(stanza_re, doc, -1)

deny contains msg if {
	some p in policies
	count(stanzas(document(p))) == 0
	msg := sprintf("policy %q has no readable path stanza", [policy_name(p)])
}

deny contains msg if {
	some p in policies
	leftover := trim_space(regex.replace(document(p), stanza_re, ""))
	leftover != ""
	msg := sprintf("policy %q contains text that is not a path stanza: %q", [policy_name(p), leftover])
}

deny contains msg if {
	some p in policies
	some s in stanzas(document(p))
	not path_ok(s[1], policy_name(p))
	msg := sprintf(
		"policy %q: path %q is not under secret/(data|metadata)/teams/<team>/<service>/ of this policy's own team and service",
		[policy_name(p), s[1]],
	)
}

deny contains msg if {
	some p in policies
	some s in stanzas(document(p))
	not capabilities_ok(s[2])
	msg := sprintf("policy %q: path %q must grant only read and list, found: %s", [policy_name(p), s[1], trim_space(s[2])])
}

# The path's team and service, joined, must be the policy's own name. Team
# names carry no hyphen, so "<team>-<service>" splits one way only.
path_ok(path, name) if {
	m := regex.find_all_string_submatch_n(path_re, path, 1)[0]
	concat("-", [m[2], m[3]]) == name
	regex.match(suffix_re, m[4])
}

# The stanza body must be exactly one capabilities list, and every entry in
# it must be allowed. Extra keys (for example allowed_parameters) fail.
capabilities_ok(body) if {
	m := regex.find_all_string_submatch_n(`^\s*capabilities\s*=\s*\[([^\]]*)\]\s*$`, body, 1)[0]
	listed := {c[1] | some c in regex.find_all_string_submatch_n(`"([^"]*)"`, m[1], -1)}
	count(listed) > 0
	count(listed - allowed_capabilities) == 0
	trim_space(regex.replace(m[1], `"[^"]*"|,`, "")) == ""
}

# ----------------------------------------------------------------------- role

# A Kubernetes name: lowercase letters, digits and hyphens. "*" does not match.
plain_name_re := `^[a-z0-9]([a-z0-9-]*[a-z0-9])?$`

exactly_one_plain(values) if {
	count(values) == 1
	regex.match(plain_name_re, values[0])
}

deny contains msg if {
	some r in roles
	names := object.get(after(r), "bound_service_account_names", [])
	not exactly_one_plain(names)
	msg := sprintf("%s must bind exactly one named service account, found %v", [r.address, names])
}

deny contains msg if {
	some r in roles
	namespaces := object.get(after(r), "bound_service_account_namespaces", [])
	not exactly_one_plain(namespaces)
	msg := sprintf("%s must bind exactly one named namespace, found %v", [r.address, namespaces])
}

deny contains msg if {
	some r in roles
	some p in policies
	token_policies := object.get(after(r), "token_policies", [])
	token_policies != [policy_name(p)]
	msg := sprintf("%s must carry only its own policy %q, found %v", [r.address, policy_name(p), token_policies])
}

deny contains msg if {
	some r in roles
	some p in policies
	role_name := object.get(after(r), "role_name", "")
	role_name != policy_name(p)
	msg := sprintf("role name %q must equal policy name %q", [role_name, policy_name(p)])
}

# --------------------------------------------------------------- KV scaffolds

secret_re := `^teams/([a-z][a-z0-9]*)/([a-z][a-z0-9-]*)/[a-z0-9][a-z0-9_-]*(/[a-z0-9][a-z0-9_-]*)*$`

secret_ok(r, name) if {
	object.get(after(r), "mount", "") == "secret"
	m := regex.find_all_string_submatch_n(secret_re, object.get(after(r), "name", ""), 1)[0]
	concat("-", [m[1], m[2]]) == name
}

deny contains msg if {
	some r in changes
	r.type == "vault_kv_secret_v2"
	some p in policies
	not secret_ok(r, policy_name(p))
	msg := sprintf("%s: secret %q is not under secret/teams/<team>/<service>/ of policy %q", [r.address, object.get(after(r), "name", ""), policy_name(p)])
}
