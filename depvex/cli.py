import argparse
import json
import os
import sys
import threading
from pathlib import Path

from depvex.resolver import DependencyResolver
from depvex.watcher import ProjectWatcher


class Colors:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    RESET = "\033[0m"

    @classmethod
    def enabled(cls) -> bool:
        return os.getenv("NO_COLOR") is None and os.getenv("TERM") not in {None, "dumb"}

    @classmethod
    def colorize(cls, text: str, color: str) -> str:
        return f"{color}{text}{cls.RESET}" if cls.enabled() else text


class DepvexCLI:
    def __init__(self) -> None:
        self.parser = self._build_parser()

    def _build_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog="depvex")
        subparsers = parser.add_subparsers(dest="command")

        scan_parser = subparsers.add_parser("scan", help="Run a one-time dependency scan and update requirements.txt")
        scan_parser.add_argument("path", nargs="?", default=".")
        scan_parser.add_argument("--multi", dest="multi", nargs="?", const="services", default=None, help="Scan a set of service folders, e.g. --multi services")

        check_parser = subparsers.add_parser("check", help="Check whether requirements.txt is up to date")
        check_parser.add_argument("path", nargs="?", default=".")
        check_parser.add_argument("--multi", dest="multi", nargs="?", const="services", default=None, help="Check a set of service folders, e.g. --multi services")

        watch_parser = subparsers.add_parser("watch", help="Watch project and auto-update requirements.txt")
        watch_parser.add_argument("path", nargs="?", default=".")
        watch_parser.add_argument("--multi", dest="multi", nargs="?", const="services", default=None, help="Watch a set of service folders, e.g. --multi services")
        return parser

    def _load_service_config(self, root: Path) -> list[str]:
        config_candidates = [root / ".depvex", root / "depvex.json"]
        for config_path in config_candidates:
            if not config_path.exists():
                continue
            try:
                with config_path.open("r", encoding="utf-8") as handle:
                    data = json.load(handle)
                services = data.get("services") if isinstance(data, dict) else None
                if isinstance(services, list):
                    resolved = []
                    for service in services:
                        candidate = root / service
                        if candidate.exists():
                            resolved.append(str(candidate.resolve()))
                    if resolved:
                        return resolved
            except (OSError, json.JSONDecodeError):
                continue
        return []

    def _resolve_targets(self, path: str, multi: str | None) -> list[str]:
        root = Path(path)
        if multi:
            multi_root = root / multi
            if multi_root.exists() and multi_root.is_dir():
                return [str(service_dir) for service_dir in sorted(multi_root.iterdir()) if service_dir.is_dir()]

            services = self._load_service_config(root)
            if services:
                return services
            return [str(multi_root.resolve())]

        services = self._load_service_config(root)
        if services:
            return services
        return [str(root.resolve())]

    def scan(self, path: str, multi: str | None = None) -> int:
        targets = self._resolve_targets(path, multi)
        if len(targets) > 1:
            print(Colors.colorize(f"[depvex] Scanning {len(targets)} service directories from {path}...", Colors.CYAN))
        else:
            print(Colors.colorize(f"[depvex] Starting one-time scan for {path}...", Colors.CYAN))

        resolver = DependencyResolver()
        for target in targets:
            requirements = resolver.rebuild_requirements(target, output_path=str(Path(target) / "requirements.txt"))
            print(Colors.colorize(f"[depvex] Updated {target}/requirements.txt with {len(requirements)} dependency entries.", Colors.GREEN))
        return 0

    def check(self, path: str, multi: str | None = None) -> int:
        targets = self._resolve_targets(path, multi)
        if len(targets) > 1:
            print(Colors.colorize(f"[depvex] Checking {len(targets)} service directories from {path}...", Colors.CYAN))
        else:
            print(Colors.colorize(f"[depvex] Checking whether {path}/requirements.txt is up to date...", Colors.CYAN))

        resolver = DependencyResolver()
        overall_ok = True

        for target in targets:
            output_path = Path(target) / "requirements.txt"
            if not output_path.exists():
                print(Colors.colorize(f"[depvex] No requirements.txt found for {target}. Run 'depvex scan .' first.", Colors.RED))
                overall_ok = False
                continue

            discovered = set()
            for dirpath, dirnames, filenames in __import__("os").walk(target):
                dirnames[:] = [directory for directory in dirnames if directory not in {".git", "__pycache__", ".venv", "venv", "node_modules"}]
                for filename in filenames:
                    if not filename.endswith(".py"):
                        continue
                    file_path = Path(dirpath) / filename
                    discovered.update(resolver._get_imports_for_file(str(file_path)))

            expected_requirements = [resolver.resolve(module_name, resolver.internet_check()) for module_name in sorted(discovered) if module_name]
            current_requirements = [line.strip() for line in output_path.read_text(encoding="utf-8").splitlines() if line.strip()]

            if set(expected_requirements) != set(current_requirements):
                print(Colors.colorize(f"[depvex] {target}/requirements.txt is out of date. Run 'depvex scan .' to update it.", Colors.YELLOW))
                overall_ok = False
            else:
                print(Colors.colorize(f"[depvex] {target}/requirements.txt is already up to date.", Colors.GREEN))

        return 0 if overall_ok else 1

    def watch(self, path: str, multi: str | None = None) -> None:
        targets = self._resolve_targets(path, multi)
        if len(targets) > 1:
            print(Colors.colorize(f"[depvex] Starting watch mode for {len(targets)} service directories from {path}...", Colors.CYAN))
        else:
            print(Colors.colorize(f"[depvex] Starting watch mode for {path}...", Colors.CYAN))
        print(Colors.colorize("[depvex] Depvex will keep scanning and updating requirements.txt as files change.", Colors.YELLOW))

        resolver = DependencyResolver()
        for target in targets:
            resolver.rebuild_requirements(target)
            watcher = ProjectWatcher(target, resolver=resolver)
            thread = threading.Thread(target=watcher.start, daemon=True)
            thread.start()

    def run(self, argv: list[str] | None = None) -> int:
        args = self.parser.parse_args(argv or sys.argv[1:])

        if args.command == "scan":
            return self.scan(args.path, multi=args.multi)

        if args.command == "check":
            return self.check(args.path, multi=args.multi)

        if args.command == "watch":
            self.watch(args.path, multi=args.multi)
            return 0

        self.parser.print_help()
        return 1

    def __call__(self, argv: list[str] | None = None) -> int:
        return self.run(argv)


def main(argv: list[str] | None = None) -> int:
    return DepvexCLI().run(argv)