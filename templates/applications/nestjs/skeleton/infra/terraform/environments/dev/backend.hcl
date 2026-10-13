# State location only - no credentials (Entra auth through OIDC).
resource_group_name  = "rg-sportify-tfstate-${{ values.environment }}"
storage_account_name = "stsportifytfstate${{ values.environment }}"
container_name       = "apps"
key                  = "apps/${{ values.name }}/${{ values.environment }}.tfstate"
use_azuread_auth     = true
use_oidc             = true
