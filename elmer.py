#!/usr/bin/env python3
"""ELMER - a study assistant and game for radio theory and propagation.

    ./elmer.py                 serve on http://0.0.0.0:5000
    ./elmer.py --kiosk         serve, and open full screen on this machine
    ./elmer.py --install-launcher   add ELMER to the applications menu
    ./elmer.py --doctor        self-check and print every URL to try
    ./elmer.py --build         rebuild the question pools from data/raw
    ./elmer.py --fetch         re-download the source pools, then rebuild
    ./elmer.py --stats         print progress to the terminal
    ./elmer.py --log-level DEBUG   verbose console output
"""
import argparse
import secrets
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="0.0.0.0",
                    help="interface to bind (default: all)")
    ap.add_argument("--port", type=int, default=5000)
    ap.add_argument("--debug", action="store_true",
                    help="Flask debug mode with auto-reload and tracebacks in the browser")
    ap.add_argument("--log-level", default="INFO",
                    choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                    help="console verbosity; the log file always keeps DEBUG")
    ap.add_argument("--no-log-file", action="store_true",
                    help="console only, do not write data/elmer.log")
    ap.add_argument("--kiosk", action="store_true",
                    help="open a full-screen browser on this machine and show "
                         "an Exit button that stops the server")
    ap.add_argument("--install-launcher", action="store_true",
                    help="add ELMER to the applications menu and the desktop, "
                         "with its icon")
    ap.add_argument("--remove-launcher", action="store_true",
                    help="take the menu entry, icon and desktop shortcut away again")
    ap.add_argument("--doctor", action="store_true",
                    help="check the install and report where to reach it")
    ap.add_argument("--build", action="store_true", help="rebuild pools from data/raw")
    ap.add_argument("--fetch", action="store_true", help="re-download sources, then rebuild")
    ap.add_argument("--stats", action="store_true", help="print progress and exit")
    args = ap.parse_args()

    from elmer import logs
    log_path = logs.setup(args.log_level, to_file=not args.no_log_file)

    if args.install_launcher or args.remove_launcher:
        from elmer import launcher
        if args.remove_launcher:
            removed = launcher.remove()
            print("\n  Removed:" if removed else "\n  Nothing to remove.")
            for path in removed:
                print(f"      {path}")
            print()
            return
        try:
            written = launcher.install()
        except (OSError, FileNotFoundError) as exc:
            print(f"\n  Could not install the launcher: {exc}\n")
            sys.exit(1)
        print("\n  ELMER is now in the applications menu. Installed:\n")
        for path in written:
            print(f"      {path}")
        print("\n  Clicking it starts ELMER full screen. Right-click the entry")
        print("  and choose \"Open in a window\" for an ordinary window instead.")
        print("  Remove it again with ./elmer.py --remove-launcher\n")
        return

    if args.doctor:
        from elmer.diagnostics import doctor
        sys.exit(0 if doctor(args.port) else 1)

    if args.fetch:
        from elmer.pools.fetch import fetch_all
        fetch_all()
        args.build = True
    if args.build:
        from elmer.pools.build import build_all
        print("Building question pools:")
        build_all()
        if not args.stats:
            return

    if args.stats:
        from elmer.report import print_stats
        print_stats()
        return

    from elmer.diagnostics import local_addresses, port_in_use
    took_over = False
    if port_in_use(args.port):
        # Started from the menu entry there is no terminal to print to, so a
        # second click would look like nothing happening at all.  If ELMER is
        # already serving, put a window on that instead of refusing.
        #
        # An ordinary window rather than a kiosk one: that server is not ours to
        # stop, so its pages carry no Exit button, and a full screen window with
        # no way out and no button would strand the user.  But if the thing on
        # the port is another ELMER of ours, the operator can simply be asked
        # whether to take it over - which is what they usually want, and what a
        # message printed to a Terminal=false launcher could never tell them.
        if args.kiosk:
            from elmer import kiosk
            url = f"http://localhost:{args.port}"
            other = kiosk.serving_elsewhere(args.port)

            if other and kiosk.have_display():
                choice = kiosk.ask(
                    f"ELMER is already serving on port {args.port}.\n\n"
                    "Full screen has to be the instance that owns the server, so "
                    "that its Exit button can stop it.",
                    ["Stop it and go full screen", "Just open a window"])
                if choice == "Stop it and go full screen":
                    if kiosk.stop_other(other, args.port):
                        print(f"  stopped the ELMER already on port {args.port}")
                        took_over = True
                    else:
                        kiosk.tell("Could not stop the other instance.\n"
                                   "Opening a window on it instead.")

            if not took_over and kiosk.have_display():
                import webbrowser
                if webbrowser.open(url):
                    kiosk.tell(
                        f"ELMER is already serving on port {args.port}, so this is "
                        "an ordinary window.\n\nIt has no Exit button, because that "
                        "server is not this one's to stop.")
                    print(f"\n  ELMER is already serving on port {args.port} - "
                          f"opened {url} in a window.\n"
                          "  Stop that one first if you want the full-screen "
                          "kiosk with its Exit button.\n")
                    return

        if not took_over:
            print(f"\n  Port {args.port} is already in use - ELMER may already be "
                  f"running.\n  Try http://localhost:{args.port} first, or start "
                  f"this one on another port with --port 5001\n")
            sys.exit(1)

    print("\n  ELMER is starting. Open it at:\n")
    print(f"      http://localhost:{args.port}          (on this machine)")
    for interface, ip in local_addresses():
        print(f"      http://{ip}:{args.port}      (from another device, via {interface})")
    if log_path:
        print(f"\n  Logging to {log_path}")
        print(f"  Watch it live with:  tail -f {log_path}")

    from elmer.app import app

    browsers, quitting = [], None
    if args.kiosk:
        import threading

        from elmer import kiosk
        if not kiosk.have_display():
            print("\n  --kiosk needs a screen, and this session has none.")
            print("  Serving normally instead; open one of the URLs above.\n")
        elif not kiosk.find_browser()[0]:
            print("\n  --kiosk needs chromium or firefox, and neither is installed.")
            print("  Serving normally instead; open one of the URLs above.\n")
        else:
            # Minted per run and handed only to loopback requests, so the Exit
            # button works on this screen and nowhere else on the network.
            app.config["KIOSK"] = True
            app.config["KIOSK_TOKEN"] = secrets.token_urlsafe(32)
            quitting = threading.Event()
            browsers = kiosk.launch_when_ready(
                f"http://localhost:{args.port}", args.port, quitting)

            # systemd stops a service with SIGTERM, which would otherwise kill
            # this process outright and leave the browser full screen with
            # nothing behind it.  Route it into the same exit as Ctrl+C.
            def _terminate(_signum, _frame):
                raise KeyboardInterrupt

            signal.signal(signal.SIGTERM, _terminate)
            print("\n  Opening full screen. Stop it with the Exit button in "
                  "the top bar,")
            print("  or with Ctrl+C here.")
    print("\n  Press Ctrl+C to stop.\n" if not app.config["KIOSK"] else "")

    try:
        app.run(host=args.host, port=args.port, debug=args.debug, threaded=True,
                # The reloader runs a second copy of this process, which in
                # kiosk mode would mean a second browser on top of the first.
                use_reloader=args.debug and not args.kiosk)
    except KeyboardInterrupt:
        pass
    except OSError as exc:
        print(f"\n  Could not bind {args.host}:{args.port} - {exc}\n"
              f"  Run ./elmer.py --doctor for a full check.\n")
        sys.exit(1)
    finally:
        if quitting is not None:
            quitting.set()
            from elmer import kiosk
            for process in browsers:
                kiosk.close(process)
            # Any window opened for an off-site link goes with it, rather than
            # being left on the screen with ELMER gone from behind it.
            kiosk.close_windows()
    print("\n  ELMER stopped.\n")


if __name__ == "__main__":
    main()
