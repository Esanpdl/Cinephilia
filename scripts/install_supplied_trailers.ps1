# Install the prepared owner-supplied batch using literal, workspace-checked paths.
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$planPath = Join-Path $projectRoot 'data/phase8/2026-09-18-owner-supplied/prepared.json'
$plan = Get-Content -LiteralPath $planPath -Raw -Encoding UTF8 | ConvertFrom-Json

function Assert-ProjectPath([string]$Candidate) {
    $resolved = [IO.Path]::GetFullPath($Candidate)
    if (-not $resolved.StartsWith($projectRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Path is outside the project: $resolved"
    }
    return $resolved
}

# Validate all sources and destinations before the first move. Resuming is safe.
foreach ($entry in $plan.parts.PSObject.Properties) {
    $part = $entry.Value
    $source = Assert-ProjectPath $part.original_path
    $archive = Assert-ProjectPath $part.archive_path
    $current = if (Test-Path -LiteralPath $source) { $source } else { $archive }
    if (-not (Test-Path -LiteralPath $current)) { throw "Missing input: $source" }
    if ((Get-FileHash -LiteralPath $current -Algorithm SHA256).Hash -ne $part.sha256) { throw "Input changed: $current" }
    if ((Test-Path -LiteralPath $source) -and (Test-Path -LiteralPath $archive)) { throw "Both source and archive exist: $source" }
}
foreach ($entry in $plan.outputs.PSObject.Properties) {
    $output = $entry.Value
    $target = Assert-ProjectPath $output.target_path
    $previous = Assert-ProjectPath $output.previous_path
    if ($output.prepared_path) {
        $prepared = Assert-ProjectPath $output.prepared_path
        $current = if (Test-Path -LiteralPath $prepared) { $prepared } else { $target }
        if ((Get-FileHash -LiteralPath $current -Algorithm SHA256).Hash -ne $output.sha256) { throw "Prepared video changed: $current" }
    }
    if ((Test-Path -LiteralPath $previous) -and (Test-Path -LiteralPath $target) -and
        (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $output.sha256) {
        throw "Cannot overwrite an existing archived predecessor: $target"
    }
}
foreach ($entry in $plan.parts.PSObject.Properties) {
    $part = $entry.Value
    $source = Assert-ProjectPath $part.original_path
    $archive = Assert-ProjectPath $part.archive_path
    New-Item -ItemType Directory -Path (Split-Path -Parent $archive) -Force | Out-Null
    if (Test-Path -LiteralPath $source) { Move-Item -LiteralPath $source -Destination $archive }
}
foreach ($entry in $plan.outputs.PSObject.Properties) {
    $output = $entry.Value
    $target = Assert-ProjectPath $output.target_path
    $previous = Assert-ProjectPath $output.previous_path
    if ((Test-Path -LiteralPath $target) -and (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -eq $output.sha256) { continue }
    New-Item -ItemType Directory -Path (Split-Path -Parent $previous) -Force | Out-Null
    if (Test-Path -LiteralPath $target) { Move-Item -LiteralPath $target -Destination $previous }
    if ($output.prepared_path) {
        $prepared = Assert-ProjectPath $output.prepared_path
        Move-Item -LiteralPath $prepared -Destination $target
    } else {
        $part = $plan.parts.PSObject.Properties[$output.parts[0]].Value
        $archive = Assert-ProjectPath $part.archive_path
        Copy-Item -LiteralPath $archive -Destination $target
    }
    if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $output.sha256) { throw "Installed checksum differs: $target" }
    Write-Output "Installed $($entry.Name).mp4"
}
Write-Output 'Supplied originals and replaced videos are preserved in data/raw/trailers/supplied and previous.'
