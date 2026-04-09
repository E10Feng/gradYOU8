Get-ChildItem Env: | Where-Object { $_.Name -match 'MINIMAX' } | Format-Table Name,Value -AutoSize
