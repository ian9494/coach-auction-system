@echo off
set "TOKEN=%ADMIN_TOKEN%"
if "%TOKEN%"=="" set "TOKEN=dev-token"

curl -X POST http://localhost:3000/api/admin/reset-budgets ^
  -H "x-admin-token: %TOKEN%"

pause
