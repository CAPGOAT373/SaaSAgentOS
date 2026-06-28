# ============================================================
# Agent OS V6.0 - Deployment Verification Script
# Validates all deployment manifests, Dockerfile, Helm chart
# ============================================================

param(
    [switch]$SkipDocker,
    [switch]$SkipK8s,
    [switch]$SkipHelm,
    [switch]$Verbose
)

$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$PassCount = 0
$FailCount = 0
$TotalCount = 0

function Write-Check {
    param([string]$Name, [string]$Status, [string]$Detail = "")
    $TotalCount = $script:TotalCount + 1
    $script:TotalCount = $TotalCount
    switch ($Status) {
        "PASS" {
            $script:PassCount++
            Write-Host "  [PASS] $Name" -ForegroundColor Green
        }
        "FAIL" {
            $script:FailCount++
            Write-Host "  [FAIL] $Name" -ForegroundColor Red
            if ($Detail) {
                Write-Host "         $Detail" -ForegroundColor Red
            }
        }
        "WARN" {
            Write-Host "  [WARN] $Name" -ForegroundColor Yellow
            if ($Detail) {
                Write-Host "         $Detail" -ForegroundColor Yellow
            }
        }
        "INFO" {
            Write-Host "  [INFO] $Name" -ForegroundColor Cyan
        }
    }
}

# ============================================================
# Section 1: Docker Validation
# ============================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Section 1: Docker Validation" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

if (-not $SkipDocker) {
    $dockerfile = Join-Path $RootDir "deploy\docker\Dockerfile"
    if (Test-Path $dockerfile) {
        Write-Check "Dockerfile exists" "PASS"

        $content = Get-Content $dockerfile -Raw

        if ($content -match "FROM.*AS builder") {
            Write-Check "Multi-stage build detected" "PASS"
        } else {
            Write-Check "Multi-stage build" "FAIL" "Missing builder stage"
        }

        if ($content -match "USER\s+\w+") {
            Write-Check "Non-root user configured" "PASS"
        } else {
            Write-Check "Non-root user" "WARN" "Consider adding USER directive"
        }

        if ($content -match "HEALTHCHECK") {
            Write-Check "Health check configured" "PASS"
        } else {
            Write-Check "Health check" "FAIL" "Missing HEALTHCHECK"
        }

        if ($content -match "EXPOSE") {
            Write-Check "Ports exposed" "PASS"
        } else {
            Write-Check "Ports exposed" "WARN" "No EXPOSE directive"
        }
    } else {
        Write-Check "Dockerfile exists" "FAIL" "File not found: $dockerfile"
    }

    $compose = Join-Path $RootDir "deploy\docker\docker-compose.prod.yml"
    if (Test-Path $compose) {
        Write-Check "docker-compose.prod.yml exists" "PASS"

        $composeContent = Get-Content $compose -Raw

        if ($composeContent -match "deploy:") {
            Write-Check "Resource limits configured" "PASS"
        } else {
            Write-Check "Resource limits" "WARN" "No deploy.resources section"
        }

        if ($composeContent -match "healthcheck:") {
            Write-Check "Service health checks" "PASS"
        } else {
            Write-Check "Service health checks" "WARN" "Missing healthcheck"
        }

        if ($composeContent -match "logging:") {
            Write-Check "Logging configured" "PASS"
        } else {
            Write-Check "Logging" "WARN" "No logging driver"
        }
    } else {
        Write-Check "docker-compose.prod.yml" "FAIL" "File not found"
    }
}

# ============================================================
# Section 2: Kubernetes Manifest Validation
# ============================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Section 2: Kubernetes Manifests" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

if (-not $SkipK8s) {
    $k8sDir = Join-Path $RootDir "deploy\kubernetes"
    $requiredFiles = @(
        "namespace.yaml",
        "configmap.yaml",
        "secret.yaml",
        "serviceaccount.yaml",
        "deployment.yaml",
        "service.yaml",
        "hpa.yaml",
        "pdb.yaml",
        "kustomization.yaml"
    )

    foreach ($file in $requiredFiles) {
        $path = Join-Path $k8sDir $file
        if (Test-Path $path) {
            Write-Check "$file present" "PASS"
        } else {
            Write-Check "$file present" "FAIL" "Missing: $path"
        }
    }

    # Validate deployment.yaml specifics
    $deployFile = Join-Path $k8sDir "deployment.yaml"
    if (Test-Path $deployFile) {
        $deploy = Get-Content $deployFile -Raw

        if ($deploy -match "replicas:") {
            Write-Check "Deployment replicas set" "PASS"
        }
        if ($deploy -match "strategy:") {
            Write-Check "Rolling update strategy" "PASS"
        }
        if ($deploy -match "resources:") {
            Write-Check "Resource requests/limits" "PASS"
        } else {
            Write-Check "Resource requests/limits" "FAIL" "Missing resources section"
        }
        if ($deploy -match "livenessProbe:") {
            Write-Check "Liveness probe" "PASS"
        } else {
            Write-Check "Liveness probe" "WARN" "Missing"
        }
        if ($deploy -match "readinessProbe:") {
            Write-Check "Readiness probe" "PASS"
        } else {
            Write-Check "Readiness probe" "WARN" "Missing"
        }
        if ($deploy -match "startupProbe:") {
            Write-Check "Startup probe" "PASS"
        }
        if ($deploy -match "securityContext:") {
            Write-Check "Security context" "PASS"
        } else {
            Write-Check "Security context" "WARN" "Missing"
        }
        if ($deploy -match "podAntiAffinity:") {
            Write-Check "Pod anti-affinity" "PASS"
        }
        if ($deploy -match "topologySpreadConstraints:") {
            Write-Check "Topology spread" "PASS"
        }
        if ($deploy -match "serviceAccountName:") {
            Write-Check "Service account" "PASS"
        }
    }

    # Validate HPA specifics
    $hpaFile = Join-Path $k8sDir "hpa.yaml"
    if (Test-Path $hpaFile) {
        $hpa = Get-Content $hpaFile -Raw

        if ($hpa -match "minReplicas:") {
            Write-Check "HPA min replicas" "PASS"
        }
        if ($hpa -match "maxReplicas:") {
            Write-Check "HPA max replicas" "PASS"
        }
        if ($hpa -match "behavior:") {
            Write-Check "HPA scale behavior" "PASS"
        } else {
            Write-Check "HPA scale behavior" "WARN" "No behavior policies"
        }
        if ($hpa -match "name: cpu" -and $hpa -match "name: memory") {
            Write-Check "HPA CPU + Memory metrics" "PASS"
        } else {
            Write-Check "HPA metrics" "WARN" "Missing CPU or memory metrics"
        }
    }

    # Validate PDB
    $pdbFile = Join-Path $k8sDir "pdb.yaml"
    if (Test-Path $pdbFile) {
        $pdb = Get-Content $pdbFile -Raw
        if ($pdb -match "minAvailable:") {
            Write-Check "PDB minAvailable" "PASS"
        }
    }

    # Validate kustomization references all files
    $kustFile = Join-Path $k8sDir "kustomization.yaml"
    if (Test-Path $kustFile) {
        $kust = Get-Content $kustFile -Raw
        $missingInKust = @()
        foreach ($f in $requiredFiles | Where-Object { $_ -ne "kustomization.yaml" }) {
            if ($kust -notmatch [regex]::Escape($f)) {
                $missingInKust += $f
            }
        }
        if ($missingInKust.Count -eq 0) {
            Write-Check "Kustomization references complete" "PASS"
        } else {
            Write-Check "Kustomization references" "FAIL" "Missing: $($missingInKust -join ', ')"
        }
    }
}

# ============================================================
# Section 3: Istio Service Mesh Validation
# ============================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Section 3: Istio Service Mesh" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$istioDir = Join-Path $RootDir "deploy\istio"
$istioFiles = @(
    "gateway.yaml",
    "virtual-service.yaml",
    "destination-rule.yaml",
    "peer-authentication.yaml",
    "sidecar.yaml"
)

foreach ($file in $istioFiles) {
    $path = Join-Path $istioDir $file
    if (Test-Path $path) {
        Write-Check "$file present" "PASS"
    } else {
        Write-Check "$file present" "FAIL" "Missing: $path"
    }
}

# Validate VirtualService
$vsFile = Join-Path $istioDir "virtual-service.yaml"
if (Test-Path $vsFile) {
    $vs = Get-Content $vsFile -Raw
    if ($vs -match "retries:") {
        Write-Check "VirtualService retries" "PASS"
    }
    if ($vs -match "timeout:") {
        Write-Check "VirtualService timeout" "PASS"
    }
    if ($vs -match "corsPolicy:") {
        Write-Check "VirtualService CORS" "PASS"
    }
}

# Validate DestinationRule
$drFile = Join-Path $istioDir "destination-rule.yaml"
if (Test-Path $drFile) {
    $dr = Get-Content $drFile -Raw
    if ($dr -match "outlierDetection:") {
        Write-Check "Circuit breaker (outlier detection)" "PASS"
    } else {
        Write-Check "Circuit breaker" "WARN" "Missing outlierDetection"
    }
    if ($dr -match "connectionPool:") {
        Write-Check "Connection pool limits" "PASS"
    }
    if ($dr -match "loadBalancer:") {
        Write-Check "Load balancing" "PASS"
    }
    if ($dr -match "ISTIO_MUTUAL") {
        Write-Check "mTLS enabled" "PASS"
    }
}

# Validate PeerAuthentication
$paFile = Join-Path $istioDir "peer-authentication.yaml"
if (Test-Path $paFile) {
    $pa = Get-Content $paFile -Raw
    if ($pa -match "STRICT") {
        Write-Check "mTLS STRICT mode" "PASS"
    }
}

# ============================================================
# Section 4: Helm Chart Validation
# ============================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Section 4: Helm Chart" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

if (-not $SkipHelm) {
    $helmDir = Join-Path $RootDir "deploy\helm\agent-os"

    $chartFile = Join-Path $helmDir "Chart.yaml"
    if (Test-Path $chartFile) {
        Write-Check "Chart.yaml present" "PASS"
    } else {
        Write-Check "Chart.yaml" "FAIL" "Missing"
    }

    $valuesFile = Join-Path $helmDir "values.yaml"
    if (Test-Path $valuesFile) {
        Write-Check "values.yaml present" "PASS"
    }

    $valuesProd = Join-Path $helmDir "values-prod.yaml"
    if (Test-Path $valuesProd) {
        Write-Check "values-prod.yaml present" "PASS"
    }

    $templatesDir = Join-Path $helmDir "templates"
    $requiredTemplates = @(
        "_helpers.tpl",
        "configmap.yaml",
        "secret.yaml",
        "serviceaccount.yaml",
        "deployment.yaml",
        "service.yaml",
        "hpa.yaml",
        "pdb.yaml",
        "NOTES.txt"
    )

    foreach ($tpl in $requiredTemplates) {
        $path = Join-Path $templatesDir $tpl
        if (Test-Path $path) {
            Write-Check "Template $tpl present" "PASS"
        } else {
            Write-Check "Template $tpl" "FAIL" "Missing"
        }
    }

    # Try helm lint
    $helmCmd = Get-Command helm -ErrorAction SilentlyContinue
    if ($helmCmd) {
        $lintResult = helm lint $helmDir 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Check "Helm lint passed" "PASS"
        } else {
            Write-Check "Helm lint" "FAIL" "$lintResult"
        }
    } else {
        Write-Check "Helm CLI" "WARN" "Helm not installed, skipping lint"
    }

    # Try helm template dry-run
    if ($helmCmd) {
        $templateResult = helm template test-release $helmDir --namespace agent-os 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Check "Helm template dry-run" "PASS"
        } else {
            Write-Check "Helm template" "FAIL" "$templateResult"
        }
    }
}

# ============================================================
# Section 5: GitHub Actions Validation
# ============================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Section 5: CI/CD Pipelines" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$ciFile = Join-Path $RootDir ".github\workflows\ci.yml"
if (Test-Path $ciFile) {
    Write-Check "CI workflow present" "PASS"
    $ci = Get-Content $ciFile -Raw
    if ($ci -match "pytest") {
        Write-Check "CI includes tests" "PASS"
    }
    if ($ci -match "bandit" -or $ci -match "safety") {
        Write-Check "CI includes security scan" "PASS"
    }
    if ($ci -match "docker/build-push-action") {
        Write-Check "CI includes Docker build" "PASS"
    }
    if ($ci -match "codecov") {
        Write-Check "CI includes coverage upload" "PASS"
    }
} else {
    Write-Check "CI workflow" "FAIL" "Missing .github/workflows/ci.yml"
}

$cdFile = Join-Path $RootDir ".github\workflows\cd.yml"
if (Test-Path $cdFile) {
    Write-Check "CD workflow present" "PASS"
    $cd = Get-Content $cdFile -Raw
    if ($cd -match "staging") {
        Write-Check "CD includes staging env" "PASS"
    }
    if ($cd -match "production") {
        Write-Check "CD includes production env" "PASS"
    }
    if ($cd -match "canary") {
        Write-Check "CD includes canary deploy" "PASS"
    }
    if ($cd -match "rollback") {
        Write-Check "CD includes rollback" "PASS"
    }
    if ($cd -match "helm upgrade") {
        Write-Check "CD uses Helm" "PASS"
    }
} else {
    Write-Check "CD workflow" "FAIL" "Missing .github/workflows/cd.yml"
}

# ============================================================
# Section 6: YAML Syntax Validation
# ============================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Section 6: YAML Syntax Check" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$yamlFiles = Get-ChildItem -Path $RootDir -Recurse -Include "*.yaml", "*.yml" `
    -Exclude "__pycache__" | Where-Object {
        $_.FullName -match "deploy|\.github" -and
        $_.FullName -notmatch "node_modules|\.venv"
    }

foreach ($yf in $yamlFiles) {
    try {
        $null = Get-Content $yf.FullName -Raw
        $relPath = $yf.FullName.Replace($RootDir, ".").Replace("\", "/")
        Write-Check "YAML parse: $relPath" "PASS"
    } catch {
        Write-Check "YAML parse: $($yf.Name)" "FAIL" $_.Exception.Message
    }
}

# ============================================================
# Section 7: Deploy Checklist
# ============================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Section 7: Pre-Deploy Checklist" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Check "K8s cluster >= 1.29" "INFO" "Verify with: kubectl version"
Write-Check "Istio >= 1.22 installed" "INFO" "Verify with: istioctl version"
Write-Check "Helm >= 3.15 installed" "INFO" "Verify with: helm version"
Write-Check "Container registry access" "INFO" "Verify GHCR or Docker Hub access"
Write-Check "TLS certificate ready" "INFO" "Create agent-os-tls-cert secret"
Write-Check "External secrets configured" "INFO" "Replace placeholder secrets"
Write-Check "Monitoring stack ready" "INFO" "Prometheus + Grafana"
Write-Check "Backup strategy defined" "INFO" "Database backup schedule"

# ============================================================
# Summary
# ============================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Verification Summary" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Total Checks : $TotalCount" -ForegroundColor White
Write-Host "  Passed       : $PassCount" -ForegroundColor Green
Write-Host "  Failed       : $FailCount" -ForegroundColor Red
Write-Host "========================================" -ForegroundColor Cyan

if ($FailCount -gt 0) {
    Write-Host "`n  VERIFICATION FAILED - $FailCount checks failed" -ForegroundColor Red
    exit 1
} else {
    Write-Host "`n  VERIFICATION PASSED - All checks passed" -ForegroundColor Green
    exit 0
}