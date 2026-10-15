mock_provider "kubernetes" {}

variables {
  name                  = "orders-api"
  owner                 = "team-orders"
  deployer_principal_id = "11111111-1111-1111-1111-111111111111"
}

run "restricted_namespace_with_standard_quota" {
  command = plan
  assert {
    condition     = kubernetes_namespace_v1.this.metadata[0].labels["pod-security.kubernetes.io/enforce"] == "restricted"
    error_message = "application namespaces enforce restricted Pod Security"
  }
  assert {
    condition     = kubernetes_namespace_v1.this.metadata[0].labels["idp.io/owner"] == "team-orders"
    error_message = "the owner label must be set"
  }
  assert {
    condition     = kubernetes_resource_quota_v1.default.spec[0].hard["requests.cpu"] == "1"
    error_message = "standard tier quota is 1 CPU requested"
  }
}

run "deployer_binding_is_the_deployer_role_only" {
  command = plan
  assert {
    condition     = kubernetes_role_binding_v1.deployer.role_ref[0].name == "idp-app-deployer"
    error_message = "the binding must grant only the deployer ClusterRole"
  }
  assert {
    condition     = kubernetes_role_binding_v1.deployer.subject[0].name == "11111111-1111-1111-1111-111111111111"
    error_message = "the binding must name the deployment identity"
  }
}

run "ha_tier_has_a_larger_quota" {
  command = plan
  variables {
    availability_tier = "ha"
  }
  assert {
    condition     = kubernetes_resource_quota_v1.default.spec[0].hard["pods"] == "20"
    error_message = "ha tier allows 20 pods"
  }
}

run "rejects_kube_prefixed_names" {
  command = plan
  variables {
    name = "kube-orders"
  }
  expect_failures = [var.name]
}
