[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [int]$DiskNumber = -1,
    [switch]$ListDisks,
    [switch]$Force,
    [string]$UsbLabel = "",
    [string]$WorkingDirectory = "",
    [string]$ReleaseIsoUrl = "",
    [string]$WriterVariant = "",
    [string]$PresetName = "",
    [string]$PresetBase64 = "",
    [string]$InstallerLogUrl = "",
    [string]$InstallerLogToken = "",
    [string]$InstallerLogSessionId = ""
)

$ErrorActionPreference = "Stop"

$DefaultReleaseIsoUrl = "__BEAGLE_DEFAULT_RELEASE_ISO_URL__"
$DefaultWriterVariant = "__BEAGLE_DEFAULT_WRITER_VARIANT__"
$DefaultPresetName = "__BEAGLE_DEFAULT_PRESET_NAME__"
$DefaultPresetBase64 = "__BEAGLE_DEFAULT_PRESET_B64__"
$DefaultInstallerLogUrl = "__BEAGLE_DEFAULT_INSTALLER_LOG_URL__"
$DefaultInstallerLogToken = "__BEAGLE_DEFAULT_INSTALLER_LOG_TOKEN__"
$DefaultInstallerLogSessionId = "__BEAGLE_DEFAULT_INSTALLER_LOG_SESSION_ID__"
$script:BeagleInstallerStage = "init"

function Write-Step {
    param([string]$Message)
    Write-Host ("[Beagle OS] {0}" -f $Message)
}

function Send-InstallerLog {
    param(
        [string]$Event,
        [string]$Stage = $script:BeagleInstallerStage,
        [string]$Status = "info",
        [string]$Message = "",
        [hashtable]$Details = @{}
    )

    if ([string]::IsNullOrWhiteSpace($InstallerLogUrl) -or [string]::IsNullOrWhiteSpace($InstallerLogToken)) {
        return
    }

    try {
        $body = [ordered]@{
            session_id = $InstallerLogSessionId
            event = $Event
            stage = $Stage
            status = $Status
            message = $Message
            script = [IO.Path]::GetFileName($PSCommandPath)
            writer_variant = $WriterVariant
            details = $Details
        } | ConvertTo-Json -Depth 5
        Invoke-RestMethod `
            -Uri $InstallerLogUrl `
            -Method Post `
            -Headers @{ Authorization = ("Bearer {0}" -f $InstallerLogToken) } `
            -ContentType "application/json" `
            -Body $body `
            -TimeoutSec 5 | Out-Null
    } catch {
        # Installer logging must never block USB provisioning.
    }
}

function Resolve-WriterVariant {
    param(
        [string]$RequestedVariant,
        [string]$DefaultVariant
    )

    $candidate = [string]$RequestedVariant
    if ([string]::IsNullOrWhiteSpace($candidate)) {
        $candidate = [string]$DefaultVariant
    }
    if ([string]::IsNullOrWhiteSpace($candidate)) {
        $scriptName = [IO.Path]::GetFileName($PSCommandPath)
        if ($scriptName -match 'live-usb') {
            $candidate = 'live'
        } else {
            $candidate = 'installer'
        }
    }
    $normalized = $candidate.Trim().ToLowerInvariant()
    if ($normalized -notin @('installer', 'live')) {
        throw "Unsupported WriterVariant: $candidate"
    }
    return $normalized
}

if ([string]::IsNullOrWhiteSpace($ReleaseIsoUrl)) {
    $ReleaseIsoUrl = $DefaultReleaseIsoUrl
}
if ([string]::IsNullOrWhiteSpace($PresetName)) {
    $PresetName = $DefaultPresetName
}
if ([string]::IsNullOrWhiteSpace($PresetBase64)) {
    $PresetBase64 = $DefaultPresetBase64
}
if ([string]::IsNullOrWhiteSpace($InstallerLogUrl)) {
    $InstallerLogUrl = $DefaultInstallerLogUrl
}
if ([string]::IsNullOrWhiteSpace($InstallerLogToken)) {
    $InstallerLogToken = $DefaultInstallerLogToken
}
if ([string]::IsNullOrWhiteSpace($InstallerLogSessionId)) {
    $InstallerLogSessionId = $DefaultInstallerLogSessionId
}
if ($InstallerLogUrl -like "__BEAGLE_DEFAULT_*") {
    $InstallerLogUrl = ""
}
if ($InstallerLogToken -like "__BEAGLE_DEFAULT_*") {
    $InstallerLogToken = ""
}
if ($InstallerLogSessionId -like "__BEAGLE_DEFAULT_*") {
    $InstallerLogSessionId = ""
}
$WriterVariant = Resolve-WriterVariant -RequestedVariant $WriterVariant -DefaultVariant $DefaultWriterVariant
if ([string]::IsNullOrWhiteSpace($UsbLabel)) {
    $UsbLabel = if ($WriterVariant -eq "live") { "BEAGLELIVE" } else { "BEAGLEOS" }
}

trap {
    Send-InstallerLog -Event "script_failed" -Stage $script:BeagleInstallerStage -Status "error" -Message $_.Exception.Message
    break
}

Send-InstallerLog -Event "script_started" -Stage "init" -Status "ok" -Message "Windows USB writer script started"

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Administratorrechte sind erforderlich. PowerShell als Administrator starten."
    }
}

function Get-UsbDiskCandidates {
    $disks = Get-Disk | Where-Object {
        $_.Number -ge 0 -and
        $_.Size -gt 4GB -and
        $_.BusType -in @("USB", "SD", "MMC", "Unknown")
    } | Sort-Object Number
    return @($disks)
}

function Show-DiskTable {
    $table = Get-UsbDiskCandidates | Select-Object Number, FriendlyName, BusType, PartitionStyle,
        @{ Name = "SizeGB"; Expression = { [Math]::Round($_.Size / 1GB, 1) } },
        IsBoot, IsSystem, IsReadOnly, OperationalStatus
    if (-not $table) {
        Write-Host "Keine passenden USB-Zielmedien gefunden."
        return
    }
    $table | Format-Table -AutoSize | Out-Host
}

function Resolve-WorkingDirectory {
    if (-not [string]::IsNullOrWhiteSpace($WorkingDirectory)) {
        New-Item -ItemType Directory -Path $WorkingDirectory -Force | Out-Null
        return (Resolve-Path -LiteralPath $WorkingDirectory).Path
    }
    $root = Join-Path $env:TEMP "beagle-usb"
    New-Item -ItemType Directory -Path $root -Force | Out-Null
    $leaf = "run-{0}" -f ([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())
    $path = Join-Path $root $leaf
    New-Item -ItemType Directory -Path $path -Force | Out-Null
    return $path
}

function Download-Iso {
    param(
        [string]$Url,
        [string]$TargetPath
    )
    $script:BeagleInstallerStage = "iso_download"
    if (Test-Path -LiteralPath $TargetPath) {
        $existingFile = Get-Item -LiteralPath $TargetPath -ErrorAction SilentlyContinue
        if ($existingFile -and $existingFile.Length -gt 0) {
            Write-Step ("Verwende bereits heruntergeladenes ISO: {0}" -f $TargetPath)
            Send-InstallerLog -Event "iso_download_cached" -Stage $script:BeagleInstallerStage -Status "ok" -Message $TargetPath
            return
        }
    }
    Write-Step ("Lade Beagle OS Installer ISO von {0} ..." -f $Url)
    Send-InstallerLog -Event "iso_download_started" -Stage $script:BeagleInstallerStage -Status "running" -Message $Url
    try {
        Invoke-WebRequest -Uri $Url -OutFile $TargetPath -UseBasicParsing
        Send-InstallerLog -Event "iso_download_completed" -Stage $script:BeagleInstallerStage -Status "ok" -Message $TargetPath
    } catch {
        throw "ISO-Download fehlgeschlagen: $($_.Exception.Message)"
    }
}

function Get-MountedIsoLetter {
    param([string]$ImagePath)
    $mount = Mount-DiskImage -ImagePath $ImagePath -StorageType ISO -PassThru
    Start-Sleep -Seconds 2
    $volume = $mount | Get-Volume | Select-Object -First 1
    if (-not $volume -or [string]::IsNullOrWhiteSpace($volume.DriveLetter)) {
        throw "ISO konnte gemountet werden, aber kein Laufwerksbuchstabe wurde erkannt."
    }
    return @{
        DiskImage = $mount
        DriveLetter = ("{0}:" -f $volume.DriveLetter)
    }
}

function Invoke-DiskPartScript {
    param([string[]]$Commands)

    $scriptPath = Join-Path $env:TEMP ("beagle-diskpart-{0}.txt" -f ([Guid]::NewGuid().ToString("N")))
    try {
        [IO.File]::WriteAllLines($scriptPath, $Commands, [Text.Encoding]::ASCII)
        $output = & diskpart /s $scriptPath 2>&1
        $exitCode = $LASTEXITCODE
        if ($exitCode -ne 0) {
            throw "diskpart ist fehlgeschlagen (ExitCode $exitCode): $($output -join '; ')"
        }
        return $output
    } finally {
        Remove-Item -LiteralPath $scriptPath -Force -ErrorAction SilentlyContinue
    }
}

function Get-AvailableDriveLetter {
    $used = @(
        Get-Volume |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_.DriveLetter) } |
            ForEach-Object { ([string]$_.DriveLetter).ToUpperInvariant() }
    )
    foreach ($candidate in @("U", "V", "W", "X", "Y", "Z", "T", "S", "R", "Q", "P")) {
        if ($used -notcontains $candidate) {
            return $candidate
        }
    }
    throw "Kein freier Laufwerksbuchstabe fuer den USB-Datentraeger gefunden."
}

function Prepare-UsbDisk {
    param(
        [int]$TargetDiskNumber,
        [string]$Label
    )

    $disk = Get-Disk -Number $TargetDiskNumber
    if ($disk.IsBoot -or $disk.IsSystem) {
        throw "Der gewaehlte Datentraeger ist ein Boot-/Systemlaufwerk und wird aus Sicherheitsgruenden nicht beschrieben."
    }
    if ($disk.Size -lt 4GB) {
        throw "Der gewaehlte Datentraeger ist zu klein."
    }

    $script:BeagleInstallerStage = "usb_prepare"
    Write-Step ("Bereite USB-Datentraeger {0} vor ..." -f $TargetDiskNumber)
    Send-InstallerLog -Event "usb_prepare_started" -Stage $script:BeagleInstallerStage -Status "running" -Message ("disk={0}" -f $TargetDiskNumber)
    if (-not $Force) {
        $confirmation = Read-Host ("Alle Daten auf Datentraeger {0} werden geloescht. Zum Fortfahren YES eingeben" -f $TargetDiskNumber)
        if ($confirmation -ne "YES") {
            throw "Abgebrochen."
        }
    }

    $driveLetter = Get-AvailableDriveLetter
    Invoke-DiskPartScript @(
        "select disk $TargetDiskNumber",
        "attributes disk clear readonly",
        "online disk noerr",
        "clean",
        "convert gpt",
        "create partition primary",
        "format fs=fat32 quick label=$Label",
        "assign letter=$driveLetter"
    ) | Out-Null

    Start-Sleep -Seconds 2
    $volume = Get-Volume -DriveLetter $driveLetter -ErrorAction SilentlyContinue
    if (-not $volume) {
        throw "USB-Datentraeger wurde vorbereitet, aber Laufwerk $driveLetter`: konnte nicht bestaetigt werden."
    }
    Send-InstallerLog -Event "usb_prepare_completed" -Stage $script:BeagleInstallerStage -Status "ok" -Message ("drive={0}:" -f $driveLetter)
    return ("{0}:" -f $driveLetter)
}

function Copy-Tree {
    param(
        [string]$SourcePath,
        [string]$TargetPath
    )
    if (-not (Test-Path -LiteralPath $SourcePath)) {
        return
    }
    New-Item -ItemType Directory -Path $TargetPath -Force | Out-Null
    $null = & robocopy $SourcePath $TargetPath /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP
    $code = $LASTEXITCODE
    if ($code -ge 8) {
        throw "robocopy ist fehlgeschlagen (ExitCode $code)."
    }
}

function Copy-IsoDirectory {
    param(
        [string]$SourceDrive,
        [string]$RelativePath,
        [string]$TargetPath
    )
    $sourcePath = Join-Path $SourceDrive $RelativePath
    Copy-Tree -SourcePath $sourcePath -TargetPath $TargetPath
}

function Copy-IsoFile {
    param(
        [string]$SourceDrive,
        [string]$RelativePath,
        [string]$TargetPath
    )
    $sourcePath = Join-Path $SourceDrive $RelativePath
    if (-not (Test-Path -LiteralPath $sourcePath)) {
        return
    }
    $parent = Split-Path -Parent $TargetPath
    if (-not [string]::IsNullOrWhiteSpace($parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    Copy-Item -LiteralPath $sourcePath -Destination $TargetPath -Force
}

function Write-PresetFiles {
    param(
        [string]$TargetDrive,
        [string]$PresetBase64Value,
        [string]$Variant
    )
    if ([string]::IsNullOrWhiteSpace($PresetBase64Value)) {
        return
    }
    $bytes = [Convert]::FromBase64String($PresetBase64Value)
    $presetDir = Join-Path $TargetDrive "pve-thin-client"
    New-Item -ItemType Directory -Path $presetDir -Force | Out-Null
    [IO.File]::WriteAllBytes((Join-Path $presetDir "preset.env"), $bytes)

    $secondaryPresetPath = if ($Variant -eq "live") {
        Join-Path $TargetDrive "live\preset.env"
    } else {
        Join-Path $TargetDrive "pve-thin-client\live\preset.env"
    }
    $secondaryDir = Split-Path -Parent $secondaryPresetPath
    New-Item -ItemType Directory -Path $secondaryDir -Force | Out-Null
    [IO.File]::WriteAllBytes($secondaryPresetPath, $bytes)
}

function Parse-PresetEnv {
    param([string]$PresetPath)

    $result = @{}
    foreach ($rawLine in Get-Content -LiteralPath $PresetPath -ErrorAction Stop) {
        $line = [string]$rawLine
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }
        $trimmed = $line.Trim()
        if ($trimmed.StartsWith("#")) {
            continue
        }
        $index = $trimmed.IndexOf("=")
        if ($index -lt 1) {
            continue
        }
        $key = $trimmed.Substring(0, $index).Trim()
        $value = $trimmed.Substring($index + 1).Trim()
        if ($value.Length -ge 2 -and $value.StartsWith("'") -and $value.EndsWith("'")) {
            $value = $value.Substring(1, $value.Length - 2)
            $value = $value.Replace("'\"'\"'", "'")
        } elseif ($value.Length -ge 2 -and $value.StartsWith('"') -and $value.EndsWith('"')) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        $result[$key] = $value
    }
    return $result
}

function Get-PresetValue {
    param(
        [hashtable]$Preset,
        [string]$Key,
        [string]$Default = ""
    )
    if ($Preset.ContainsKey($Key) -and -not [string]::IsNullOrWhiteSpace([string]$Preset[$Key])) {
        return [string]$Preset[$Key]
    }
    return [string]$Default
}

function Write-LiveRuntimeState {
    param(
        [string]$TargetDrive,
        [string]$PresetBase64Value
    )

    if ([string]::IsNullOrWhiteSpace($PresetBase64Value)) {
        throw "Live USB creation requires an embedded VM preset."
    }

    $tempPreset = Join-Path $env:TEMP ("beagle-preset-{0}.env" -f ([Guid]::NewGuid().ToString("N")))
    try {
        [IO.File]::WriteAllBytes($tempPreset, [Convert]::FromBase64String($PresetBase64Value))
        $preset = Parse-PresetEnv -PresetPath $tempPreset
        $stateDir = Join-Path $TargetDrive "pve-thin-client\state"
        New-Item -ItemType Directory -Path $stateDir -Force | Out-Null

        $mode = Get-PresetValue -Preset $preset -Key "PVE_THIN_CLIENT_PRESET_DEFAULT_MODE" -Default "BEAGLE_STREAM_CLIENT"
        if ([string]::IsNullOrWhiteSpace($mode) -and -not [string]::IsNullOrWhiteSpace((Get-PresetValue -Preset $preset -Key "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_HOST"))) {
            $mode = "BEAGLE_STREAM_CLIENT"
        }
        if ($mode -ne "BEAGLE_STREAM_CLIENT") {
            throw "Live USB preset does not define a supported default mode."
        }

        $thinclientConf = @(
            '# pve-thin-client runtime configuration'
            ('PVE_THIN_CLIENT_MODE="{0}"' -f $mode)
            ('PVE_THIN_CLIENT_RUNTIME_USER="thinclient"' )
            ('PVE_THIN_CLIENT_AUTOSTART="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_AUTOSTART" "1"))
            ('PVE_THIN_CLIENT_PROFILE_NAME="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_PROFILE_NAME" "default"))
            ('PVE_THIN_CLIENT_HOSTNAME="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_HOSTNAME_VALUE" "beagle-live"))
            ('PVE_THIN_CLIENT_CONNECTION_METHOD="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_CONNECTION_METHOD" "direct"))
            ('PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_HOST="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_HOST"))
            ('PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_LOCAL_HOST="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_LOCAL_HOST"))
            ('PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PORT="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_PORT"))
            ('PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_APP="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_APP" "Desktop"))
            ('PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_BIN="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_BIN" "beagle-stream-client"))
            ('PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_RESOLUTION="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_RESOLUTION" "auto"))
            ('PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_FPS="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_FPS" "60"))
            ('PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_BITRATE="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_BITRATE" "20000"))
            ('PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_VIDEO_CODEC="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_VIDEO_CODEC" "H.264"))
            ('PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_VIDEO_DECODER="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_VIDEO_DECODER" "auto"))
            ('PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUDIO_CONFIG="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_AUDIO_CONFIG" "stereo"))
            ('PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_ABSOLUTE_MOUSE="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_ABSOLUTE_MOUSE" "1"))
            ('PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_QUIT_AFTER="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_QUIT_AFTER" "0"))
            ('PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_API_URL="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_SERVER_API_URL"))
            ('PVE_THIN_CLIENT_BEAGLE_SCHEME="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_SCHEME" "https"))
            ('PVE_THIN_CLIENT_BEAGLE_HOST="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_HOST"))
            ('PVE_THIN_CLIENT_BEAGLE_PORT="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_PORT" "8006"))
            ('PVE_THIN_CLIENT_BEAGLE_NODE="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_NODE"))
            ('PVE_THIN_CLIENT_BEAGLE_VMID="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_VMID"))
            ('PVE_THIN_CLIENT_BEAGLE_REALM="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_REALM" "pam"))
            ('PVE_THIN_CLIENT_BEAGLE_VERIFY_TLS="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_VERIFY_TLS" "1"))
            ('PVE_THIN_CLIENT_BEAGLE_MANAGER_URL="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_MANAGER_URL"))
            ('PVE_THIN_CLIENT_BEAGLE_MANAGER_PINNED_PUBKEY="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_MANAGER_PINNED_PUBKEY"))
            ('PVE_THIN_CLIENT_BEAGLE_ENROLLMENT_URL="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_ENROLLMENT_URL"))
            ('PVE_THIN_CLIENT_BEAGLE_UPDATE_ENABLED="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_UPDATE_ENABLED" "1"))
            ('PVE_THIN_CLIENT_BEAGLE_UPDATE_CHANNEL="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_UPDATE_CHANNEL" "stable"))
            ('PVE_THIN_CLIENT_BEAGLE_UPDATE_BEHAVIOR="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_UPDATE_BEHAVIOR" "prompt"))
            ('PVE_THIN_CLIENT_BEAGLE_UPDATE_FEED_URL="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_UPDATE_FEED_URL"))
            ('PVE_THIN_CLIENT_BEAGLE_UPDATE_VERSION_PIN="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_UPDATE_VERSION_PIN"))
            ('PVE_THIN_CLIENT_BEAGLE_EGRESS_MODE="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_MODE" "full"))
            ('PVE_THIN_CLIENT_BEAGLE_EGRESS_TYPE="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_TYPE" "wireguard"))
            ('PVE_THIN_CLIENT_BEAGLE_EGRESS_INTERFACE="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_INTERFACE" "wg-beagle"))
            ('PVE_THIN_CLIENT_BEAGLE_EGRESS_DOMAINS="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_DOMAINS"))
            ('PVE_THIN_CLIENT_BEAGLE_EGRESS_RESOLVERS="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_RESOLVERS"))
            ('PVE_THIN_CLIENT_BEAGLE_EGRESS_ALLOWED_IPS="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_ALLOWED_IPS"))
            ('PVE_THIN_CLIENT_BEAGLE_EGRESS_WG_ADDRESS="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_ADDRESS"))
            ('PVE_THIN_CLIENT_BEAGLE_EGRESS_WG_DNS="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_DNS"))
            ('PVE_THIN_CLIENT_BEAGLE_EGRESS_WG_PUBLIC_KEY="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_PUBLIC_KEY"))
            ('PVE_THIN_CLIENT_BEAGLE_EGRESS_WG_ENDPOINT="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_ENDPOINT"))
            ('PVE_THIN_CLIENT_BEAGLE_EGRESS_WG_PERSISTENT_KEEPALIVE="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_PERSISTENT_KEEPALIVE" "25"))
            ('PVE_THIN_CLIENT_IDENTITY_HOSTNAME="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_IDENTITY_HOSTNAME"))
            ('PVE_THIN_CLIENT_IDENTITY_TIMEZONE="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_IDENTITY_TIMEZONE"))
            ('PVE_THIN_CLIENT_IDENTITY_LOCALE="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_IDENTITY_LOCALE"))
            ('PVE_THIN_CLIENT_IDENTITY_KEYMAP="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_IDENTITY_KEYMAP"))
            ('PVE_THIN_CLIENT_IDENTITY_CHROME_PROFILE="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_IDENTITY_CHROME_PROFILE" "default"))
            ('PVE_THIN_CLIENT_BEAGLE_USB_ENABLED="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_USB_ENABLED"))
            ('PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_HOST="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_USB_TUNNEL_HOST"))
            ('PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_USER="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_USB_TUNNEL_USER"))
            ('PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_PORT="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_USB_TUNNEL_PORT"))
            ('PVE_THIN_CLIENT_BEAGLE_USB_ATTACH_HOST="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_USB_ATTACH_HOST"))
            ('PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_PRIVATE_KEY_FILE=""')
            ('PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_KNOWN_HOSTS_FILE=""')
        ) -join "`n"

        $networkEnv = @(
            ('PVE_THIN_CLIENT_NETWORK_MODE="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_NETWORK_MODE" "dhcp"))
            ('PVE_THIN_CLIENT_NETWORK_INTERFACE="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_NETWORK_INTERFACE" "eth0"))
            ('PVE_THIN_CLIENT_NETWORK_STATIC_ADDRESS="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_NETWORK_STATIC_ADDRESS"))
            ('PVE_THIN_CLIENT_NETWORK_STATIC_PREFIX="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_NETWORK_STATIC_PREFIX" "24"))
            ('PVE_THIN_CLIENT_NETWORK_GATEWAY="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_NETWORK_GATEWAY"))
            ('PVE_THIN_CLIENT_NETWORK_DNS_SERVERS="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_NETWORK_DNS_SERVERS" "1.1.1.1 8.8.8.8"))
        ) -join "`n"

        $credentialsEnv = @(
            ('PVE_THIN_CLIENT_CONNECTION_USERNAME="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_USERNAME"))
            ('PVE_THIN_CLIENT_CONNECTION_PASSWORD="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_PASSWORD"))
            ('PVE_THIN_CLIENT_CONNECTION_TOKEN="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_TOKEN"))
            ('PVE_THIN_CLIENT_BEAGLE_MANAGER_TOKEN="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_MANAGER_TOKEN"))
            ('PVE_THIN_CLIENT_BEAGLE_ENROLLMENT_TOKEN="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_ENROLLMENT_TOKEN"))
            ('PVE_THIN_CLIENT_BEAGLE_EGRESS_WG_PRIVATE_KEY="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_PRIVATE_KEY"))
            ('PVE_THIN_CLIENT_BEAGLE_EGRESS_WG_PRESHARED_KEY="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_PRESHARED_KEY"))
            ('PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_USERNAME="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_SERVER_USERNAME"))
            ('PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_PASSWORD="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_SERVER_PASSWORD"))
            ('PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_PIN="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_SERVER_PIN"))
            ('PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_PINNED_PUBKEY="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_SERVER_PINNED_PUBKEY"))
            ('PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_NAME="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_SERVER_NAME"))
            ('PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_STREAM_PORT="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_SERVER_STREAM_PORT"))
            ('PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_UNIQUEID="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_SERVER_UNIQUEID"))
            ('PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_CERT_B64="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_SERVER_CERT_B64"))
        ) -join "`n"

        $localAuthEnv = ('PVE_THIN_CLIENT_RUNTIME_PASSWORD="{0}"' -f (Get-PresetValue $preset "PVE_THIN_CLIENT_PRESET_THINCLIENT_PASSWORD"))

        [IO.File]::WriteAllText((Join-Path $stateDir "thinclient.conf"), $thinclientConf + "`n", [Text.Encoding]::UTF8)
        [IO.File]::WriteAllText((Join-Path $stateDir "network.env"), $networkEnv + "`n", [Text.Encoding]::UTF8)
        [IO.File]::WriteAllText((Join-Path $stateDir "credentials.env"), $credentialsEnv + "`n", [Text.Encoding]::UTF8)
        [IO.File]::WriteAllText((Join-Path $stateDir "local-auth.env"), $localAuthEnv + "`n", [Text.Encoding]::UTF8)
    } finally {
        Remove-Item -LiteralPath $tempPreset -Force -ErrorAction SilentlyContinue
    }
}

function Write-GrubConfig {
    param(
        [string]$TargetDrive,
        [string]$Variant,
        [string]$PresetBase64Value
    )

    $grubDir = Join-Path $TargetDrive "boot\grub"
    New-Item -ItemType Directory -Path $grubDir -Force | Out-Null

    if ($Variant -eq "live") {
        $hostname = "beagle-live"
        if (-not [string]::IsNullOrWhiteSpace($PresetBase64Value)) {
            $tempPreset = Join-Path $env:TEMP ("beagle-preset-grub-{0}.env" -f ([Guid]::NewGuid().ToString("N")))
            try {
                [IO.File]::WriteAllBytes($tempPreset, [Convert]::FromBase64String($PresetBase64Value))
                $preset = Parse-PresetEnv -PresetPath $tempPreset
                $hostname = Get-PresetValue -Preset $preset -Key "PVE_THIN_CLIENT_PRESET_HOSTNAME_VALUE" -Default "beagle-live"
            } finally {
                Remove-Item -LiteralPath $tempPreset -Force -ErrorAction SilentlyContinue
            }
        }
        $content = @"
insmod part_gpt
insmod fat
terminal_output console
set default=0
set timeout=5

menuentry 'Beagle OS Live' {
  linux /live/vmlinuz boot=live components username=thinclient hostname=$hostname live-media-path=/live live-media-timeout=10 ignore_uuid ip=dhcp quiet splash loglevel=3 systemd.show_status=0 systemd.gpt_auto=0 vt.global_cursor_default=0 console=tty0 console=ttyS0,115200n8 plymouth.ignore-serial-consoles pve_thin_client.mode=runtime
  initrd /live/initrd.img
}

menuentry 'Beagle OS Live (safe mode)' {
  linux /live/vmlinuz boot=live components username=thinclient hostname=$hostname live-media-path=/live live-media-timeout=10 ignore_uuid ip=dhcp loglevel=7 systemd.show_status=1 systemd.gpt_auto=0 vt.global_cursor_default=0 console=tty0 console=ttyS0,115200n8 plymouth.enable=0 nomodeset irqpoll pci=nomsi noapic pve_thin_client.mode=runtime
  initrd /live/initrd.img
}

menuentry 'Beagle OS Live (legacy IRQ mode)' {
  linux /live/vmlinuz boot=live components username=thinclient hostname=$hostname live-media-path=/live live-media-timeout=10 ignore_uuid ip=dhcp loglevel=7 systemd.show_status=1 systemd.gpt_auto=0 vt.global_cursor_default=0 console=tty0 console=ttyS0,115200n8 plymouth.enable=0 nomodeset irqpoll noapic nolapic pve_thin_client.mode=runtime
  initrd /live/initrd.img
}
"@
    } else {
        $timeout = if ([string]::IsNullOrWhiteSpace($PresetBase64Value) -and [string]::IsNullOrWhiteSpace($PresetName)) { "5" } else { "0" }
        $content = @"
terminal_output console
set default=0
set timeout=$timeout
set gfxpayload=text

menuentry 'Beagle OS Installer' {
  linux /pve-thin-client/live/vmlinuz boot=live components username=thinclient hostname=beagle-installer live-media-path=/pve-thin-client/live live-media-timeout=10 ip=dhcp console=tty0 console=ttyS0,115200n8 systemd.gpt_auto=0 plymouth.ignore-serial-consoles systemd.unit=multi-user.target systemd.mask=pve-thin-client-installer-gui.service systemd.mask=pve-thin-client-runtime.service pve_thin_client.mode=installer pve_thin_client.installer_ui=text pve_thin_client.no_x11=1
  initrd /pve-thin-client/live/initrd.img
}

menuentry 'Beagle OS Installer (compatibility mode)' {
  linux /pve-thin-client/live/vmlinuz boot=live components username=thinclient hostname=beagle-installer live-media-path=/pve-thin-client/live live-media-timeout=10 ip=dhcp console=tty0 console=ttyS0,115200n8 loglevel=7 systemd.show_status=1 systemd.gpt_auto=0 plymouth.enable=0 nomodeset irqpoll pci=nomsi noapic systemd.unit=multi-user.target systemd.mask=pve-thin-client-installer-gui.service systemd.mask=pve-thin-client-runtime.service pve_thin_client.mode=installer pve_thin_client.installer_ui=text pve_thin_client.no_x11=1
  initrd /pve-thin-client/live/initrd.img
}

menuentry 'Beagle OS Installer (legacy IRQ mode)' {
  linux /pve-thin-client/live/vmlinuz boot=live components username=thinclient hostname=beagle-installer live-media-path=/pve-thin-client/live live-media-timeout=10 ip=dhcp console=tty0 console=ttyS0,115200n8 loglevel=7 systemd.show_status=1 systemd.gpt_auto=0 plymouth.enable=0 nomodeset irqpoll noapic nolapic systemd.unit=multi-user.target systemd.mask=pve-thin-client-installer-gui.service systemd.mask=pve-thin-client-runtime.service pve_thin_client.mode=installer pve_thin_client.installer_ui=text pve_thin_client.no_x11=1
  initrd /pve-thin-client/live/initrd.img
}

menuentry 'Boot from local disk' {
  exit
}
"@
    }

    [IO.File]::WriteAllText((Join-Path $grubDir "grub.cfg"), $content, [Text.Encoding]::UTF8)
}

function Build-InstallerUsb {
    param(
        [string]$SourceDrive,
        [string]$TargetDrive,
        [string]$Variant,
        [string]$PresetBase64Value
    )

    $script:BeagleInstallerStage = "usb_write"
    Write-Step ("Erstelle {0}-USB-Inhalte auf {1} ..." -f $Variant, $TargetDrive)
    Send-InstallerLog -Event "usb_write_started" -Stage $script:BeagleInstallerStage -Status "running" -Message ("target={0}" -f $TargetDrive)
    Copy-IsoDirectory -SourceDrive $SourceDrive -RelativePath "EFI" -TargetPath (Join-Path $TargetDrive "EFI")
    Copy-IsoDirectory -SourceDrive $SourceDrive -RelativePath "boot" -TargetPath (Join-Path $TargetDrive "boot")

    if ($Variant -eq "live") {
        Copy-IsoDirectory -SourceDrive $SourceDrive -RelativePath "live" -TargetPath (Join-Path $TargetDrive "live")
        Write-PresetFiles -TargetDrive $TargetDrive -PresetBase64Value $PresetBase64Value -Variant $Variant
        Write-LiveRuntimeState -TargetDrive $TargetDrive -PresetBase64Value $PresetBase64Value
    } else {
        Copy-IsoDirectory -SourceDrive $SourceDrive -RelativePath "live" -TargetPath (Join-Path $TargetDrive "pve-thin-client\live")
        Copy-IsoFile -SourceDrive $SourceDrive -RelativePath "start-installer-menu.sh" -TargetPath (Join-Path $TargetDrive "start-installer-menu.sh")
        Write-PresetFiles -TargetDrive $TargetDrive -PresetBase64Value $PresetBase64Value -Variant $Variant
    }

    Write-GrubConfig -TargetDrive $TargetDrive -Variant $Variant -PresetBase64Value $PresetBase64Value
    Send-InstallerLog -Event "usb_write_completed" -Stage $script:BeagleInstallerStage -Status "ok" -Message ("target={0}" -f $TargetDrive)
}

function Write-Manifest {
    param(
        [string]$TargetDrive,
        [string]$IsoUrl,
        [string]$ProfileName,
        [string]$Variant
    )
    $manifest = [ordered]@{
        version = "windows-builder"
        generated_at = [DateTime]::UtcNow.ToString("o")
        iso_url = $IsoUrl
        preset_name = $ProfileName
        platform = "windows"
        writer_variant = $Variant
        boot_mode = "uefi"
    } | ConvertTo-Json -Depth 4
    [IO.File]::WriteAllText((Join-Path $TargetDrive ".beagle-windows-usb.json"), $manifest, [Text.Encoding]::UTF8)
}

$script:BeagleInstallerStage = "privilege"
Assert-Administrator

if ($ListDisks) {
    $script:BeagleInstallerStage = "device_listing"
    Send-InstallerLog -Event "device_listing_started" -Stage $script:BeagleInstallerStage -Status "running" -Message "listing candidate USB disks"
    Show-DiskTable
    Send-InstallerLog -Event "device_listing_completed" -Stage $script:BeagleInstallerStage -Status "ok" -Message "candidate USB disks listed"
    exit 0
}

if ([string]::IsNullOrWhiteSpace($ReleaseIsoUrl)) {
    throw "Es wurde keine ISO-URL konfiguriert."
}

$candidates = Get-UsbDiskCandidates
if (-not $candidates) {
    throw "Keine beschreibbaren USB-Datentraeger gefunden."
}

if ($DiskNumber -lt 0) {
    $script:BeagleInstallerStage = "device_selection"
    Show-DiskTable
    $selection = Read-Host "Datentraegernummer eingeben"
    if (-not [int]::TryParse($selection, [ref]$DiskNumber)) {
        throw "Ungueltige Datentraegernummer."
    }
}

$workingRoot = Resolve-WorkingDirectory
$isoPath = Join-Path $workingRoot "beagle-os-installer-amd64.iso"

Download-Iso -Url $ReleaseIsoUrl -TargetPath $isoPath
$mountedIso = $null
try {
    $script:BeagleInstallerStage = "iso_mount"
    $mountedIso = Get-MountedIsoLetter -ImagePath $isoPath
    $usbDrive = Prepare-UsbDisk -TargetDiskNumber $DiskNumber -Label $UsbLabel
    Build-InstallerUsb -SourceDrive $mountedIso.DriveLetter -TargetDrive $usbDrive -Variant $WriterVariant -PresetBase64Value $PresetBase64
    Write-Manifest -TargetDrive $usbDrive -IsoUrl $ReleaseIsoUrl -ProfileName $PresetName -Variant $WriterVariant
    $script:BeagleInstallerStage = "complete"
    Write-Step ("Windows {0}-USB fertig: Datentraeger {1} ({2})" -f $WriterVariant, $DiskNumber, $usbDrive)
    Send-InstallerLog -Event "script_completed" -Stage $script:BeagleInstallerStage -Status "ok" -Message ("disk={0}; drive={1}" -f $DiskNumber, $usbDrive)
    if ($WriterVariant -eq "live") {
        Write-Step "Hinweis: Das Windows-Skript erstellt ein UEFI-bootfaehiges Live-Medium."
    }
} finally {
    if ($mountedIso -and $mountedIso.DiskImage) {
        Dismount-DiskImage -ImagePath $isoPath -ErrorAction SilentlyContinue | Out-Null
    }
}
