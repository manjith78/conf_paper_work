$ErrorActionPreference = "Stop"

$Root = (Get-Location).Path
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$PackageDir = Join-Path $Root "CLAUDE_EVIDENCE_PACKAGE"
$Log = Join-Path $PackageDir "CLAUDE_COMPLETE_RESEARCH_LOG.txt"
$Brief = Join-Path $PackageDir "CLAUDE_PAPER_BRIEF.txt"
$Manifest = Join-Path $PackageDir "CLAUDE_FILE_MANIFEST.txt"
$Zip = Join-Path $Root ("SSM_FINAL_REBUILD_CLAUDE_PACKAGE_" + $Stamp + ".zip")

if (Test-Path $PackageDir) { Remove-Item $PackageDir -Recurse -Force }
New-Item -ItemType Directory -Path $PackageDir | Out-Null

function Add-Line([string]$s="") {
    Add-Content -LiteralPath $Log -Value $s -Encoding UTF8
}

function Add-Section([string]$title) {
    Add-Line ""
    Add-Line ("=" * 90)
    Add-Line $title
    Add-Line ("=" * 90)
}

"SSM FINAL REBUILD 2026 - COMPLETE EVIDENCE PACKAGE" | Set-Content $Log -Encoding UTF8
Add-Line "Generated: $(Get-Date -Format o)"
Add-Line "Project root: $Root"
Add-Line "Purpose: independent paper construction/review from the reproducible implementation and generated evidence."
Add-Line "IMPORTANT: This log is evidence, not a source of invented or tuned numbers."

Add-Section "1. ENVIRONMENT"
try { Add-Line (& python --version 2>&1 | Out-String).Trim() } catch { Add-Line "python command unavailable" }
try { Add-Line (& git --version 2>&1 | Out-String).Trim() } catch { Add-Line "git command unavailable" }
try {
    $venvPy = Join-Path $Root ".venv\Scripts\python.exe"
    if (Test-Path $venvPy) {
        Add-Line "Venv Python:"
        Add-Line ((& $venvPy --version 2>&1 | Out-String).Trim())
        Add-Line "Installed packages:"
        Add-Line ((& $venvPy -m pip freeze 2>&1 | Out-String).Trim())
    }
} catch {}

Add-Section "2. AUTHORITATIVE GENERATED JSON - VERBATIM"
$jsonFiles = @(
    "results\json\crypto_benchmark.json",
    "results\json\ssm_activity_summary.json",
    "results\json\sensitivity_analysis.json"
)
foreach ($rel in $jsonFiles) {
    $p = Join-Path $Root $rel
    Add-Line ""
    Add-Line "FILE: $rel"
    if (Test-Path $p) {
        Add-Line ((Get-Content -LiteralPath $p -Raw -Encoding UTF8).Trim())
    } else { Add-Line "MISSING" }
}

Add-Section "3. AUTHORITATIVE GENERATED CSV - VERBATIM"
$csvFiles = @(
    "results\csv\ssm_event_log.csv",
    "results\csv\ssm_session_summary.csv",
    "results\csv\sanity_trace_25event_S01_AEROBIC.csv",
    "paper\tables\table_ii_crypto_benchmark.csv",
    "paper\tables\table_iii_ssm_results.csv"
)
foreach ($rel in $csvFiles) {
    $p = Join-Path $Root $rel
    Add-Line ""
    Add-Line "FILE: $rel"
    if (Test-Path $p) {
        Add-Line ((Get-Content -LiteralPath $p -Raw -Encoding UTF8).Trim())
    } else { Add-Line "MISSING" }
}

Add-Section "4. ALL PROJECT TEXT/CONFIG FILES - VERBATIM"
$includeExt = @(".txt",".md",".json",".csv",".py",".bat",".ps1",".pv",".toml",".ini",".cfg",".yaml",".yml",".gitignore",".lock")
$excludeDirs = @(".venv",".git","__pycache__",".pytest_cache","CLAUDE_EVIDENCE_PACKAGE")
$files = Get-ChildItem -LiteralPath $Root -Recurse -File | Where-Object {
    $okDir = $true
    foreach ($d in $excludeDirs) {
        if ($_.FullName -like "*\$d\*") { $okDir = $false }
    }
    $okDir -and ($includeExt -contains $_.Extension.ToLower() -or $_.Name -eq ".gitignore")
} | Sort-Object FullName

foreach ($f in $files) {
    $rel = $f.FullName.Substring($Root.Length).TrimStart("\")
    Add-Line ""
    Add-Line ("--- FILE: " + $rel + " ---")
    try { Add-Line ((Get-Content -LiteralPath $f.FullName -Raw -Encoding UTF8).TrimEnd()) }
    catch { Add-Line "[Could not read as UTF-8 text: $($_.Exception.Message)]" }
}

Add-Section "5. BINARY FILE MANIFEST AND SHA-256"
$binaryExt = @(".png",".jpg",".jpeg",".webp",".pdf",".docx",".xlsx",".pptx",".zip",".exe",".dll")
$binaryFiles = Get-ChildItem -LiteralPath $Root -Recurse -File | Where-Object {
    $okDir = $true
    foreach ($d in $excludeDirs) {
        if ($_.FullName -like "*\$d\*") { $okDir = $false }
    }
    $okDir -and ($binaryExt -contains $_.Extension.ToLower())
} | Sort-Object FullName

foreach ($f in $binaryFiles) {
    $rel = $f.FullName.Substring($Root.Length).TrimStart("\")
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $f.FullName).Hash
    Add-Line "$rel`t$($f.Length) bytes`tSHA256=$hash"
}

Add-Section "6. REPRODUCIBILITY STATE"
$required = @(
"requirements-lock.txt",
"run_all.py",
"run_all.bat",
"REPRODUCE_ALL.bat",
"README.md",
"results\json\crypto_benchmark.json",
"results\json\ssm_activity_summary.json",
"results\json\sensitivity_analysis.json",
"results\csv\ssm_event_log.csv",
"results\csv\ssm_session_summary.csv",
"paper\tables\table_ii_crypto_benchmark.csv",
"paper\tables\table_iii_ssm_results.csv",
"paper\figures\fig3_compute_cost.png",
"paper\figures\fig4_sensitivity_tmax.png",
"paper\figures\fig5_sensitivity_ath.png",
"formal_verification\protocol_model.pv",
"formal_verification\unbounded_attempt.pv"
)
foreach ($rel in $required) {
    $p = Join-Path $Root $rel
    if (Test-Path $p) { Add-Line "PRESENT`t$rel" } else { Add-Line "MISSING`t$rel" }
}

# Human-readable paper brief.
@"
SSM FINAL REBUILD 2026 — PAPER CONSTRUCTION BRIEF FOR CLAUDE

ROLE
Act as an independent academic paper editor and reproducibility reviewer.
Use the supplied project files and CLAUDE_COMPLETE_RESEARCH_LOG.txt as the evidence base.

NON-NEGOTIABLE EVIDENCE RULES
1. Do not invent, smooth, round selectively, interpolate, or tune measured values.
2. Do not alter the implementation to make the paper look better.
3. If a value is measured, use the value from the latest generated result files.
4. If a value is not supported by the files, mark it as unsupported and do not put it in the paper as a fact.
5. Every table and figure must be traceable to results/ or an explicitly cited external source.
6. Keep the implementation, protocol description, formal model, tables, figures, and prose consistent.
7. If a benchmark timing changes between runs, use the latest supplied authoritative result set; do not average unrelated runs unless the experiment explicitly defines such averaging.
8. Preserve limitations and uncertainty. Do not convert a modeling limitation into a security proof.

CURRENT FROZEN EXPERIMENT CONFIGURATION
T_MAX = 900 s (15 min)
R_MAX = 10
A_TH = 0.5
w1 = 0.7
w2 = 0.3
check cadence/window = 20 s
AES-128-GCM for data transport
HKDF-SHA256 for key derivation
HMAC-SHA256 for resumption authentication
Ed25519 identity signatures
ML-KEM-512 key establishment

DATASET / PREPROCESSING
Official PhysioNet Wearable Device Dataset v1.0.0.
Zip SHA-256:
229b6cd388d0193bea1320e01bee7ca8525c168920add7d95f4969ae6d57899c
708/708 extracted files checksum verified.
36 distinct subjects.
97 canonical sessions:
STRESS 36
AEROBIC 30
ANAEROBIC 31
10,318 real windows.
Three documented split sessions preserve real gaps:
STRESS/f14 = 91.3 s
AEROBIC/S11 = 219.1 s
ANAEROBIC/S16 = 51.4 s
Reconnection elapsed deltas:
f14 = 115.0 s
S11 = 258.0 s
S16 = 80.0 s
STRESS/S02 ACC is capped at 49,542 genuine samples to remove documented duplication.

LATEST REPRODUCTION SUMMARY
Python 3.14.7
pytest 9.1.1
23/23 pytest tests passed.
SSM engine tests: 16/16 passed.
Protocol tests: 7/7 passed.
Dataset verification: 708/708 passed.
Latest headline benchmark summary from the supplied run:
Full handshake = 20.001059666666666 ms
Resumption = 0.0562782 ms
Full handshake bytes = 928
Resumption bytes = 96

Latest SSM activity summary from the supplied run:
STRESS:
  n_real_sessions = 36
  mean_session_wallclock_duration_min = 42.27
  mean_full_events_per_session = 15.6944
  mean_resume_events_per_session = 110.9722
  extrapolated_full_events_per_24h = 534.71
  extrapolated_resume_events_per_24h = 3780.8
  proposed_compute_ms_per_24h = 10907.47
  proposed_compute_ms_per_24h_std_across_sessions = 1829.8
  always_full_baseline_compute_ms_per_24h = 86314.67
  compute_time_reduction_pct = 87.36
  proposed_bytes_per_24h = 859164.0
  always_full_baseline_bytes_per_24h = 4004788.3
  bandwidth_reduction_pct = 78.55

AEROBIC:
  n_real_sessions = 30
  mean_session_wallclock_duration_min = 36.5
  mean_full_events_per_session = 17.5
  mean_resume_events_per_session = 91.6
  extrapolated_full_events_per_24h = 690.43
  extrapolated_resume_events_per_24h = 3613.92
  proposed_compute_ms_per_24h = 14012.76
  proposed_compute_ms_per_24h_std_across_sessions = 4002.02
  always_full_baseline_compute_ms_per_24h = 86091.57
  compute_time_reduction_pct = 83.72
  proposed_bytes_per_24h = 987657.0
  always_full_baseline_bytes_per_24h = 3994437.0
  bandwidth_reduction_pct = 75.27

ANAEROBIC:
  n_real_sessions = 31
  mean_session_wallclock_duration_min = 26.75
  mean_full_events_per_session = 11.6129
  mean_resume_events_per_session = 68.5484
  extrapolated_full_events_per_24h = 625.08
  extrapolated_resume_events_per_24h = 3689.71
  proposed_compute_ms_per_24h = 12709.92
  proposed_compute_ms_per_24h_std_across_sessions = 2506.54
  always_full_baseline_compute_ms_per_24h = 86300.39
  compute_time_reduction_pct = 85.27
  proposed_bytes_per_24h = 934286.8
  always_full_baseline_bytes_per_24h = 4004126.0
  bandwidth_reduction_pct = 76.67

SENSITIVITY
Use results/json/sensitivity_analysis.json as the complete authoritative source.
Do not omit points or replace them with a simplified trend.
Defaults held when one parameter is swept:
T_MAX=900 s, R_MAX=10, A_TH=0.5.
The supplied latest console output reports:
T_MAX minutes: 1 -> 69.4%; 3 -> 82.87%; 5 -> 83.72%; 10 -> 83.72%; 15 -> 83.72%; 30 -> 83.72%; 60 -> 83.72%.
A_TH: 0.1 -> 26.84%; 0.2 -> 52.71%; 0.3 -> 69.56%; 0.4 -> 78.24%; 0.5 -> 83.72%; 0.6 -> 86.28%; 0.7 -> 87.9%; 0.8 -> 90.15%; 0.9 -> 90.15%; 1.0 -> 90.15%.
R_MAX: 2 -> 62.0%; 5 -> 77.17%; 10 -> 83.72%; 15 -> 85.8%; 20 -> 87.17%; 30 -> 87.96%.
The raw JSON in the complete log takes precedence if any formatting differs.

PROTOCOL / SECURITY DESCRIPTION
Wearable device uses Ed25519 identity keys and ML-KEM-512 keys.
Full authentication:
GW sends fresh nonce N1.
WD signs N1 with Ed25519.
WD creates N2.
GW verifies sigma1.
GW performs real ML-KEM-512 encapsulation.
GW signs N2 || ciphertext with Ed25519.
WD verifies sigma2 and decapsulates.
Both derive session/resumption material using HKDF-SHA256.
Resumption uses gateway-held per-device ticket/session state, fresh nonces and HMAC-SHA256. Successful resumption avoids Ed25519/ML-KEM and derives a fresh session key with HKDF.
AES-128-GCM protects data.
Do not describe a separately transmitted encrypted ticket credential unless the implementation actually contains one. The implementation stores gateway-side per-device ticket state and a monotonic resumption count.

IMPORTANT IMPLEMENTATION FIX
The gateway previously used one global pending nonce for resumption, which could cause cross-device interleaving failure.
It was corrected to store pending nonces per device:
_pending_n3[device_id].
A permanent regression test now verifies interleaved resumption is per-device.
Current protocol test count is 7 and full pytest count is 23.

FORMAL VERIFICATION
The authoritative single-session ProVerif model has 8 queries.
The unbounded replicated attempt has one unresolved injective correspondence query that is false.
Do not claim all unbounded replicated properties are proven.
Do not call the replicated-model result a confirmed implementation vulnerability.
Explain it as an open modeling limitation because the replicated model does not faithfully represent the implementation's shared per-device ticket state/counter.
If ProVerif was not run on the current machine, distinguish existing checked artifacts from a fresh local execution.

PAPER CONTENT REQUIREMENTS
The paper should include:
- problem and motivation for session resumption in wearable healthcare IoT;
- threat/security model;
- protocol architecture and sequence;
- exact SSM decision logic and frozen thresholds;
- dataset and preprocessing decisions;
- reproducible experimental methodology;
- cryptographic benchmark table;
- 24-hour extrapolated activity results table;
- sensitivity analysis figures/tables;
- security/formal verification section with the exact scope;
- implementation/interleaving regression fix where relevant;
- limitations including only three documented split/reconnection cases, linear 24-hour extrapolation, benchmark machine dependence, and formal-model scope;
- reproducibility statement.

FIGURES
The pipeline-generated figures are evidence-backed:
paper/figures/fig3_compute_cost.png
paper/figures/fig4_sensitivity_tmax.png
paper/figures/fig5_sensitivity_ath.png
Do not create a graph with numbers different from the raw result files.
New publication-quality versions may be redrawn, but the data points must remain identical.

TABLES
Use:
paper/tables/table_ii_crypto_benchmark.csv
paper/tables/table_iii_ssm_results.csv
The complete raw values are also preserved in the JSON/CSV evidence section of the log.

FINAL REVIEW REQUEST
Before finalizing the manuscript:
1. Compare every numerical statement to the evidence log.
2. Check every table cell against its source.
3. Check every figure data point against its source.
4. Search for stale old-paper values such as 41 sessions, A_TH=1.5, old 74.5–85.0% compute reduction, old 67–76% bandwidth reduction, old Intel Xeon benchmark, and old 11.15/0.034 ms timings. None should remain unless explicitly discussed as historical discarded results.
5. Do not silently repair unsupported claims. Flag them.
6. Produce a final manuscript only after the evidence check.
"@ | Set-Content $Brief -Encoding UTF8

# Manifest with hashes for all project files, excluding the package itself and heavy environment/cache folders.
$manifestLines = @("SSM FINAL REBUILD 2026 - FILE MANIFEST","Generated: $(Get-Date -Format o)","")
Get-ChildItem -LiteralPath $Root -Recurse -File | Where-Object {
    $_.FullName -notlike "*\.venv\*" -and
    $_.FullName -notlike "*\.git\*" -and
    $_.FullName -notlike "*\__pycache__\*" -and
    $_.FullName -notlike "*\.pytest_cache\*" -and
    $_.FullName -notlike "*\CLAUDE_EVIDENCE_PACKAGE\*"
} | Sort-Object FullName | ForEach-Object {
    $rel = $_.FullName.Substring($Root.Length).TrimStart("\")
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash
    $manifestLines += "$rel`t$($_.Length) bytes`tSHA256=$hash"
}
$manifestLines | Set-Content $Manifest -Encoding UTF8

# Copy the main evidence artifacts verbatim into the package as a convenient subfolder.
$RawDir = Join-Path $PackageDir "raw_evidence"
New-Item -ItemType Directory -Path $RawDir | Out-Null
foreach ($rel in $jsonFiles + $csvFiles) {
    $src = Join-Path $Root $rel
    if (Test-Path $src) {
        $dest = Join-Path $RawDir (($rel -replace '[\\/]','__'))
        Copy-Item $src $dest -Force
    }
}

# Include the generated log/brief/manifest in the project root copy inside the zip.
Compress-Archive -Path $PackageDir -DestinationPath $Zip -CompressionLevel Optimal -Force

Write-Host ""
Write-Host "============================================================"
Write-Host "CLAUDE EVIDENCE PACKAGE CREATED"
Write-Host "============================================================"
Write-Host "Log:      $Log"
Write-Host "Brief:    $Brief"
Write-Host "Manifest: $Manifest"
Write-Host "ZIP:      $Zip"
Write-Host ""
Write-Host "The ZIP contains the evidence package only."
Write-Host "Send Claude BOTH:"
Write-Host "  1. The full SSM project folder/ZIP"
Write-Host "  2. This evidence-package ZIP"
Write-Host ""
Write-Host "Do NOT rerun the benchmark merely to create the log."
Write-Host "============================================================"
