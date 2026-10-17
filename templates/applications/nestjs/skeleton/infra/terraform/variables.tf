# Typed, validated inputs. Values come from environments/<env>/terraform.tfvars, rendered from the
# Backstage form and already validated on the server (ADR-0002 §3-4).

variable "application" {
  type = string
}

variable "environment" {
  type = string
}

variable "owner" {
  description = "Owning team name (without the group:default/ prefix)."
  type        = string
}

variable "request_id" {
  type = string
}

variable "repository" {
  type = string
}

variable "region" {
  type = string
}

variable "subscription_id" {
  type = string
}

variable "resource_group" {
  type = object({
    mode = string # new | existing
    name = string
  })
  validation {
    condition     = contains(["new", "existing"], var.resource_group.mode)
    error_message = "resource_group.mode must be new or existing."
  }
}

variable "aks_cluster" {
  description = "Always an existing shared cluster in an application repository."
  type = object({
    name           = string
    resource_group = string
  })
}

variable "container_registry" {
  description = "Always an existing shared registry in an application repository."
  type = object({
    name           = string
    resource_group = string
  })
}

variable "namespace" {
  type = object({
    mode = string
    name = string
  })
  validation {
    condition     = contains(["new", "existing"], var.namespace.mode)
    error_message = "namespace.mode must be new or existing."
  }
}

variable "runtime_capability" {
  type = object({
    type           = string # storage | keyvault | none
    mode           = optional(string, "existing")
    name           = optional(string)
    resource_group = optional(string) # for existing resources outside the app's resource group
  })
  validation {
    condition     = contains(["storage", "keyvault", "none"], var.runtime_capability.type)
    error_message = "runtime_capability.type must be storage, keyvault or none."
  }
  validation {
    condition     = var.runtime_capability.type == "none" || (contains(["new", "existing"], var.runtime_capability.mode) && var.runtime_capability.name != null)
    error_message = "runtime_capability needs mode (new|existing) and name."
  }
}

variable "availability_tier" {
  type    = string
  default = "standard"
  validation {
    condition     = contains(["standard", "ha"], var.availability_tier)
    error_message = "availability_tier must be standard or ha."
  }
}

variable "deployment_identity" {
  description = "The platform's deployment identity, bound to this namespace only."
  type = object({
    name           = string
    resource_group = string
  })
}
