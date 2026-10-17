# Subscription vending through the Microsoft.Subscription alias API. Needs an EA or MCA billing scope;
# a free or pay-as-you-go account can't vend subscriptions (the form disables this option there).

variable "name" {
  type = string
}

variable "billing_scope" {
  description = "EA enrollment account or MCA invoice section resource ID."
  type        = string
  validation {
    condition     = startswith(var.billing_scope, "/providers/Microsoft.Billing/")
    error_message = "billing_scope must be a Microsoft.Billing resource ID."
  }
}

variable "management_group_id" {
  type = string
}

variable "workload" {
  type    = string
  default = "DevTest"
  validation {
    condition     = contains(["Production", "DevTest"], var.workload)
    error_message = "workload must be Production or DevTest."
  }
}

variable "tags" {
  type = map(string)
}

resource "azapi_resource" "alias" {
  type      = "Microsoft.Subscription/aliases@2021-10-01"
  name      = var.name
  parent_id = "/"
  body = {
    properties = {
      displayName  = var.name
      billingScope = var.billing_scope
      workload     = var.workload
      additionalProperties = {
        managementGroupId = var.management_group_id
        tags              = var.tags
      }
    }
  }
  response_export_values = ["properties.subscriptionId"]
}

output "subscription_id" {
  value = azapi_resource.alias.output.properties.subscriptionId
}
