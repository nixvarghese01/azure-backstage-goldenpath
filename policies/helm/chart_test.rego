package main_test

import rego.v1

import data.main

container := {
	"name": "app",
	"securityContext": {"allowPrivilegeEscalation": false, "capabilities": {"drop": ["ALL"]}, "readOnlyRootFilesystem": true},
	"resources": {"limits": {"memory": "256Mi"}},
	"readinessProbe": {"httpGet": {"path": "/health/ready", "port": 8080}},
}

workload(kind, c) := {
	"kind": kind,
	"metadata": {"name": "x"},
	"spec": {"template": {"spec": {"securityContext": {"runAsNonRoot": true}, "containers": [c]}}},
}

test_compliant_deployment_passes if {
	count(main.deny) == 0 with input as workload("Deployment", container)
}

test_deployment_without_readiness_denied if {
	some msg in main.deny with input as workload("Deployment", object.remove(container, ["readinessProbe"]))
	contains(msg, "readiness probe")
}

test_job_without_readiness_allowed if {
	count(main.deny) == 0 with input as workload("Job", object.remove(container, ["readinessProbe"]))
}

test_secret_object_denied if {
	some msg in main.deny with input as {"kind": "Secret", "metadata": {"name": "s"}}
	contains(msg, "must not create Secret objects")
}

test_root_pod_denied if {
	w := workload("Deployment", container)
	some msg in main.deny with input as json.patch(w, [{"op": "replace", "path": "/spec/template/spec/securityContext", "value": {}}])
	contains(msg, "runAsNonRoot")
}

test_literal_secret_env_denied if {
	c := object.union(container, {"env": [{"name": "DB_PASSWORD", "value": "x"}]})
	some msg in main.deny with input as workload("Deployment", c)
	contains(msg, "looks like a secret")
}
