# Subscription vending from subscriptions.d/*.json (one file per orchestrator platform request).
# Needs an EA or MCA billing scope; on a free or pay-as-you-go account leave billing_scope null and keep
# subscriptions.d empty (the form disables "Create new subscription" in that case).

terraform {
  required_version = "~> 1.16.0"
  required_providers {
    azapi = {
      source  = "Azure/azapi"
      version = "~> 2.13"
    }
  }
  backend "azurerm" {}
}

provider "azapi" {}

variable "billing_scope" {
  type    = string
  default = null
}

variable "management_group_id" {
  type    = string
  default = null
}

locals {
  requests = {
    for f in fileset(path.module, "subscriptions.d/*.json") :
    trimsuffix(basename(f), ".json") => jsondecode(file("${path.module}/${f}"))
  }
}

resource "terraform_data" "vending_possible" {
  lifecycle {
    precondition {
      condition     = length(local.requests) == 0 || (var.billing_scope != null && var.management_group_id != null)
      error_message = "Subscription requests exist but no EA/MCA billing scope or management group is configured."
    }
  }
}

module "subscription" {
  for_each            = local.requests
  source              = "../../modules/subscription-vending"
  name                = each.key
  billing_scope       = var.billing_scope
  management_group_id = var.management_group_id
  workload            = try(each.value.environment, "dev") == "prod" ? "Production" : "DevTest"
  tags = {
    "managed-by"   = "idp-platform"
    "lifecycle"    = "platform"
    "environment"  = try(each.value.environment, "dev")
    "request-id"   = try(each.value.request_id, "")
    "requested-by" = try(each.value.requested_by, "")
  }
  depends_on = [terraform_data.vending_possible]
}

output "subscriptions" {
  value = { for k, m in module.subscription : k => m.subscription_id }
}
