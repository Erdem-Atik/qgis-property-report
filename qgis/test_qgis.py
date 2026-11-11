"""Smoke test: initialise headless QGIS and print version info.

Run inside the container:
    docker compose run --rm qgis
Exits with code 0 on success, 1 on failure.
"""
import os
import sys


def main() -> int:
    try:
        from qgis.core import Qgis, QgsApplication, QgsProviderRegistry
    except ImportError as exc:
        print(f"ERROR: cannot import PyQGIS: {exc}", file=sys.stderr)
        return 1

    qgs = QgsApplication([], False)
    qgs.setPrefixPath("/usr", True)
    qgs.initQgis()
    try:
        providers = QgsProviderRegistry.instance().providerList()
        print(f"QGIS version:    {Qgis.version()} ({Qgis.versionInt()})")
        print(f"Python version:  {sys.version.split()[0]}")
        print(f"QT_QPA_PLATFORM: {os.environ.get('QT_QPA_PLATFORM', '<not set>')}")
        print(f"Data providers:  {len(providers)} ({', '.join(sorted(providers)[:6])}, ...)")
        if not providers:
            print("ERROR: no data providers registered", file=sys.stderr)
            return 1
        print("OK: headless QGIS is working.")
        return 0
    finally:
        qgs.exitQgis()


if __name__ == "__main__":
    sys.exit(main())
