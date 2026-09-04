#!/usr/bin/env python3
"""ELMER - a study assistant and game for radio theory and propagation.

    ./elmer.py                 serve on http://0.0.0.0:5000
    ./elmer.py --doctor        self-check and print every URL to try
    ./elmer.py --build         rebuild the question pools from data/raw
    ./elmer.py --fetch         re-download the source pools, then rebuild
    ./elmer.py --stats         print progress to the terminal
    ./elmer.py --log-level DEBUG   verbose console output
"""
import argparse
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
    ap.add_argument("--doctor", action="store_true",
                    help="check the install and report where to reach it")
    ap.add_argument("--build", action="store_true", help="rebuild pools from data/raw")
    ap.add_argument("--fetch", action="store_true", help="re-download sources, then rebuild")
    ap.add_argument("--stats", action="store_true", help="print progress and exit")
    args = ap.parse_args()

    from elmer import logs
    log_path = logs.setup(args.log_level, to_file=not args.no_log_file)

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
    if port_in_use(args.port):
        print(f"\n  Port {args.port} is already in use - ELMER may already be "
              f"running.\n  Try http://localhost:{args.port} first, or start this "
              f"one on another port with --port 5001\n")
        sys.exit(1)

    print("\n  ELMER is starting. Open it at:\n")
    print(f"      http://localhost:{args.port}          (on this machine)")
    for interface, ip in local_addresses():
        print(f"      http://{ip}:{args.port}      (from another device, via {interface})")
    if log_path:
        print(f"\n  Logging to {log_path}")
        print(f"  Watch it live with:  tail -f {log_path}")
    print("  Press Ctrl+C to stop.\n")

    from elmer.app import app
    try:
        app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)
    except OSError as exc:
        print(f"\n  Could not bind {args.host}:{args.port} - {exc}\n"
              f"  Run ./elmer.py --doctor for a full check.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
