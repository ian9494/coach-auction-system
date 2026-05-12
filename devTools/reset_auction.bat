@echo off
set "TOKEN=%ADMIN_TOKEN%"
if "%TOKEN%"=="" set "TOKEN=dev-token"

curl -X POST http://localhost:3000/api/admin/reset-auctions ^
  -H "x-admin-token: %TOKEN%"

curl -X POST https://auction.noctration.dev/api/admin/reset-auctions ^
  -H "x-admin-token: %TOKEN%"

pause
