# Names and standard tags for everything the platform creates (ADR-0002 §8). No resources.

variable "application" {
  description = "Application name (DNS-label style)."
  type        = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,30}[a-z0-9]$", var.application))
    error_message = "application must be 4-32 lowercase letters, digits or hyphens, starting with a letter."
  }
}

variable "environment" {
  type = string
  validation {
    condition     = contains(["dev", "test", "prod"], var.environment)
    error_message = "environment must be dev, test or prod."
  }
}

variable "owner" {
  description = "Owning team (Backstage group name, e.g. team-orders)."
  type        = string
}

variable "request_id" {
  description = "Orchestrator request ID (used by cleanup to find platform-created resources)."
  type        = string
  default     = ""
}

variable "repository" {
  description = "GitHub repository (org/name)."
  type        = string
  default     = ""
}

variable "availability_tier" {
  type    = string
  default = "standard"
  validation {
    condition     = contains(["standard", "ha"], var.availability_tier)
    error_message = "availability_tier must be standard or ha."
  }
}

variable "lifecycle_scope" {
  description = "application or platform."
  type        = string
  default     = "application"
  validation {
    condition     = contains(["application", "platform"], var.lifecycle_scope)
    error_message = "lifecycle_scope must be application or platform."
  }
}

variable "extra_tags" {
  description = <<-EOT
    Organisation tags required by the landing zone, e.g. costCenter, criticality, dataClassification
    (Cloud Adoption Framework tagging). Applied last, so they can't remove the standard tags below.
  EOT
  type        = map(string)
  default     = {}
}

locals {
  compact = replace(var.application, "-", "")

  tags = merge(
    var.extra_tags,
    {
      "managed-by"        = "idp-platform"
      "workload"          = var.application # CAF: the workload a resource belongs to
      "application"       = var.application
      "owner"             = var.owner
      "environment"       = var.environment
      "lifecycle"         = var.lifecycle_scope
      "availability-tier" = var.availability_tier
    },
    var.request_id == "" ? {} : { "request-id" = var.request_id },
    var.repository == "" ? {} : { "repository" = var.repository },
  )
}

output "tags" {
  description = "Standard tags to apply to every resource."
  value       = local.tags
}

output "names" {
  description = "Conventional names for application resources."
  value = {
    resource_group   = "rg-${var.application}-${var.environment}"
    runtime_identity = "id-${var.application}-${var.environment}"
    storage_account  = substr("st${local.compact}${var.environment}", 0, 24)
    key_vault        = substr("kv-${var.application}-${var.environment}", 0, 24)
    namespace        = var.application
    service_account  = var.application
  }
}
