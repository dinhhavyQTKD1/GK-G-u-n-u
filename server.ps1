# =====================================================================
# Enterprise Data Analytics AI Agent - Localhost Server (Port 8080)
# Sử dụng TcpListener (không yêu cầu quyền Admin URL ACL trên Windows)
# Phục vụ Giao diện Web App (index.html) + REST API Backend (/api/*)
# =====================================================================
param(
    [int]$Port = 8080
)

$ErrorActionPreference = "Continue"
$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DataDir = Join-Path $RootDir "data"
if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir | Out-Null
}

$VectorDbFile = Join-Path $DataDir "vector_feedback_db.json"
$ApprovalLogFile = Join-Path $DataDir "approval_audit_log.json"

if (-not (Test-Path $VectorDbFile)) {
    $initVectors = @(
        @{
            id = "VEC-001"
            time = "2026-11-15 09:00"
            role = "Manager_Region_North"
            type = "LIKE_ACCURATE"
            threshold = "15.0%"
            rule = "Luôn loại bỏ đơn test nội bộ (is_test = True) và cảnh báo đỏ khi tỷ lệ hủy tại cửa hàng vượt 15%."
        },
        @{
            id = "VEC-002"
            time = "2026-11-15 14:20"
            role = "CEO_Executive"
            type = "KPI_FORMULA_UPDATED"
            threshold = "15.0%"
            rule = "Khi phân tích nguyên nhân hủy đơn, bắt buộc đối chiếu chênh lệch tồn kho thực tế (Physical Stock) và tồn kho POS theo khung giờ."
        }
    )
    $initVectors | ConvertTo-Json -Depth 5 | Set-Content -Path $VectorDbFile -Encoding UTF8
}

$Endpoint = New-Object System.Net.IPEndPoint([System.Net.IPAddress]::Loopback, $Port)
$Listener = New-Object System.Net.Sockets.TcpListener($Endpoint)
$Listener.Start()

Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host " AI Agent Localhost Server is running at: http://localhost:$Port" -ForegroundColor Green
Write-Host " Workspace Root: $RootDir" -ForegroundColor Gray
Write-Host "==============================================================" -ForegroundColor Cyan

$MimeTypes = @{
    ".html" = "text/html; charset=utf-8"
    ".css"  = "text/css; charset=utf-8"
    ".js"   = "application/javascript; charset=utf-8"
    ".json" = "application/json; charset=utf-8"
    ".csv"  = "text/csv; charset=utf-8"
    ".png"  = "image/png"
    ".svg"  = "image/svg+xml"
}

function Send-HttpResponse($Stream, [int]$StatusCode, [string]$StatusText, [string]$ContentType, [byte[]]$BodyBytes) {
    $Header = "HTTP/1.1 $StatusCode $StatusText`r`n" +
              "Content-Type: $ContentType`r`n" +
              "Content-Length: $($BodyBytes.Length)`r`n" +
              "Access-Control-Allow-Origin: *`r`n" +
              "Access-Control-Allow-Methods: GET, POST, OPTIONS`r`n" +
              "Access-Control-Allow-Headers: Content-Type`r`n" +
              "Connection: close`r`n`r`n"
    $HeaderBytes = [System.Text.Encoding]::ASCII.GetBytes($Header)
    $Stream.Write($HeaderBytes, 0, $HeaderBytes.Length)
    if ($BodyBytes.Length -gt 0) {
        $Stream.Write($BodyBytes, 0, $BodyBytes.Length)
    }
    $Stream.Flush()
}

try {
    while ($true) {
        $Client = $Listener.AcceptTcpClient()
        try {
            $Stream = $Client.GetStream()
            $Stream.ReadTimeout = 3000
            $Buffer = New-Object byte[] 65536
            $BytesRead = $Stream.Read($Buffer, 0, $Buffer.Length)
            if ($BytesRead -le 0) {
                $Client.Close()
                continue
            }

            $RawRequest = [System.Text.Encoding]::UTF8.GetString($Buffer, 0, $BytesRead)
            $Lines = $RawRequest -split "`r`n"
            $RequestLine = $Lines[0] -split " "
            $Method = $RequestLine[0]
            $RawUrl = if ($RequestLine.Length -ge 2) { $RequestLine[1] } else { "/" }
            $UrlPath = ($RawUrl -split "\?")[0]

            $BodyIndex = $RawRequest.IndexOf("`r`n`r`n")
            $BodyText = if ($BodyIndex -ge 0) { $RawRequest.Substring($BodyIndex + 4) } else { "" }

            if ($Method -eq "OPTIONS") {
                Send-HttpResponse $Stream 200 "OK" "text/plain" ([byte[]]@())
                $Client.Close()
                continue
            }

            # REST API 1: GET /api/status
            if ($UrlPath -eq "/api/status") {
                $vectors = Get-Content -Path $VectorDbFile -Raw -Encoding UTF8 | ConvertFrom-Json
                $payload = @{
                    status = "online"
                    server = "Enterprise Data Analytics AI Agent Localhost"
                    port = $Port
                    timestamp = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss+07:00")
                    vector_memories = $vectors
                } | ConvertTo-Json -Depth 6
                $bytes = [System.Text.Encoding]::UTF8.GetBytes($payload)
                Send-HttpResponse $Stream 200 "OK" "application/json; charset=utf-8" $bytes
                $Client.Close()
                continue
            }

            # REST API 2: POST /api/feedback
            if ($UrlPath -eq "/api/feedback" -and $Method -eq "POST") {
                $newEntry = $BodyText | ConvertFrom-Json
                $existing = @(Get-Content -Path $VectorDbFile -Raw -Encoding UTF8 | ConvertFrom-Json)
                $newId = "VEC-" + ($existing.Count + 1).ToString("000")
                $record = [PSCustomObject]@{
                    id        = $newId
                    time      = (Get-Date).ToString("yyyy-MM-dd HH:mm")
                    role      = $newEntry.role
                    type      = $newEntry.type
                    threshold = $newEntry.threshold
                    rule      = $newEntry.rule
                }
                $updated = @($record) + $existing
                $updated | ConvertTo-Json -Depth 5 | Set-Content -Path $VectorDbFile -Encoding UTF8

                $respJson = @{ ok = $true; saved = $record; all_memories = $updated } | ConvertTo-Json -Depth 6
                $bytes = [System.Text.Encoding]::UTF8.GetBytes($respJson)
                Send-HttpResponse $Stream 200 "OK" "application/json; charset=utf-8" $bytes
                $Client.Close()
                continue
            }

            # REST API 3: POST /api/approve-alert
            if ($UrlPath -eq "/api/approve-alert" -and $Method -eq "POST") {
                $data = $BodyText | ConvertFrom-Json
                $auditRecord = @{
                    audit_id = "AUD-" + (Get-Date).ToString("yyyyMMddHHmmss")
                    approved = $data.approved
                    role = $data.role
                    target_store = "CH04 - Cửa hàng #04 Cầu Giấy"
                    timestamp = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss+07:00")
                }
                $auditRecord | ConvertTo-Json -Depth 4 | Set-Content -Path $ApprovalLogFile -Encoding UTF8

                $respJson = @{ ok = $true; audit = $auditRecord } | ConvertTo-Json -Depth 4
                $bytes = [System.Text.Encoding]::UTF8.GetBytes($respJson)
                Send-HttpResponse $Stream 200 "OK" "application/json; charset=utf-8" $bytes
                $Client.Close()
                continue
            }

            # Static files
            if ($UrlPath -eq "/" -or $UrlPath -eq "") {
                $UrlPath = "/index.html"
            }

            $RelativePath = [System.Uri]::UnescapeDataString($UrlPath.TrimStart("/")).Replace("/", "\")
            $FilePath = Join-Path $RootDir $RelativePath

            if (Test-Path $FilePath -PathType Leaf) {
                $Ext = [System.IO.Path]::GetExtension($FilePath).ToLower()
                $CType = if ($MimeTypes.ContainsKey($Ext)) { $MimeTypes[$Ext] } else { "application/octet-stream" }
                $FileBytes = [System.IO.File]::ReadAllBytes($FilePath)
                Send-HttpResponse $Stream 200 "OK" $CType $FileBytes
            } else {
                $errBytes = [System.Text.Encoding]::UTF8.GetBytes("404 Not Found: $UrlPath")
                Send-HttpResponse $Stream 404 "Not Found" "text/plain; charset=utf-8" $errBytes
            }
        } catch {
            # Ignore client disconnect errors
        } finally {
            $Client.Close()
        }
    }
} finally {
    $Listener.Stop()
}
