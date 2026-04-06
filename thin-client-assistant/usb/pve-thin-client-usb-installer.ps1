[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [int]$DiskNumber = -1,
    [switch]$ListDisks,
    [switch]$Force,
    [string]$UsbLabel = "BEAGLEOS",
    [string]$WorkingDirectory = "",
    [string]$ReleaseIsoUrl = "",
    [string]$PresetName = "",
    [string]$PresetBase64 = ""
)

$ErrorActionPreference = "Stop"

$DefaultReleaseIsoUrl = "__BEAGLE_DEFAULT_RELEASE_ISO_URL__"
$DefaultPresetName = "__BEAGLE_DEFAULT_PRESET_NAME__"
$DefaultPresetBase64 = "__BEAGLE_DEFAULT_PRESET_B64__"

if ([string]::IsNullOrWhiteSpace($ReleaseIsoUrl)) {
    $ReleaseIsoUrl = $DefaultReleaseIsoUrl
}
if ([string]::IsNullOrWhiteSpace($PresetName)) {
    $PresetName = $DefaultPresetName
}
if ([string]::IsNullOrWhiteSpace($PresetBase64)) {
    $PresetBase64 = $DefaultPresetBase64
}

function Write-Step {
    param([string]$Message)
    Write-Host ("[Beagle OS] {0}" -f $Message)
}

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
    Write-Step ("Lade Beagle OS Installer ISO von {0} ..." -f $Url)
    try {
        Invoke-WebRequest -Uri $Url -OutFile $TargetPath -UseBasicParsing
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

    Write-Step ("Bereite USB-Datentraeger {0} vor ..." -f $TargetDiskNumber)
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
    return ("{0}:" -f $driveLetter)
}

function Copy-IsoContents {
    param(
        [string]$SourceDrive,
        [string]$TargetDrive
    )
    Write-Step ("Kopiere Installer-Inhalte auf {0} ..." -f $TargetDrive)
    $source = "{0}\" -f $SourceDrive.TrimEnd("\")
    $target = "{0}\" -f $TargetDrive.TrimEnd("\")
    $null = & robocopy $source $target /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP
    $code = $LASTEXITCODE
    if ($code -ge 8) {
        throw "robocopy ist fehlgeschlagen (ExitCode $code)."
    }
}

function Write-PresetFile {
    param(
        [string]$TargetDrive,
        [string]$PresetBase64Value
    )
    if ([string]::IsNullOrWhiteSpace($PresetBase64Value)) {
        return
    }
    $targetDir = Join-Path $TargetDrive "pve-thin-client"
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    $bytes = [Convert]::FromBase64String($PresetBase64Value)
    [IO.File]::WriteAllBytes((Join-Path $targetDir "preset.env"), $bytes)
}

function Write-Manifest {
    param(
        [string]$TargetDrive,
        [string]$IsoUrl,
        [string]$ProfileName
    )
    $manifest = [ordered]@{
        version = "windows-builder"
        generated_at = [DateTime]::UtcNow.ToString("o")
        iso_url = $IsoUrl
        preset_name = $ProfileName
        platform = "windows"
    } | ConvertTo-Json -Depth 4
    [IO.File]::WriteAllText((Join-Path $TargetDrive ".beagle-windows-usb.json"), $manifest, [Text.Encoding]::UTF8)
}

Assert-Administrator

if ($ListDisks) {
    Show-DiskTable
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
    $mountedIso = Get-MountedIsoLetter -ImagePath $isoPath
    $usbDrive = Prepare-UsbDisk -TargetDiskNumber $DiskNumber -Label $UsbLabel
    Copy-IsoContents -SourceDrive $mountedIso.DriveLetter -TargetDrive $usbDrive
    Write-PresetFile -TargetDrive $usbDrive -PresetBase64Value $PresetBase64
    Write-Manifest -TargetDrive $usbDrive -IsoUrl $ReleaseIsoUrl -ProfileName $PresetName
    Write-Step ("Windows USB-Installer fertig: Datentraeger {0} ({1})" -f $DiskNumber, $usbDrive)
} finally {
    if ($mountedIso -and $mountedIso.DiskImage) {
        Dismount-DiskImage -ImagePath $isoPath -ErrorAction SilentlyContinue | Out-Null
    }
}
