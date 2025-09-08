# --- WinRT helpers ---
Add-Type -AssemblyName System.Runtime.WindowsRuntime

# Generic AsTask: IAsyncOperation`1 -> Task<T>
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() |
    Where-Object {
        $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and
        $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    } | Select-Object -First 1)
if (-not $asTaskGeneric) { throw "Couldn't locate generic AsTask(IAsyncOperation`1) method." }

# Non-generic AsTask: IAsyncAction -> Task
$asTaskNonGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() |
    Where-Object {
        $_.Name -eq 'AsTask' -and -not $_.IsGenericMethod -and
        $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction'
    } | Select-Object -First 1)
if (-not $asTaskNonGeneric) { throw "Couldn't locate non-generic AsTask(IAsyncAction) method." }

function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $null = $netTask.Wait(-1)
    $netTask.Result
}
function AwaitAction($WinRtAction) {
    $netTask = $asTaskNonGeneric.Invoke($null, @($WinRtAction))
    $null = $netTask.Wait(-1)
}

# ---- Band support helpers ----
$ApiInfo = [Windows.Foundation.Metadata.ApiInformation, Windows.Foundation, ContentType=WindowsRuntime]
$NwOpNS  = 'Windows.Networking.NetworkOperators'
$CfgType = "$NwOpNS.NetworkOperatorTetheringAccessPointConfiguration"

function Get-BandEnum([string]$BandText) {
    $bandEnumType = "$NwOpNS.TetheringWiFiBand"
    if (-not $ApiInfo::IsTypePresent($bandEnumType)) { return $null }
    switch ($BandText.Trim().ToLower()) {
        '2.4 ghz' { return ([type]$bandEnumType)::TwoPointFourGigahertz }
        '5 ghz'   { return ([type]$bandEnumType)::FiveGigahertz }
        default   { return ([type]$bandEnumType)::Auto } # "Any available"
    }
}

function Set-Hotspot {
param(
    [Parameter(Mandatory=$true)][ValidateSet(0,1)][int]$Enable,
    [string]$Ssid,
    [string]$Passphrase,
    [ValidateSet('2.4 GHz','5 GHz','Any available')][string]$Network_band = 'Any available'
)
    # Current internet connection profile (Wi-Fi/Ethernet with internet)
    $connectionProfile = [Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime]::GetInternetConnectionProfile()
    if (-not $connectionProfile) { throw "No internet connection profile found." }

    $tetheringManager = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime]::CreateFromConnectionProfile($connectionProfile)
    if (-not $tetheringManager) { throw "Failed to create NetworkOperatorTetheringManager." }

    # Optional: set SSID/passphrase and (if supported) band before starting
    if ($Ssid -or $Passphrase -or $Network_band) {
        $cfg = $tetheringManager.GetCurrentAccessPointConfiguration()
        $applyCfg = $false

        if ($Ssid)       { $cfg.Ssid = $Ssid; $applyCfg = $true }
        if ($Passphrase) { $cfg.Passphrase = $Passphrase; $applyCfg = $true }

        $bandEnum = Get-BandEnum $Network_band
        $bandPropSupported = $ApiInfo::IsPropertyPresent($CfgType, 'Band') -and $bandEnum -ne $null
        if ($bandPropSupported) {
            $cfg.Band = $bandEnum
            $applyCfg = $true
        } elseif ($Network_band -ne 'Any available') {
            Write-Warning "This Windows build/driver doesn't expose Hotspot Band; ignoring -Network_band."
        }

        if ($applyCfg) { AwaitAction ($tetheringManager.ConfigureAccessPointAsync($cfg)) }
    }

    switch ($Enable) {
        1 {
            if ($tetheringManager.TetheringOperationalState -eq 1) {
                "Hotspot is already On!"
            } else {
                "Hotspot is off! Turning it on"
                $result = Await ($tetheringManager.StartTetheringAsync()) ([Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult])
                if ($result.Status -ne [Windows.Networking.NetworkOperators.TetheringOperationStatus]::Success) {
                    throw "Start failed: $($result.Status)"
                }
            }
        }
        0 {
            if ($tetheringManager.TetheringOperationalState -eq 0) {
                "Hotspot is already Off!"
            } else {
                "Hotspot is on! Turning it off"
                $result = Await ($tetheringManager.StopTetheringAsync()) ([Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult])
                if ($result.Status -ne [Windows.Networking.NetworkOperators.TetheringOperationStatus]::Success) {
                    throw "Stop failed: $($result.Status)"
                }
            }
        }
    }
}

# Examples:
# Set-Hotspot -Enable 1                               # On (keep current SSID/pass/band)
# Set-Hotspot -Enable 1 -Ssid "MyHotspot" -Passphrase "Str0ngPassw0rd!"
# Set-Hotspot -Enable 1 -Network_band "2.4 GHz"
# Set-Hotspot -Enable 1 -Network_band "5 GHz"
# Set-Hotspot -Enable 0                               # Off
