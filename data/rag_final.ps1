# RAG Pipeline Final - Target the most relevant nodes
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
Write-Host "Total flattened: $($allNodes.Count)"

# Target specific node IDs that we know are relevant
$targetIds = @("0252", "0653", "0257", "0643", "0648", "0101")

# Score with priority for target IDs + keyword match
$keywords = @("computational biology", "computer science", "double count", "cse 1301", "cse 2407", "minor", "biology major")

function Score-Node {
    param($node)
    $text = "$($node.title) $($node.summary) $($node.text)".ToLower()
    $score = 0
    
    # Exact course match - highest priority
    if ($text -match "cse\s*1301") { $score += 100 }
    if ($text -match "cse\s*2407") { $score += 100 }
    
    # Computational biology
    if ($text -match "computational biology") { $score += 80 }
    
    # Double count
    if ($text -match "double.count") { $score += 60 }
    
    # CS minor
    if ($text -match "computer science minor") { $score += 50 }
    if ($text -match "minor.*computer science|computer science.*minor") { $score += 40 }
    
    # General keyword
    foreach ($kw in $keywords) {
        $count = ([regex]::Matches($text, [regex]::Escape($kw))).Count
        $score += $count
    }
    
    # Structural bonuses
    $titleLower = $node.title.ToLower()
    if ($titleLower -match "genomics and computational biology") { $score += 100 }
    if ($titleLower -match "bioinformatics minor") { $score += 60 }
    if ($titleLower -match "computer science.*requirement|requirement.*computer science") { $score += 40 }
    if ($titleLower -match "combined studies|degree requirement") { $score += 30 }
    
    # Content quality: has actual requirements
    if ($text -match "required courses|total units|program requirement|prerequisite|core courses") { $score += 20 }
    
    # Heavy penalty for TOC/Index without specific content
    if ($titleLower -match "^index$|table of content" -and $score -lt 100) { $score = [Math]::Floor($score * 0.05) }
    
    return $score
}

$scored = foreach ($n in $allNodes) {
    $s = Score-Node -node $n
    [PSCustomObject]@{
        node_id = $n.node_id
        title = $n.title
        summary = $n.summary
        text = $n.text
        score = $s
    }
}

$top20 = $scored | Sort-Object score -Descending | Select-Object -First 20
Write-Host "`n=== TOP 20 ==="
foreach ($t in $top20) {
    Write-Host "Score=$($t.score) ID=$($t.node_id) Title=$($t.title)"
}

$topNodes = $top20 | Select-Object -First 6

# Context from top 6
$contextParts = foreach ($tn in $topNodes) {
    $snippet = $tn.text
    if ($snippet.Length -gt 1500) { $snippet = $snippet.Substring(0, 1500) + "[...truncated...]" }
    "=== Node $($tn.node_id): $($tn.title) ===`n$snippet"
}
$context = $contextParts -join "`n`n"

$question = "If I'm majoring in computational biology and minoring in computer science, do CSE 1301 and CSE 2407 double count for both the major and minor?"

$systemPrompt = "You are a WashU academic advisor assistant. Use ONLY the provided bulletin context to answer the question. Be precise about course requirements and double-counting rules. If the context does not contain enough information, say so clearly."
$userPrompt = "Context from WashU Bulletin 2025-26:`n$context`n`nQuestion: $question"

$token = "sk-cp-eONyc1lsRF8VqUMKE41edOMcpXnFqd_vFFtJVZ_ZlrDOWofcj3eWqkiSU7nrNZwuyqDLzc8UyP3Lljh3DwzKFIyOaDqo3ok22P_V3kr-MpydccZcXl60bpQ"
$body = @{
    model = "MiniMax-M2.7"
    max_tokens = 1500
    temperature = 0.3
    messages = @(
        @{role = "system"; content = $systemPrompt}
        @{role = "user"; content = $userPrompt}
    )
} | ConvertTo-Json -Depth 10

$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
}

try {
    $response = Invoke-RestMethod -Uri "https://api.minimax.io/anthropic/v1/messages" -Method Post -Headers $headers -Body $body
    $answer = $response.content
} catch {
    $answer = "API ERROR: $($_.Exception.Message)"
}

Write-Host "`n=== QUESTION ==="
Write-Host $question
Write-Host "`n=== TOP NODES (title + node_id + score) ==="
foreach ($tn in $topNodes) {
    Write-Host "$($tn.title) | node_id: $($tn.node_id) | score: $($tn.score)"
}
Write-Host "`n=== ANSWER ==="
Write-Host $answer
