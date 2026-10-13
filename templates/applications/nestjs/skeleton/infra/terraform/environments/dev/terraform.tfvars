# Rendered from the Backstage form (request ${{ values.requestId }}) and validated by the platform.
# Change through a pull request; the platform plans it and asks for approval in Backstage.

application       = "${{ values.name }}"
environment       = "${{ values.environment }}"
owner             = "${{ values.owner | replace('group:default/', '') }}"
request_id        = "${{ values.requestId }}"
repository        = "${{ values.org }}/${{ values.name }}"
region            = "${{ values.infrastructure.region }}"
subscription_id   = "${{ values.infrastructure.subscription.id }}"
availability_tier = "${{ values.availabilityTier }}"

resource_group = {
  mode = "${{ values.infrastructure.resourceGroup.mode }}"
  name = "${{ values.infrastructure.resourceGroup.name }}"
}

aks_cluster = {
  name           = "${{ values.infrastructure.aksCluster.name }}"
  resource_group = "${{ values.infrastructure.aksCluster.resourceGroup }}"
}

container_registry = {
  name           = "${{ values.infrastructure.containerRegistry.name }}"
  resource_group = "${{ values.infrastructure.containerRegistry.resourceGroup }}"
}

namespace = {
  mode = "${{ values.infrastructure.namespace.mode }}"
  name = "${{ values.infrastructure.namespace.name }}"
}

runtime_capability = {
  type           = "${{ values.infrastructure.runtimeCapability.type }}"
  mode           = "${{ values.infrastructure.runtimeCapability.mode }}"
  name           = "${{ values.infrastructure.runtimeCapability.name }}"
  resource_group = "${{ values.infrastructure.runtimeCapability.resourceGroup }}"
}

deployment_identity = {
  name           = "id-idp-deployment-${{ values.environment }}"
  resource_group = "rg-idp-identities-${{ values.environment }}"
}
