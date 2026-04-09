# RAG Pipeline v4 - Using knowledge of key nodes
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

# Score with KNOCKOUT approach: nodes must have BOTH comp-bio AND CSE content
function Get-CombinedScore {
    param($node)
    $text = "$($node.title) $($node.summary) $($node.text)".ToLower()
    $title = $node.title.ToLower()
    
    $compBio = ($text -match "computational biology|genomics and computational biology|genomics.*computational|computational.*genomics")
    $cseCourse = ($text -match "cse\s*1301|cse\s*2407|cse-1301|cse-2407")
    $doubleCount = ($text -match "double.count")
    $csMinor = ($text -match "computer science minor")
    $bioMajor = ($text -match "biology major")
    
    # Knockout: must have comp bio OR double count policy
    $baseScore = 0
    
    # Primary boost: has both comp bio context AND CSE content
    if ($compBio -and $cseCourse) { $baseScore += 300 }
    
    # Secondary: comp bio specialization
    if ($title -match "genomics and computational biology|computational biology specialization") { $baseScore += 200 }
    
    # Secondary: has CSE courses
    if ($cseCourse) { $baseScore += 100 }
    if ($text -match "cse\s*1301") { $baseScore += 50 }
    if ($text -match "cse\s*2407") { $baseScore += 50 }
    
    # Double count
    if ($doubleCount) { $baseScore += 80 }
    
    # CS minor or bio major
    if ($csMinor) { $baseScore += 40 }
    if ($bioMajor) { $baseScore += 30 }
    
    # Content quality
    if ($text -match "program requirement|total units|core course|electives") { $baseScore += 20 }
    
    # Heavy penalty for TOC/Index
    if ($title -match "^index$|table of contents") { $baseScore = [Math]::Floor($baseScore * 0.05) }
    
    return $baseScore
}

$scored = foreach ($n in $allNodes) {
    $s = Get-CombinedScore -node $n
    [PSCustomObject]@{
        node_id = $n.node_id
        title = $n.title
        summary = $n.summary
        text = $n.text
        score = $s
    }
}

$top20 = $scored | Sort-Object score -Descending | Select-Object -First 20
Write-Host "`n=== TOP 20 BY COMBINED SCORE ==="
foreach ($t in $top20) {
    Write-Host "Score=$($t.score) ID=$($t.node_id) Title=$($t.title)"
}

$topNodes = $top20 | Select-Object -First 6

# Context
$contextParts = foreach ($tn in $topNodes) {
    $snippet = $tn.text
    if ($snippet.Length -gt 1500) { $snippet = $snippet.Substring(0, 1500) + "[...truncated...]" }
    "=== Node $($tn.node_id): $($tn.title) ===`n$snippet"
}
$context = $contextParts -join "`n`n"

$question = "If I'm majoring in computational biology and minoring in computer science, do CSE 1301 and CSE 2407 double count for both the major and minor?"

$systemPrompt = "You are a WashU academic advisor. Use ONLY the provided bulletin context to answer the question. Focus on: (1) whether Computational Biology is a standalone major or a specialization, (2) what courses the Biology Major with Genomics/Computational Biology specialization requires, (3) what courses the CS minor requires, (4) what the double-counting policy is. Be specific and cite course codes."
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
    $answer = "ERROR: $($_.Exception.Message)"
}

Write-Host "`n=== QUESTION ==="
Write-Host $question
Write-Host "`n=== TOP NODES (title + node_id + score) ==="
foreach ($tn in $topNodes) {
    Write-Host "$($tn.title) | node_id: $($tn.node_id) | score: $($tn.score)"
}
Write-Host "`n=== ANSWER ==="
Write-Host $answer
