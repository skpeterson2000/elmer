"""The smallest devtools client that will load a page and run a script in it.

For tests that need a real browser: a page's inline script either runs or it
does not, and nothing short of a JavaScript engine can say which. Chromium's
own --screenshot stopped noticing page loads after the upgrade to 152;
driving it over the devtools protocol does not depend on that. Pure Python -
the websocket handshake, masked client frames, and a handful of CDP calls -
so the test suite needs nothing installed beyond the browser the kiosk
already runs.

    from _browser import evaluate
    value = evaluate("http://127.0.0.1:5079/party", "typeof tick")
"""
import base64, json, os, shutil, socket, struct, subprocess, time, urllib.request


def available():
    return shutil.which("chromium") or shutil.which("chromium-browser")


def evaluate(url, js, width=1024, height=600, settle=2.0, port=9341):
    """Load `url` in a headless Chromium, wait `settle` seconds, return `js`."""
    chromium = available()
    if not chromium:
        raise RuntimeError("no chromium on this machine")
    return _run(chromium, url, None, width, height, js, settle, port)


def _run(chromium, url, out, w, h, js, settle, port):
  proc = subprocess.Popen(
      [chromium, "--headless=new", "--disable-gpu", "--no-sandbox",
       "--disable-dev-shm-usage", f"--remote-debugging-port={port}",
       f"--window-size={w},{h}", "about:blank"],
      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
  try:
      for _ in range(100):
          try:
              targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json"))
              page = next(t for t in targets if t["type"] == "page")
              break
          except Exception:
              time.sleep(0.2)
      else:
          raise SystemExit("chromium never answered on the debugging port")
      ws = page["webSocketDebuggerUrl"]           # ws://127.0.0.1:9333/devtools/page/ID
      path = ws.split(f":{port}", 1)[1]
      s = socket.create_connection(("127.0.0.1", port))
      s.sendall((f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nUpgrade: websocket\r\n"
                 f"Connection: Upgrade\r\nSec-WebSocket-Key: {base64.b64encode(os.urandom(16)).decode()}\r\n"
                 f"Sec-WebSocket-Version: 13\r\n\r\n").encode())
      buf = b""
      while b"\r\n\r\n" not in buf:
          buf += s.recv(4096)
      buf = buf.split(b"\r\n\r\n", 1)[1]

      def send(obj):
          data = json.dumps(obj).encode()
          mask = os.urandom(4)
          head = bytes([0x81])
          n = len(data)
          if n < 126: head += bytes([0x80 | n])
          elif n < 65536: head += bytes([0x80 | 126]) + struct.pack(">H", n)
          else: head += bytes([0x80 | 127]) + struct.pack(">Q", n)
          s.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

      def recv():
          nonlocal buf
          while True:
              while len(buf) < 2:
                  buf += s.recv(65536)
              n = buf[1] & 0x7F; off = 2
              if n == 126: n = struct.unpack(">H", buf[2:4])[0]; off = 4
              elif n == 127: n = struct.unpack(">Q", buf[2:10])[0]; off = 10
              while len(buf) < off + n:
                  buf += s.recv(65536)
              payload, buf = buf[off:off + n], buf[off + n:]
              return json.loads(payload)

      def call(ident, method, **params):
          send({"id": ident, "method": method, "params": params})
          while True:
              msg = recv()
              if msg.get("id") == ident:
                  return msg.get("result", msg)

      call(1, "Page.enable")
      call(2, "Emulation.setDeviceMetricsOverride", width=w, height=h,
           deviceScaleFactor=1, mobile=False)
      call(3, "Page.navigate", url=url)
      time.sleep(settle)
      value = None
      if js:
          got = call(4, "Runtime.evaluate", expression=js, returnByValue=True, awaitPromise=True)
          value = (got.get("result") or {}).get("value")
          if got.get("exceptionDetails"):
              value = "EXCEPTION " + str(got["exceptionDetails"].get("text"))
      if out:
          shot = call(5, "Page.captureScreenshot", format="png")
          open(out, "wb").write(base64.b64decode(shot["data"]))
      return value
  finally:
      proc.terminate()
