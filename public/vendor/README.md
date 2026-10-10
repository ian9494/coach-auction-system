# Vendored Socket.IO client

`socket.io.min.js` is the unmodified browser distribution from **socket.io-client 4.8.1** (MIT).
Source: https://registry.npmjs.org/socket.io-client/-/socket.io-client-4.8.1.tgz (`package/dist/socket.io.min.js`).
License: `socket.io.LICENSE`, copied from the same package. The distribution's license header is preserved.

SHA-256: `b0e735814f8dcfecd6cdb8a7ce95a297a7e1e5f2727a29e6f5901801d52fa0c5`.

JavaScript Socket.IO 4.x uses Socket.IO protocol 5 / Engine.IO 4 and is compatible with python-socketio 5.x / python-engineio 4.x.
Compatibility reference: https://python-socketio.readthedocs.io/en/stable/intro.html#version-compatibility
Runtime pages load `/vendor/socket.io.min.js` locally; no CDN or Node `/socket.io/socket.io.js` route is required.
The optional source map is not included; it is not needed to execute the client.
