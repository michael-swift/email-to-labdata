#!/usr/bin/env python3
"""Clear all Python cache files and pytest cache to force fresh imports."""

import os
import shutil
from pathlib import Path


def main():
    project_root = Path(__file__).parent
    print(f"Clearing caches in: {project_root}")

    # Count files for reporting
    pyc_count = 0
    pycache_count = 0

    # Remove .pyc files and __pycache__ directories
    for pycache_dir in project_root.rglob("__pycache__"):
        try:
            # Count .pyc files before removal
            pyc_files = list(pycache_dir.glob("*.pyc"))
            pyc_count += len(pyc_files)

            # Remove the entire __pycache__ directory
            shutil.rmtree(pycache_dir)
            pycache_count += 1
            print(f"  Removed: {pycache_dir.relative_to(project_root)}")
        except Exception as e:
            print(f"  Warning: Could not remove {pycache_dir}: {e}")

    # Remove .pytest_cache
    pytest_cache = project_root / ".pytest_cache"
    if pytest_cache.exists():
        try:
            shutil.rmtree(pytest_cache)
            print(f"  Removed: .pytest_cache")
        except Exception as e:
            print(f"  Warning: Could not remove .pytest_cache: {e}")

    # Remove any .coverage files
    for coverage_file in project_root.glob(".coverage*"):
        try:
            coverage_file.unlink()
            print(f"  Removed: {coverage_file.name}")
        except Exception as e:
            print(f"  Warning: Could not remove {coverage_file}: {e}")

    # Remove htmlcov directory if it exists
    htmlcov = project_root / "htmlcov"
    if htmlcov.exists():
        try:
            shutil.rmtree(htmlcov)
            print(f"  Removed: htmlcov/")
        except Exception as e:
            print(f"  Warning: Could not remove htmlcov: {e}")

    print(f"\nSummary:")
    print(f"  - Removed {pycache_count} __pycache__ directories")
    print(f"  - Removed {pyc_count} .pyc files")
    print(f"  - Cleared pytest and coverage caches")
    print("\nCache clearing complete!")


if __name__ == "__main__":
    main()
