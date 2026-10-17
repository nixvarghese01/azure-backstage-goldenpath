# Start/stop the local platform from Windows (PowerShell, VS Code terminal). Everything runs in
# Ubuntu (WSL2) with Docker Engine; this only forwards to scripts/local/platform.sh and the Makefile.
#
#   .\scripts\local\platform.ps1 up                start the platform, wait until healthy
#   .\scripts\local\platform.ps1 status            containers, health, URL
#   .\scripts\local\platform.ps1 logs [-Service orchestrator-worker]
#   .\scripts\local\platform.ps1 e2e               golden-path check through the running platform
#   .\scripts\local\platform.ps1 test              Python and portal checks in throwaway containers
#   .\scripts\local\platform.ps1 down [-StopWsl]   stop this platform; -StopWsl also shuts Ubuntu down,
#                                                  but only when nothing else runs there
#   .\scripts\local\platform.ps1 restart
#
# Independent of other projects in the same Ubuntu (e.g. k8s-ai-agent-platform's k3s): this stack only
# uses Docker Engine, its own Compose project, volumes and ports (7007, 5432), and never stops k3s.
param(
    [Parameter(Mandatory, Position = 0)][ValidateSet('up', 'down', 'restart', 'status', 'logs', 'e2e', 'test')][string]$Action,
    [string]$Service,
    [switch]$StopWsl
)
$ErrorActionPreference = 'Stop'
$distro = 'Ubuntu-26.04'

# E:\Github\azure-backstage-goldenpath\scripts\local -> /mnt/e/Github/azure-backstage-goldenpath
$root = (Resolve-Path "$PSScriptRoot\..\..").Path
$wslRoot = "/mnt/$($root.Substring(0, 1).ToLower())" + ($root.Substring(2) -replace '\\', '/')

function Invoke-Make([string[]]$Targets) {
    wsl -d $distro --cd $wslRoot -- make @Targets
    if ($LASTEXITCODE -ne 0) { throw "make $($Targets -join ' ') failed ($LASTEXITCODE)" }
}

function Stop-Ubuntu {
    if (-not $StopWsl) { return }
    # Shutting Ubuntu down would also stop anything else running there; refuse if anything is.
    $others = wsl -d $distro -- sh -c "docker ps -q | wc -l; systemctl is-active k3s 2>/dev/null || true"
    if ([int]$others[0] -gt 0 -or $others[1] -eq 'active') {
        "Ubuntu kept running: other containers or k3s are active there."
        return
    }
    wsl --terminate $distro | Out-Null
    'Ubuntu stopped; its memory is released.'
}

switch ($Action) {
    'up' { Invoke-Make @('up') }
    'status' { Invoke-Make @('status') }
    'logs' { if ($Service) { Invoke-Make @('logs', "S=$Service") } else { Invoke-Make @('logs') } }
    'e2e' { Invoke-Make @('e2e') }
    'test' { Invoke-Make @('check') }
    'down' { Invoke-Make @('down'); Stop-Ubuntu }
    'restart' { Invoke-Make @('restart') }
}
