# Search for specific content in the bulletin
$ErrorActionPreference = "Stop"

# Load JSON
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

# Search for computational biology
Write-Host "=== NODES MENTIONING 'computational biology' ==="
foreach ($n in $allNodes) {
    $text = "$($n.title) $($n.summary) $($n.text)".ToLower()
    if ($text -match "computational biology") {
        Write-Host "ID=$($n.node_id) Title=$($n.title)"
        Write-Host "  Summary: $($n.summary.Substring(0, [Math]::Min(200, $n.summary.Length)))"
        Write-Host "  Text snippet: $($n.text.Substring(0, [Math]::Min(300, $n.text.Length)))"
        Write-Host ""
    }
}

# Search for CSE 1301
Write-Host "`n=== NODES MENTIONING 'CSE 1301' ==="
foreach ($n in $allNodes) {
    $text = "$($n.title) $($n.summary) $($n.text)".ToLower()
    if ($text -match "cse\s*1301") {
        Write-Host "ID=$($n.node_id) Title=$($n.title)"
        $idx = $text.IndexOf("cse 1301")
        $start = [Math]::Max(0, $idx - 50)
        $end = [Math]::Min($n.text.Length, $idx + 150)
        Write-Host "  Context: ...$($n.text.Substring($start, $end - $start))..."
        Write-Host ""
    }
}

# Search for CSE 2407
Write-Host "`n=== NODES MENTIONING 'CSE 2407' ==="
foreach ($n in $allNodes) {
    $text = "$($n.title) $($n.summary) $($n.text)".ToLower()
    if ($text -match "cse\s*2407") {
        Write-Host "ID=$($n.node_id) Title=$($n.title)"
        Write-Host ""
    }
}

# Search for double count
Write-Host "`n=== NODES MENTIONING 'double count' (first 5) ==="
$count = 0
foreach ($n in $allNodes) {
    $text = "$($n.title) $($n.summary) $($n.text)".ToLower()
    if ($text -match "double.count") {
        Write-Host "ID=$($n.node_id) Title=$($n.title)"
        $idx = $text.IndexOf("double")
        $start = [Math]::Max(0, $idx - 100)
        $end = [Math]::Min($n.text.Length, $idx + 200)
        if ($n.text.Length -gt 100) {
            Write-Host "  Context: ...$($n.text.Substring($start, [Math]::Min(200, $n.text.Length - $start)))..."
        }
        $count++
        if ($count -ge 5) { break }
    }
}

# Search for biology major (genomics/computational)
Write-Host "`n=== NODES MENTIONING 'Biology Major, Genomics and Computational Biology' ==="
foreach ($n in $allNodes) {
    $text = "$($n.title) $($n.summary) $($n.text)".ToLower()
    if ($text -match "genomics and computational biology|biology major.*computational|computational biology.*major") {
        Write-Host "ID=$($n.node_id) Title=$($n.title)"
        Write-Host "  Summary: $($n.summary.Substring(0, [Math]::Min(300, $n.summary.Length)))"
        Write-Host ""
    }
}
