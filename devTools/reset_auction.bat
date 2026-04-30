@echo off
curl -X POST http://localhost:3000/api/admin/reset-auctions ^
  -H "x-admin-token: yukimura20050904"

pause