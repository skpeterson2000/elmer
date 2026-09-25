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
import base64, json, os, shutil, socket, struct, subprocess, tempfile, time, urllib.request


def available():
    """A Chromium-family browser that actually runs, or None.

    Raspberry Pi OS has `chromium`. GitHub's Ubuntu runners have Google Chrome
    under its own name, and an Ubuntu `chromium-browser` that is a stub
    printing "install the snap" and exiting non-zero - so each candidate is
    asked for its version before it is trusted.
    """
    for name in ("chromium", "google-chrome-stable", "google-chrome", "chrome",
                 "chromium-browser"):
        path = shutil.which(name)
        if not path:
            continue
        try:
            ok = subprocess.run([path, "--version"], capture_output=True,
                                timeout=20).returncode == 0
        except Exception:
            ok = False
        if ok:
            return path
    # Windows: Edge is Chromium and is on every machine; Chrome may be. Both
    # sit at known paths, and neither is asked for its version - on Windows
    # that opens a tab in the browser the person is using, not a probe.
    if os.name == "nt":
        for env, tail in (("ProgramFiles(x86)", r"Microsoft\Edge\Application\msedge.exe"),
                          ("ProgramFiles", r"Microsoft\Edge\Application\msedge.exe"),
                          ("ProgramFiles", r"Google\Chrome\Application\chrome.exe"),
                          ("LocalAppData", r"Google\Chrome\Application\chrome.exe")):
            base = os.environ.get(env)
            if base and os.path.isfile(os.path.join(base, tail)):
                return os.path.join(base, tail)
    return None


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def evaluate(url, js, width=1024, height=600, settle=2.0, port=None, flags=(), cookies=None,
             out=None, clip=None):
    """Load `url` in a headless Chromium, wait `settle` seconds, return `js`.

    A fresh debugging port each time: the last Chromium is still letting go
    of its port when the next one starts, and a fixed port made every second
    launch wait on a browser that was not coming.

    `out` writes a PNG of the page as well, and `clip` is a CSS selector to
    crop it to - which is the difference between a picture of a page and a
    picture of the thing being explained. See tools/guideshots.py, which is
    what this is for: figures for the guide that are taken from the running
    program and can be taken again, rather than drawn once by hand and left
    to go stale as the program moves under them.
    """
    chromium = available()
    if not chromium:
        raise RuntimeError("no chromium on this machine")
    # A cold Chromium sometimes dies at launch and never binds its debug port
    # - a race that has nothing to do with the page under test. Retrying the
    # whole launch turns that flake into a pass rather than a red build; a
    # genuine failure (no browser, a real page fault) still fails, because it
    # fails the same way every attempt.
    last = None
    for attempt in range(3):
        try:
            return _run(chromium, url, out, width, height, js, settle,
                        port or _free_port(), flags, cookies, clip)
        except _LaunchFlake as exc:
            last = exc
            time.sleep(0.5)
    raise SystemExit(str(last) if last else "chromium never launched")


class _LaunchFlake(Exception):
    """Chromium did not come up this time; the launch is worth retrying."""


def _run(chromium, url, out, w, h, js, settle, port, flags=(), cookies=None, clip=None):
  # A profile of its own, thrown away after: a headless browser sharing the
  # profile of the one the person is using would be a tab in their face on
  # Windows, and a locked profile elsewhere.
  profile = tempfile.mkdtemp(prefix="elmer-browser-")
  proc = subprocess.Popen(
      [chromium, "--headless=new", "--disable-gpu", "--no-sandbox",
       "--disable-dev-shm-usage", f"--remote-debugging-port={port}",
       f"--user-data-dir={profile}", "--no-first-run",
       f"--window-size={w},{h}", *flags, "about:blank"],
      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
  try:
      for _ in range(200):          # a cold Chromium on a Pi can take 30 s to answer
          try:
              targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json"))
              page = next(t for t in targets if t["type"] == "page")
              break
          except Exception:
              time.sleep(0.2)
      else:
          raise _LaunchFlake("chromium never answered on the debugging port")
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

      # A native dialog - alert(), confirm(), prompt() - with nobody to answer
      # it. Headless Chromium closes it on its own and, in the builds this
      # has been seen on, takes the renderer down with it; after that the
      # Runtime.evaluate in flight is never answered and the test hangs for
      # ever with nothing printed. Found the first time a page was driven
      # with two accounts on the unit, which is when ELMER offers a password
      # in a confirm(). Answered here, with Cancel, the moment it opens: the
      # dialog closes cleanly and the page goes on. Cancel is the answer that
      # changes nothing.
      dialogs = [0]

      def call(ident, method, **params):
          send({"id": ident, "method": method, "params": params})
          while True:
              msg = recv()
              if msg.get("method") == "Page.javascriptDialogOpening":
                  dialogs[0] += 1
                  send({"id": 9000 + dialogs[0], "method": "Page.handleJavaScriptDialog",
                        "params": {"accept": False}})
                  continue
              if msg.get("method") == "Inspector.targetCrashed":
                  raise RuntimeError("the page crashed under the test")
              if msg.get("id") == ident:
                  return msg.get("result", msg)

      call(1, "Page.enable")
      call(2, "Emulation.setDeviceMetricsOverride", width=w, height=h,
           deviceScaleFactor=1, mobile=False)
      # Signed in before the page is asked for. ELMER's own pages send a
      # browser that has not said who it is to the door at /who, which is the
      # point of that door - so a test driving a page says who it is first,
      # the same as a person.
      for n, (name, value) in enumerate(sorted((cookies or {}).items())):
          call(30 + n, "Network.setCookie", name=name, value=str(value), url=url)
      call(3, "Page.navigate", url=url)
      time.sleep(settle)
      value = None
      if js:
          got = call(4, "Runtime.evaluate", expression=js, returnByValue=True, awaitPromise=True)
          value = (got.get("result") or {}).get("value")
          if got.get("exceptionDetails"):
              value = "EXCEPTION " + str(got["exceptionDetails"].get("text"))
      if out:
          window = None
          if clip:
              # Where the thing being explained actually sits, asked of the
              # page rather than guessed at. A figure cropped to the panel is
              # worth three of the whole window with the panel somewhere in it.
              box = call(6, "Runtime.evaluate", returnByValue=True, expression=(
                  "(() => { const el = document.querySelector(" + json.dumps(clip) + ");"
                  " if (!el) return null; const r = el.getBoundingClientRect();"
                  " return {x: r.x + window.scrollX, y: r.y + window.scrollY,"
                  " width: r.width, height: r.height}; })()"))
              window = ((box.get("result") or {}).get("value")) or None
          args = {"format": "png"}
          if window and window["width"] > 1 and window["height"] > 1:
              pad = 10
              args["clip"] = {"x": max(0, window["x"] - pad), "y": max(0, window["y"] - pad),
                              "width": window["width"] + pad * 2,
                              "height": window["height"] + pad * 2, "scale": 1}
              args["captureBeyondViewport"] = True
          shot = call(5, "Page.captureScreenshot", **args)
          open(out, "wb").write(base64.b64decode(shot["data"]))
      return value
  finally:
      proc.terminate()
      try:
          proc.wait(timeout=5)
      except subprocess.TimeoutExpired:
          proc.kill()
      shutil.rmtree(profile, ignore_errors=True)
