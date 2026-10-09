"""Public read-only endpoints; no credential or raw-state endpoints."""
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from .projections import viewer_projection


def register_http(app: FastAPI, runtime):
    def current():
        return runtime.service.snapshot() if runtime.ready else None

    def unavailable():
        return JSONResponse({'error_code': 'SERVICE_NOT_READY'}, status_code=503)

    @app.get('/health')
    async def health():
        return {'status': 'ok' if runtime.ready else 'not_ready', 'ready': runtime.ready}

    @app.get('/api/coaches')
    async def coaches():
        snapshot = current()
        if snapshot is None: return unavailable()
        return [{'id': c.id, 'name': c.name} for c in snapshot.state.coaches]

    @app.get('/api/members')
    async def members():
        snapshot = current()
        if snapshot is None: return unavailable()
        sold = {h.player for h in snapshot.state.history}
        return [p.name for p in snapshot.state.roster if p.name not in sold]

    @app.get('/api/results')
    async def results():
        snapshot = current()
        if snapshot is None: return unavailable()
        return [{'playerName': h.player, 'coachId': h.coach_id, 'amount': h.amount} for h in snapshot.state.history]

    @app.get('/api/state/viewer')
    async def viewer():
        snapshot = current()
        return viewer_projection(snapshot) if snapshot else unavailable()

    @app.exception_handler(Exception)
    async def internal_error(request, exc):
        return JSONResponse({'error_code': 'INTERNAL_ERROR'}, status_code=500)
