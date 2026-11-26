"""python -m staticbuild [--only core,news,...] [--out DIR] [--fixtures]

Runs every exporter module's build(ctx) (core first, the rest alphabetical), then writes data/manifest.json.
With --fixtures it also writes web/tests/fixtures (see fixtures.py)."""

import argparse
import hashlib
import importlib
import pkgutil
import sys

import staticbuild
from staticbuild import common

NOT_EXPORTERS = {"common", "validate", "fixtures"}
PUBLISHED = ("data", "api", "files")  # folders the manifest lists


def exporters(only: list[str] | None) -> list:
    names = sorted(m.name for m in pkgutil.iter_modules(staticbuild.__path__)
                   if not m.name.startswith("_") and m.name not in NOT_EXPORTERS)
    names.sort(key=lambda n: n != "core")
    if only:
        unknown = set(only) - set(names)
        if unknown:
            sys.exit(f"unknown exporter: {', '.join(sorted(unknown))} (have: {', '.join(names)})")
        names = [n for n in names if n in only]
    return [importlib.import_module(f"staticbuild.{n}") for n in names]


def write_manifest(ctx) -> None:
    files = {}
    for folder in PUBLISHED:
        for path in sorted((ctx.web / folder).rglob("*")):
            if path.is_file() and path.name != "manifest.json":
                blob = path.read_bytes()
                files[path.relative_to(ctx.web).as_posix()] = {"bytes": len(blob), "sha1": hashlib.sha1(blob).hexdigest()}
    ctx.write_json("data/manifest.json", {"built": ctx.built, "files": files})


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="staticbuild")
    ap.add_argument("--only", help="comma-separated exporters, e.g. core,news")
    ap.add_argument("--out", help="output root instead of web/")
    ap.add_argument("--fixtures", action="store_true", help="also write web/tests/fixtures")
    args = ap.parse_args(argv)
    mods = exporters(args.only.split(",") if args.only else None)
    if "core" not in {m.__name__.split(".")[-1] for m in mods}:
        common.keep_site_year(args.out)
    ctx = common.load(args.out)
    for mod in mods:
        print(f"build {mod.__name__.split('.')[-1]}", flush=True)
        mod.build(ctx)
    if args.fixtures:
        from staticbuild import fixtures

        fixtures.build(ctx)
    write_manifest(ctx)


main()
