@echo off
curl -X POST http://localhost:3000/api/admin/reset-budgets ^
  -H "x-admin-token: yukimura20050904"

pause