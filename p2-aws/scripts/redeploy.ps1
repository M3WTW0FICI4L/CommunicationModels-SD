# One-shot redeploy for Practice 2 on a fresh AWS Academy account.
#
# Prerequisites:
#   1. New AWS Academy credentials pasted into ~/.aws/credentials
#   2. AWS CLI, Node.js, CDK already installed (from initial setup)
#
# Usage from p2-aws/:
#   powershell -ExecutionPolicy Bypass -File scripts/redeploy.ps1
#
# Idempotent: re-running is safe. Each step checks for existing state.

$ErrorActionPreference = "Stop"
$BaseDir = Split-Path -Parent $PSScriptRoot
$KeyPath = Join-Path $BaseDir "ticket-key.pem"
$OutputsPath = Join-Path $BaseDir "config\stack_outputs.json"
$Region = "us-east-1"

# ─── env: PATH + SSL ──────────────────────────────────────────────────────────
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
$env:AWS_CA_BUNDLE = "$env:USERPROFILE\.aws\ca-bundle.pem"
$env:NODE_EXTRA_CA_CERTS = "$env:USERPROFILE\.aws\ca-bundle.pem"

function Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }

# ─── 1. Verify credentials ────────────────────────────────────────────────────
Step "Step 1/8: verify AWS credentials"
$identity = aws sts get-caller-identity --output json | ConvertFrom-Json
if (-not $identity) { throw "AWS credentials invalid or expired. Refresh ~/.aws/credentials" }
$Account = $identity.Account
Write-Host "Account: $Account"
Write-Host "Arn:     $($identity.Arn)"

# ─── 2. S3 assets bucket for CDK Lambda code ──────────────────────────────────
Step "Step 2/8: ensure CDK assets bucket"
$Bucket = "ticket-cdk-assets-$Account"
aws s3 mb "s3://$Bucket" --region $Region 2>&1 | Out-Null
Write-Host "Bucket: $Bucket"

# ─── 3. EC2 key pair ──────────────────────────────────────────────────────────
Step "Step 3/8: ensure EC2 key pair"
$exists = aws ec2 describe-key-pairs --key-names ticket-key --query "KeyPairs[0].KeyName" --output text 2>$null
if ($exists -eq "ticket-key") {
    Write-Host "Key pair 'ticket-key' already exists in AWS."
    if (-not (Test-Path $KeyPath)) {
        Write-Host "WARNING: no local ticket-key.pem found. Deleting AWS key and recreating..."
        aws ec2 delete-key-pair --key-name ticket-key | Out-Null
        $exists = ""
    }
}
if ($exists -ne "ticket-key") {
    $raw = aws ec2 create-key-pair --key-name ticket-key --query KeyMaterial --output text
    # PowerShell collapses PEM newlines — reformat to PEM with 64-char lines.
    $begin = "-----BEGIN RSA PRIVATE KEY-----"
    $end = "-----END RSA PRIVATE KEY-----"
    $b64 = ($raw -replace [regex]::Escape($begin), "" -replace [regex]::Escape($end), "") -replace "\s", ""
    $lines = @()
    for ($i = 0; $i -lt $b64.Length; $i += 64) {
        $len = [Math]::Min(64, $b64.Length - $i)
        $lines += $b64.Substring($i, $len)
    }
    $pem = "$begin`n" + ($lines -join "`n") + "`n$end`n"
    [System.IO.File]::WriteAllText($KeyPath, $pem, [System.Text.UTF8Encoding]::new($false))
    icacls $KeyPath /inheritance:r /grant:r "${env:USERNAME}:R" | Out-Null
    Write-Host "Key pair created and saved to $KeyPath"
}

# ─── 4. cdk deploy ────────────────────────────────────────────────────────────
Step "Step 4/8: cdk deploy (~2 min)"
Push-Location (Join-Path $BaseDir "infra")
try {
    cdk deploy --require-approval never --outputs-file "$OutputsPath.cdk" 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "cdk deploy failed" }
} finally {
    Pop-Location
}

# ─── 5. parse outputs ─────────────────────────────────────────────────────────
Step "Step 5/8: parse stack outputs"
$cdkOut = Get-Content "$OutputsPath.cdk" -Raw | ConvertFrom-Json
$stack = $cdkOut.TicketServiceStack
$outputs = @{
    RabbitMQHost = $stack.RabbitMQHost
    PostgresHost = $stack.PostgresHost
    LambdaFunctionName = $stack.LambdaFunctionName
    ResultsBucketName = $stack.ResultsBucketName
    Region = $Region
    Account = $Account
    DeployedAt = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss")
}
New-Item -ItemType Directory -Path (Split-Path $OutputsPath) -Force | Out-Null
$outputs | ConvertTo-Json | Out-File -FilePath $OutputsPath -Encoding UTF8
Remove-Item "$OutputsPath.cdk" -ErrorAction SilentlyContinue
Write-Host "RabbitMQ EC2:  $($outputs.RabbitMQHost)"
Write-Host "Postgres EC2:  $($outputs.PostgresHost)"
Write-Host "Lambda:        $($outputs.LambdaFunctionName)"

# ─── 6. wait for EC2s to finish user-data ─────────────────────────────────────
Step "Step 6/8: wait ~2 min for EC2 user-data (Docker pull, PostgreSQL init)"
Start-Sleep -Seconds 120

# ─── 7. SSH setup of both EC2s ────────────────────────────────────────────────
Step "Step 7/8: configure PostgreSQL + RabbitMQ via SSH"
$ssh = "C:\Windows\System32\OpenSSH\ssh.exe"
$scp = "C:\Windows\System32\OpenSSH\scp.exe"
$sshOpts = @("-i", $KeyPath, "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15")

# --- PostgreSQL ---
Write-Host "PostgreSQL setup..."
& $scp -i $KeyPath -o StrictHostKeyChecking=no `
    (Join-Path $BaseDir "scripts\setup_postgres.sh") `
    "ec2-user@$($outputs.PostgresHost):~/setup_postgres.sh" | Out-Null
& $ssh @sshOpts "ec2-user@$($outputs.PostgresHost)" `
    'chmod +x setup_postgres.sh && bash setup_postgres.sh 2>&1 | tail -8'

# --- RabbitMQ ---
Write-Host "RabbitMQ setup..."
& $scp -i $KeyPath -o StrictHostKeyChecking=no `
    (Join-Path $BaseDir "scripts\setup_rabbitmq.sh") `
    "ec2-user@$($outputs.RabbitMQHost):~/setup_rabbitmq.sh" | Out-Null
& $ssh @sshOpts "ec2-user@$($outputs.RabbitMQHost)" `
    'chmod +x setup_rabbitmq.sh && sudo bash setup_rabbitmq.sh 2>&1 | tail -8'

# --- client to RabbitMQ EC2 (so we can run workload from there) ---
Write-Host "Uploading client + scaler..."
& $ssh @sshOpts "ec2-user@$($outputs.RabbitMQHost)" 'mkdir -p ~/client ~/results' | Out-Null
& $scp -i $KeyPath -o StrictHostKeyChecking=no `
    (Join-Path $BaseDir "src\client\workload_generator.py") `
    (Join-Path $BaseDir "src\client\benchmark_runner.py") `
    (Join-Path $BaseDir "src\client\calibrate.py") `
    (Join-Path $BaseDir "src\scaling\scaler.py") `
    "ec2-user@$($outputs.RabbitMQHost):~/client/" | Out-Null

# ─── 8. ensure local Python deps for analyzer / plotter ───────────────────────
Step "Step 8/8: install local Python deps for analyzer (if missing)"
python -m pip install --quiet boto3 pika psycopg2-binary matplotlib numpy 2>&1 | Select-Object -Last 2

# ─── done ─────────────────────────────────────────────────────────────────────
Write-Host "`nDONE. Outputs in $OutputsPath" -ForegroundColor Green
Write-Host ""
Write-Host "To run experiments from the RabbitMQ EC2:" -ForegroundColor Yellow
Write-Host "  ssh -i ticket-key.pem ec2-user@$($outputs.RabbitMQHost)"
Write-Host "  cd ~/client"
Write-Host "  LAMBDA_FUNCTION_NAME=$($outputs.LambdaFunctionName) \\"
Write-Host "    RABBITMQ_HOST=localhost PG_HOST=$($outputs.PostgresHost) \\"
Write-Host "    python3 scaler.py &"
Write-Host "  RABBITMQ_HOST=localhost RESULTS_DIR=~/results \\"
Write-Host "    python3 benchmark_runner.py --mode elastic --type unnumbered"
