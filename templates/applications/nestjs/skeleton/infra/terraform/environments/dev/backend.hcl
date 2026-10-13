# State location only - no credentials (Entra auth through OIDC).
resource_group_name  = "rg-idp-tfstate-${{ values.environment }}"
storage_account_name = "stidptfstate${{ values.environment }}"
container_name       = "apps"
key                  = "apps/${{ values.name }}/${{ values.environment }}.tfstate"
use_azuread_auth     = true
use_oidc             = true
