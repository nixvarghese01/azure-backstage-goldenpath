# Rendered Helm chart policy (secret-management.md §7, README security principles).
# Run: helm template ... > rendered.yaml && conftest test rendered.yaml -p policies/helm
package main

import rego.v1

secret_like := `(?i)(_KEY|_SECRET|_PASSWORD|_TOKEN|CONNECTION_?STRING|SAS)$`

workload_kinds := {"Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob"}

# Readiness gates Service traffic, so it only applies to long-running workloads, not Jobs.
long_running_kinds := {"Deployment", "StatefulSet", "DaemonSet"}

pod_spec(obj) := obj.spec.template.spec if obj.kind in {"Deployment", "StatefulSet", "DaemonSet", "Job"}

pod_spec(obj) := obj.spec.jobTemplate.spec.template.spec if obj.kind == "CronJob"

deny contains msg if {
	input.kind == "Secret"
	msg := sprintf("Secret/%s: charts must not create Secret objects; use Key Vault + Workload Identity", [input.metadata.name])
}

deny contains msg if {
	input.kind in workload_kinds
	some c in pod_spec(input).containers
	some e in c.env
	regex.match(secret_like, e.name)
	e.value
	msg := sprintf("%s/%s: env %s looks like a secret and has a literal value", [input.kind, input.metadata.name, e.name])
}

deny contains msg if {
	input.kind in workload_kinds
	not pod_spec(input).securityContext.runAsNonRoot
	msg := sprintf("%s/%s: pod must set runAsNonRoot: true", [input.kind, input.metadata.name])
}

deny contains msg if {
	input.kind in workload_kinds
	some c in pod_spec(input).containers
	not c.securityContext.allowPrivilegeEscalation == false
	msg := sprintf("%s/%s: container %s must set allowPrivilegeEscalation: false", [input.kind, input.metadata.name, c.name])
}

deny contains msg if {
	input.kind in workload_kinds
	some c in pod_spec(input).containers
	not "ALL" in c.securityContext.capabilities.drop
	msg := sprintf("%s/%s: container %s must drop ALL capabilities", [input.kind, input.metadata.name, c.name])
}

deny contains msg if {
	input.kind in workload_kinds
	some c in pod_spec(input).containers
	not c.resources.limits.memory
	msg := sprintf("%s/%s: container %s must set a memory limit", [input.kind, input.metadata.name, c.name])
}

deny contains msg if {
	input.kind in long_running_kinds
	some c in pod_spec(input).containers
	not c.readinessProbe
	msg := sprintf("%s/%s: container %s needs a readiness probe", [input.kind, input.metadata.name, c.name])
}
