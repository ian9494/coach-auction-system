"""Exercise real Tk fields/callbacks against an ephemeral ASGI server."""
import asyncio
import tkinter as tk
from final_project.client.coach_app import CoachApp
from .live_support import live
from .transport_support import config_and_auth
from .test_registration import PASSWORD


def test_tk_registration_login_logout(tmp_path):
    async def run():
        config, auth = config_and_auth(tmp_path)
        async with live(config, auth) as r:
            root = tk.Tk()
            root.withdraw()
            app = CoachApp(root)
            app.url.set(r.url)
            app.username.set('gui_user')
            app.password.set(PASSWORD)
            app.confirm_password.set('mismatch')
            app.register_account()
            assert app.registration is None and '一致' in app.model.message
            app.confirm_password.set(PASSWORD)
            app.token.set(auth.coach_tokens['coach01'])
            app.register_account()
            try:
                async with asyncio.timeout(10):
                    while app.registration is not None:
                        root.update()
                        await asyncio.sleep(.01)
                assert app.model.message == '註冊完成，請按登入。'
                assert app.token.get() == ''
                app.connect()
                async with asyncio.timeout(10):
                    while app.model.connection != 'connected':
                        root.update()
                        await asyncio.sleep(.01)
                assert app.model.snapshot['coach']['id'] == 'coach01'
                assert not app.password.get()
                app.disconnect()
                async with asyncio.timeout(10):
                    while app.transport is not None:
                        root.update()
                        await asyncio.sleep(.01)
                assert app.model.connection == 'offline'
            finally:
                if app.transport:
                    app.transport.disconnect()
                    await asyncio.to_thread(app.transport.join, 5)
                root.destroy()
    asyncio.run(asyncio.wait_for(run(), 35))
