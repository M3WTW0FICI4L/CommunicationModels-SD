# Teardown: destroy all AWS resources created by redeploy.ps1.
# Safe to run any time — empties the S3 results bucket first, then
# runs `cdk destroy`. The S3 assets bucket and the EC2 key pair are
# kept (they're cheap to leave around and useful on next redeploy).

$ErrorActionPreference = "Continue"
$BaseDir = Split-Path -Parent $PSScriptRoot
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
$env:AWS_CA_BUNDLE = "$env:USERPROFILE\.aws\ca-bundle.pem"
$env:NODE_EXTRA_CA_CERTS = "$env:USERPROFILE\.aws\ca-bundle.pem"

Write-Host "=== Emptying S3 results bucket (if any) ===" -ForegroundColor Cyan
$outputsPath = Join-Path $BaseDir "config\stack_outputs.json"
if (Test-Path $outputsPath) {
    $outputs = Get-Content $outputsPath -Raw | ConvertFrom-Json
    if ($outputs.ResultsBucketName) {
        aws s3 rm "s3://$($outputs.ResultsBucketName)" --recursive 2>&1 | Out-Null
    }
}

Write-Host "`n=== cdk destroy ===" -ForegroundColor Cyan
Push-Location (Join-Path $BaseDir "infra")
try {
    cdk destroy --force 2>&1 | Out-Host
} finally {
    Pop-Location
}

Remove-Item $outputsPath -ErrorAction SilentlyContinue
Write-Host "`nDone." -ForegroundColor Green
