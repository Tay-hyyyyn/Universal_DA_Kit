param(
  [Parameter(Mandatory=$true)]
  [string]$Config,

  [Parameter(Mandatory=$true)]
  [string]$RunId,

  [switch]$Resume,
  [switch]$AutoProceed,

  [ValidateSet("", "00P", "00", "01", "02", "02H", "03", "04", "05", "05H", "06", "07")]
  [string]$FromStage = "",

  [switch]$Interactive,
  [switch]$FullTrain,

  [ValidateSet("auto", "both", "raw", "log1p")]
  [string]$TargetMode = "auto",

  [string]$ExplainModels = "ridge,surrogate",
  [int]$TuningTrials = 8,
  [int]$MaxFolds = 0,
  [int]$Seed = 42,
  [int]$NJobs = 1,

  [ValidateSet("weighted", "simple", "best", "manual")]
  [string]$EnsembleMethod = "weighted",

  [string]$ManualWeights = "",
  [ValidateSet("auto", "none")]
  [string]$UpperClip = "auto",
  [switch]$NoPdfReport
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Resolve-ManualRoot {
  if ($PSCommandPath) { return (Split-Path -Parent $PSCommandPath) }
  return (Join-Path (Get-Location).Path "Manual")
}

function Resolve-Python {
  param([string]$RepoRoot)
  $venvPy = Join-Path $RepoRoot ".venv\Scripts\python.exe"
  if (Test-Path -LiteralPath $venvPy) { return $venvPy }
  $cmd = Get-Command python -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  throw "Python was not found. Create .venv or put python on PATH."
}

function Join-ManualPath {
  param([string]$RelativePath)
  return (Join-Path $manualRoot $RelativePath)
}

function Run-Step {
  param(
    [string]$Name,
    [string]$PythonExe,
    [string[]]$StepArgs
  )
  Write-Host ("[run] " + $Name)
  & $PythonExe @StepArgs
  if ($LASTEXITCODE -ne 0) { throw "Step failed: $Name" }
}

$PAUSE_EXIT_CODE = 2

function Get-ManualConfig {
  param([string]$ConfigPath)
  return (Get-Content -LiteralPath $ConfigPath -Raw -Encoding utf8 | ConvertFrom-Json)
}

function Get-ConfigBool {
  param(
    [object]$ConfigObject,
    [string]$Section,
    [string]$Key
  )
  if (-not $ConfigObject.PSObject.Properties.Name.Contains($Section)) { return $false }
  $sectionValue = $ConfigObject.$Section
  if (-not $sectionValue) { return $false }
  if (-not $sectionValue.PSObject.Properties.Name.Contains($Key)) { return $false }
  return [bool]$sectionValue.$Key
}

function Run-Checkpoint {
  param(
    [string]$StageBefore,
    [string]$PythonExe,
    [string]$ConfigPath,
    [string]$RunId,
    [string]$RunBase,
    [switch]$AutoProceed
  )
  Write-Host ("[checkpoint] domain before stage " + $StageBefore)
  $cpArgs = @(
    (Join-ManualPath "plugins/manual-domain-expert/scripts/domain_checkpoint.py"),
    "--config", $ConfigPath,
    "--run-id", $RunId,
    "--stage-before", $StageBefore
  )
  if ($AutoProceed) { $cpArgs += "--auto-proceed" }
  # Capture external output so this function can reliably return only a boolean.
  $cpOut = & $PythonExe @cpArgs 2>&1
  foreach ($line in $cpOut) { Write-Host $line }
  if ($LASTEXITCODE -eq 0) { return $true }
  if ($LASTEXITCODE -eq $PAUSE_EXIT_CODE) {
    Write-Host ""
    Write-Host "[pause] Domain checkpoint pending."
    Write-Host ("[pause] See: " + (Join-Path $RunBase "reports/pending_checkpoint.md"))
    Write-Host ("[pause] Edit: " + (Join-Path $RunBase "reports/domain_answers.md"))
    Write-Host "[pause] If you want to proceed with defaults: re-run with -AutoProceed (or tell the agent \"그냥 진행해줘\")."
    return $false
  }
  throw ("Checkpoint failed (exit=" + $LASTEXITCODE + "): stage_before=" + $StageBefore)
}

function Run-HypothesisCheckpoint {
  param(
    [string]$PythonExe,
    [string]$ConfigPath,
    [string]$RunId,
    [string]$RunBase,
    [switch]$AutoProceed
  )
  Write-Host "[checkpoint] hypothesis planning before stage 03"
  $cpArgs = @(
    (Join-ManualPath "plugins/manual-hypothesis-planner/scripts/hypothesis_planner.py"),
    "propose",
    "--config", $ConfigPath,
    "--run-id", $RunId
  )
  if ($AutoProceed) { $cpArgs += "--auto-proceed" }
  $cpOut = & $PythonExe @cpArgs 2>&1
  foreach ($line in $cpOut) { Write-Host $line }
  if ($LASTEXITCODE -eq 0) { return $true }
  if ($LASTEXITCODE -eq $PAUSE_EXIT_CODE) {
    Write-Host ""
    Write-Host "[pause] Hypothesis checkpoint pending."
    Write-Host ("[pause] See: " + (Join-Path $RunBase "reports/pending_hypothesis_checkpoint.md"))
    Write-Host ("[pause] Edit: " + (Join-Path $RunBase "reports/hypothesis_answers.md"))
    Write-Host "[pause] If you want to proceed with defaults: re-run with -AutoProceed (or tell the agent \"그냥 진행해줘\")."
    return $false
  }
  throw ("Hypothesis checkpoint failed (exit=" + $LASTEXITCODE + ")")
}

$stageArtifacts = @{
  "00P" = @("reports/stage_00P_report_payload.json", "reports/raw_file_profile.json", "reports/table_detection_report.md")
  "00" = @("reports/stage_00_report_payload.json", "reports/dataset_review.md")
  "01" = @("reports/stage_01_report_payload.json", "reports/env_check.md")
  "02" = @("reports/stage_02_report_payload.json", "reports/diagnosis_report.md")
  "02H" = @("reports/stage_02H_report_payload.json", "reports/hypothesis_registry.json", "reports/hypothesis_validation_plan.csv")
  "03" = @("reports/stage_03_report_payload.json", "data/processed/feature_manifest.json", "data/processed/feature_build_report.md")
  "04" = @("reports/stage_04_report_payload.json", "data/folds/sample15_fold_summary.json", "data/folds/sample15_fold_report.md")
  "05" = @("reports/stage_05_report_payload.json", "artifacts/models/model_registry.json", "artifacts/models/metrics.csv")
  "05H" = @("reports/stage_05H_report_payload.json", "reports/hypothesis_validation_results.json")
  "06" = @("reports/stage_06_report_payload.json", "submissions/submission.csv", "submissions/postprocess_choices.json")
  "07" = @("reports/pdf/analysis_report_integrated.pdf")
}

$stageOrder = @{
  "00P" = 0
  "00" = 1
  "01" = 2
  "02" = 3
  "02H" = 4
  "03" = 5
  "04" = 6
  "05" = 7
  "05H" = 8
  "06" = 9
  "07" = 10
}

function Resolve-RunBase {
  param(
    [string]$RepoRoot,
    [string]$ConfigPath,
    [string]$RunId
  )
  $cfg = Get-ManualConfig -ConfigPath $ConfigPath
  $outputRoot = $cfg.output_root
  if (-not $outputRoot) { $outputRoot = (Join-Path (Split-Path -Leaf $manualRoot) "runs") }
  $outPath = ""
  if ([System.IO.Path]::IsPathRooted([string]$outputRoot)) {
    $outPath = [string]$outputRoot
  } else {
    $outPath = (Join-Path $RepoRoot ([string]$outputRoot))
  }
  return (Join-Path $outPath $RunId)
}

function Stage-Completed {
  param(
    [string]$RunBase,
    [string]$Stage
  )
  if (-not $stageArtifacts.ContainsKey($Stage)) { return $false }
  if ($Stage -eq "02H" -and (Test-Path -LiteralPath (Join-Path $RunBase "reports/pending_hypothesis_checkpoint.json"))) {
    return $false
  }
  foreach ($rel in $stageArtifacts[$Stage]) {
    $p = Join-Path $RunBase $rel
    if (-not (Test-Path -LiteralPath $p)) { return $false }
  }
  return $true
}

function Stage-AtOrAfter {
  param(
    [string]$Stage,
    [string]$FromStage
  )
  if (-not $FromStage) { return $false }
  if (-not $stageOrder.ContainsKey($Stage) -or -not $stageOrder.ContainsKey($FromStage)) { return $false }
  return ([int]$stageOrder[$Stage] -ge [int]$stageOrder[$FromStage])
}

function Should-RunStage {
  param(
    [string]$RunBase,
    [string]$Stage,
    [switch]$Resume,
    [string]$FromStage
  )
  if (-not $Resume) { return $true }
  if (Stage-AtOrAfter -Stage $Stage -FromStage $FromStage) { return $true }
  return (-not (Stage-Completed -RunBase $RunBase -Stage $Stage))
}

$manualRoot = Resolve-ManualRoot
$repoRoot = Split-Path -Parent $manualRoot
$pythonExe = Resolve-Python -RepoRoot $repoRoot
$configPath = (Resolve-Path -LiteralPath $Config).Path
$configObject = Get-ManualConfig -ConfigPath $configPath
$runBase = Resolve-RunBase -RepoRoot $repoRoot -ConfigPath $configPath -RunId $RunId
$rawIntakeEnabled = Get-ConfigBool -ConfigObject $configObject -Section "raw_intake" -Key "enabled"

Push-Location $repoRoot
try {
  if ($rawIntakeEnabled) {
    if (Should-RunStage -RunBase $runBase -Stage "00P" -Resume:$Resume -FromStage $FromStage) {
      Run-Step -Name "00P raw intake" -PythonExe $pythonExe -StepArgs @(
        (Join-ManualPath "plugins/manual-00-raw-intake/scripts/raw_intake.py"),
        "--config", $configPath,
        "--run-id", $RunId
      )
    } else {
      Write-Host "[skip] 00P already completed"
    }
  }

  if (Should-RunStage -RunBase $runBase -Stage "00" -Resume:$Resume -FromStage $FromStage) {
    Run-Step -Name "00 data review" -PythonExe $pythonExe -StepArgs @(
      (Join-ManualPath "plugins/manual-00-data-reviewer/scripts/review_data.py"),
      "--config", $configPath,
      "--run-id", $RunId
    )
    Run-Step -Name "00 domain expert questionnaire" -PythonExe $pythonExe -StepArgs @(
      (Join-ManualPath "plugins/manual-domain-expert/scripts/generate_questionnaire.py"),
      "--config", $configPath,
      "--run-id", $RunId
    )
    if (-not $NoPdfReport) {
      Run-Step -Name "PDF 00" -PythonExe $pythonExe -StepArgs @((Join-ManualPath "plugins/manual-07-report-writer/scripts/write_reports.py"), "--config", $configPath, "--run-id", $RunId, "--stage", "00")
    }
  } else {
    Write-Host "[skip] 00 already completed"
  }

  if (Should-RunStage -RunBase $runBase -Stage "01" -Resume:$Resume -FromStage $FromStage) {
    $ok = Run-Checkpoint -StageBefore "01" -PythonExe $pythonExe -ConfigPath $configPath -RunId $RunId -RunBase $runBase -AutoProceed:$AutoProceed
    if (-not $ok) { return }
  }

  if (Should-RunStage -RunBase $runBase -Stage "01" -Resume:$Resume -FromStage $FromStage) {
    Run-Step -Name "01 env check" -PythonExe $pythonExe -StepArgs @(
      (Join-ManualPath "plugins/manual-01-env-checker/scripts/check_env.py"),
      "--config", $configPath,
      "--run-id", $RunId
    )
    if (-not $NoPdfReport) {
      Run-Step -Name "PDF 01" -PythonExe $pythonExe -StepArgs @((Join-ManualPath "plugins/manual-07-report-writer/scripts/write_reports.py"), "--config", $configPath, "--run-id", $RunId, "--stage", "01")
    }
  } else {
    Write-Host "[skip] 01 already completed"
  }

  if (Should-RunStage -RunBase $runBase -Stage "02" -Resume:$Resume -FromStage $FromStage) {
    Run-Step -Name "02 diagnostics" -PythonExe $pythonExe -StepArgs @(
      (Join-ManualPath "plugins/manual-02-profiler-diagnoser/scripts/diagnose_data.py"),
      "--config", $configPath,
      "--run-id", $RunId
    )
    if (-not $NoPdfReport) {
      Run-Step -Name "PDF 02" -PythonExe $pythonExe -StepArgs @((Join-ManualPath "plugins/manual-07-report-writer/scripts/write_reports.py"), "--config", $configPath, "--run-id", $RunId, "--stage", "02")
    }
  } else {
    Write-Host "[skip] 02 already completed"
  }

  if (Should-RunStage -RunBase $runBase -Stage "02H" -Resume:$Resume -FromStage $FromStage) {
    $ok = Run-HypothesisCheckpoint -PythonExe $pythonExe -ConfigPath $configPath -RunId $RunId -RunBase $runBase -AutoProceed:$AutoProceed
    if (-not $ok) { return }
    if (-not $NoPdfReport) {
      Run-Step -Name "PDF 02H" -PythonExe $pythonExe -StepArgs @((Join-ManualPath "plugins/manual-07-report-writer/scripts/write_reports.py"), "--config", $configPath, "--run-id", $RunId, "--stage", "02H")
    }
  } else {
    Write-Host "[skip] 02H already completed"
  }

  if (Should-RunStage -RunBase $runBase -Stage "03" -Resume:$Resume -FromStage $FromStage) {
    $ok = Run-Checkpoint -StageBefore "03" -PythonExe $pythonExe -ConfigPath $configPath -RunId $RunId -RunBase $runBase -AutoProceed:$AutoProceed
    if (-not $ok) { return }
  }

  $featureArgs = @(
    (Join-ManualPath "plugins/manual-03-feature-builder/scripts/build_features.py"),
    "--config", $configPath,
    "--run-id", $RunId
  )
  if ($Interactive) { $featureArgs += "--interactive" }
  if (Should-RunStage -RunBase $runBase -Stage "03" -Resume:$Resume -FromStage $FromStage) {
    Run-Step -Name "03 feature build" -PythonExe $pythonExe -StepArgs $featureArgs
    if (-not $NoPdfReport) {
      Run-Step -Name "PDF 03" -PythonExe $pythonExe -StepArgs @((Join-ManualPath "plugins/manual-07-report-writer/scripts/write_reports.py"), "--config", $configPath, "--run-id", $RunId, "--stage", "03")
    }
  } else {
    Write-Host "[skip] 03 already completed"
  }

  $foldArgs = @(
    (Join-ManualPath "plugins/manual-04-validation-splitter/scripts/make_folds.py"),
    "--config", $configPath,
    "--run-id", $RunId,
    "--seed", "$Seed"
  )
  if ($FullTrain) { $foldArgs += "--full-train" }
  if ($Interactive) { $foldArgs += "--interactive" }
  if (Should-RunStage -RunBase $runBase -Stage "04" -Resume:$Resume -FromStage $FromStage) {
    Run-Step -Name "04 validation folds" -PythonExe $pythonExe -StepArgs $foldArgs
    if (-not $NoPdfReport) {
      Run-Step -Name "PDF 04" -PythonExe $pythonExe -StepArgs @((Join-ManualPath "plugins/manual-07-report-writer/scripts/write_reports.py"), "--config", $configPath, "--run-id", $RunId, "--stage", "04")
    }
  } else {
    Write-Host "[skip] 04 already completed"
  }

  if (Should-RunStage -RunBase $runBase -Stage "05" -Resume:$Resume -FromStage $FromStage) {
    $ok = Run-Checkpoint -StageBefore "05" -PythonExe $pythonExe -ConfigPath $configPath -RunId $RunId -RunBase $runBase -AutoProceed:$AutoProceed
    if (-not $ok) { return }
  }

  $trainArgs = @(
    (Join-ManualPath "plugins/manual-05-model-trainer/scripts/train_model.py"),
    "--config", $configPath,
    "--run-id", $RunId,
    "--target-mode", $TargetMode,
    "--explain-models", $ExplainModels,
    "--tuning-trials", "$TuningTrials",
    "--seed", "$Seed",
    "--n-jobs", "$NJobs"
  )
  if ($FullTrain) { $trainArgs += "--full-train" }
  if ($MaxFolds -gt 0) { $trainArgs += @("--max-folds", "$MaxFolds") }
  if (Should-RunStage -RunBase $runBase -Stage "05" -Resume:$Resume -FromStage $FromStage) {
    Run-Step -Name "05 model train" -PythonExe $pythonExe -StepArgs $trainArgs
    if (-not $NoPdfReport) {
      Run-Step -Name "PDF 05" -PythonExe $pythonExe -StepArgs @((Join-ManualPath "plugins/manual-07-report-writer/scripts/write_reports.py"), "--config", $configPath, "--run-id", $RunId, "--stage", "05")
    }
  } else {
    Write-Host "[skip] 05 already completed"
  }

  if (Should-RunStage -RunBase $runBase -Stage "05H" -Resume:$Resume -FromStage $FromStage) {
    Run-Step -Name "05H hypothesis evaluation" -PythonExe $pythonExe -StepArgs @(
      (Join-ManualPath "plugins/manual-hypothesis-planner/scripts/hypothesis_planner.py"),
      "evaluate",
      "--config", $configPath,
      "--run-id", $RunId
    )
    if (-not $NoPdfReport) {
      Run-Step -Name "PDF 05H" -PythonExe $pythonExe -StepArgs @((Join-ManualPath "plugins/manual-07-report-writer/scripts/write_reports.py"), "--config", $configPath, "--run-id", $RunId, "--stage", "05H")
    }
  } else {
    Write-Host "[skip] 05H already completed"
  }

  $submitArgs = @(
    (Join-ManualPath "plugins/manual-06-submission-maker/scripts/make_submission.py"),
    "--config", $configPath,
    "--run-id", $RunId,
    "--ensemble-method", $EnsembleMethod,
    "--upper-clip", $UpperClip
  )
  if ($EnsembleMethod -eq "manual") {
    if (-not $ManualWeights) { throw "Manual ensemble requires -ManualWeights like model_a=0.7,model_b=0.3" }
    $submitArgs += @("--manual-weights", $ManualWeights)
  }
  if ($Interactive) { $submitArgs += "--interactive" }
  if (Should-RunStage -RunBase $runBase -Stage "06" -Resume:$Resume -FromStage $FromStage) {
    Run-Step -Name "06 submission" -PythonExe $pythonExe -StepArgs $submitArgs
    if (-not $NoPdfReport) {
      Run-Step -Name "PDF 06" -PythonExe $pythonExe -StepArgs @((Join-ManualPath "plugins/manual-07-report-writer/scripts/write_reports.py"), "--config", $configPath, "--run-id", $RunId, "--stage", "06")
    }
  } else {
    Write-Host "[skip] 06 already completed"
  }

  if (-not $NoPdfReport -and (Should-RunStage -RunBase $runBase -Stage "07" -Resume:$Resume -FromStage $FromStage)) {
    $ok = Run-Checkpoint -StageBefore "07" -PythonExe $pythonExe -ConfigPath $configPath -RunId $RunId -RunBase $runBase -AutoProceed:$AutoProceed
    if (-not $ok) { return }
    Run-Step -Name "PDF integrated" -PythonExe $pythonExe -StepArgs @((Join-ManualPath "plugins/manual-07-report-writer/scripts/write_reports.py"), "--config", $configPath, "--run-id", $RunId, "--stage", "integrated")
  }

  Write-Host ""
  Write-Host ("[done] Manual run: " + $runBase)
  Write-Host ("[done] Submission: " + (Join-Path $runBase "submissions/submission.csv"))
  Write-Host ("[done] PDFs: " + (Join-Path $runBase "reports/pdf"))
} finally {
  Pop-Location
}

