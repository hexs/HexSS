# --- WinRT helpers (same pattern you used) ---
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() |
    Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]

function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}

function AwaitAction($WinRtAction) {
    $asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() |
        Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and -not $_.IsGenericMethod })[0]
    $netTask = $asTask.Invoke($null, @($WinRtAction))
    $netTask.Wait(-1) | Out-Null
}

# --- Ensure WLAN service is running (needed for Wi-Fi radios) ---
function Start-WlanServiceIfNeeded {
    $svc = Get-Service -Name WlanSvc -ErrorAction SilentlyContinue
    if ($svc -and $svc.Status -ne 'Running') {
        Start-Service -Name WlanSvc
        $svc.WaitForStatus('Running','00:00:10') | Out-Null
    }
}

# --- Helpers to connect to Wi-Fi using netsh ---
function New-WlanProfileXml {
    param(
        [Parameter(Mandatory)][string]$Ssid,
        [string]$Password  # if empty/null => open network profile
    )
    $ssidEsc = [System.Security.SecurityElement]::Escape($Ssid)
    if ([string]::IsNullOrEmpty($Password)) {
        @"
<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
  <name>$ssidEsc</name>
  <SSIDConfig><SSID><name>$ssidEsc</name></SSID></SSIDConfig>
  <connectionType>ESS</connectionType>
  <connectionMode>auto</connectionMode>
  <MSM>
    <security>
      <authEncryption>
        <authentication>open</authentication>
        <encryption>none</encryption>
        <useOneX>false</useOneX>
      </authEncryption>
    </security>
  </MSM>
</WLANProfile>
"@
    } else {
        $pwdEsc = [System.Security.SecurityElement]::Escape($Password)
        # WPA2-Personal (PSK/AES). This works for most home/office APs.
        # Note: If the network is WPA3-SAE only, this profile won't connect.
        @"
<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
  <name>$ssidEsc</name>
  <SSIDConfig><SSID><name>$ssidEsc</name></SSID></SSIDConfig>
  <connectionType>ESS</connectionType>
  <connectionMode>auto</connectionMode>
  <MSM>
    <security>
      <authEncryption>
        <authentication>WPA2PSK</authentication>
        <encryption>AES</encryption>
        <useOneX>false</useOneX>
      </authEncryption>
      <sharedKey>
        <keyType>passPhrase</keyType>
        <protected>false</protected>
        <keyMaterial>$pwdEsc</keyMaterial>
      </sharedKey>
    </security>
  </MSM>
</WLANProfile>
"@
    }
}

function Connect-WiFi {
    param(
        [Parameter(Mandatory)][string]$Ssid,
        [string]$Password
    )

    # If a profile with the same name exists, netsh connect can use it directly.
    $profileExists = (netsh wlan show profiles) -match ":\s*$([regex]::Escape($Ssid))\s*$"

    if (-not $profileExists) {
        # Build a temporary profile XML and add it
        $xml = New-WlanProfileXml -Ssid $Ssid -Password $Password
        $tmp = [System.IO.Path]::GetTempFileName()
        [IO.File]::WriteAllText($tmp, $xml, [Text.Encoding]::UTF8)
        try {
            $add = netsh wlan add profile filename="$tmp" user=current
            if ($LASTEXITCODE -ne 0 -or ($add -notmatch 'added on interface')) {
                Write-Host "Failed to add WLAN profile for '$Ssid'." -ForegroundColor Red
                return $false
            }
        } finally {
            Remove-Item $tmp -ErrorAction SilentlyContinue
        }
    }

    # Try to connect
    $out = netsh wlan connect name="$Ssid" ssid="$Ssid"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "netsh connect failed for '$Ssid'." -ForegroundColor Red
        return $false
    }

    # Wait up to ~15s for association
    for ($i=0; $i -lt 15; $i++) {
        Start-Sleep -Seconds 1
        $ifc = netsh wlan show interfaces
        if ($ifc -match '^\s*State\s*:\s*connected' -and $ifc -match "^\s*SSID\s*:\s*$([regex]::Escape($Ssid))\s*$") {
            Write-Host "Connected to '$Ssid'." -ForegroundColor Green
            return $true
        }
    }

    Write-Host "Timed out waiting to connect to '$Ssid'." -ForegroundColor Yellow
    return $false
}

# --- Toggle Wi-Fi radio using Windows.Devices.Radios and optionally connect to SSID ---
function SetWiFi([ValidateSet(0,1)][int]$Enable, [string]$Ssid = $null, [string]$Password = $null) {
    Start-WlanServiceIfNeeded

    $RadioType = [Windows.Devices.Radios.Radio, Windows.Devices.Radios, ContentType=WindowsRuntime]

    # Get radios and filter Wi-Fi
    $radios = Await ($RadioType::GetRadiosAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]])
    if (-not $radios) { Write-Host "No radios found." -ForegroundColor Red; return }

    $wifiRadios = $radios | Where-Object { $_.Kind -eq [Windows.Devices.Radios.RadioKind]::WiFi }
    if (-not $wifiRadios) { Write-Host "No Wi-Fi radio found." -ForegroundColor Red; return }

    $targetState = if ($Enable -eq 1) { [Windows.Devices.Radios.RadioState]::On } else { [Windows.Devices.Radios.RadioState]::Off }

    foreach ($r in $wifiRadios) {
        if ($r.State -ne $targetState) {
            Write-Host "Setting Wi-Fi ($($r.Name)) to $targetState…"
            $result = Await ($r.SetStateAsync($targetState)) ([Windows.Devices.Radios.RadioAccessStatus])
            Write-Host " -> Result: $result"
            if ($result.ToString() -ne 'Allowed') {
                Write-Host "   (If DeniedBySystem: check Airplane mode, policies, or a physical/OEM radio switch.)" -ForegroundColor DarkYellow
            }
        } else {
            Write-Host "Wi-Fi ($($r.Name)) already $($r.State)." -ForegroundColor Yellow
        }
    }

    # If turning off, we're done.
    if ($Enable -eq 0) { return }

    # If SSID provided, attempt connection.
    if ($Ssid) {
        # Give the radio a brief moment to come up before connecting.
        Start-Sleep -Seconds 2
        [void](Connect-WiFi -Ssid $Ssid -Password $Password)
    }
}

# --- Examples ---
# SetWiFi 0
# SetWiFi 1
# SetWiFi 1 "SSID"
# SetWiFi 1 "SSID" "password"
