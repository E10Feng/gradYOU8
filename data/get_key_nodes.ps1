# Get key nodes directly
$ErrorActionPreference = "Stop"
$bulletin = Get-Content 'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\data\bulletin_full.json' -Raw | ConvertFrom-Json

function Flatten-Nodes {
    param($nodes, [System.Collections.ArrayList]$acc)
    if ($null -eq $acc) { $acc = [System.Collections.ArrayList]::new() }
    foreach ($n in $nodes) {
        $null = $acc.Add($n)
        if ($n.nodes -and $n.nodes.Count -gt 0) {
            Flatten-Nodes -nodes $n.nodes -acc $acc | Out-Null
        }
    }
    return $acc
}

$allNodes = [System.Collections.ArrayList]::new()
foreach ($topNode in $bulletin) {
    $null = $allNodes.Add($topNode)
    if ($topNode.nodes -and $topNode.nodes.Count -gt 0) {
        Flatten-Nodes -nodes $topNode.nodes -acc $allNodes | Out-Null
    }
}

# Find key nodes
$keyIds = @("0252", "0653", "0257", "0101", "0648", "0643")
$found = $allNodes | Where-Object { $keyIds -contains $_.node_id }

foreach ($n in $found) {
    Write-Host "===== NODE $($n.node_id): $($n.title) ====="
    Write-Host "TEXT ($(($n.text).Length) chars):"
    Write-Host $n.text.Substring(0, [Math]::Min(2000, $n.text.Length))
    Write-Host ""
}
