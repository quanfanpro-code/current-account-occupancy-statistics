import importlib.util
import multiprocessing
import os
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class DependencyStatus:
    missing: list[str]
    installed_now: list[str]
    failed: list[str]


def check_dependencies(skip_install: bool = False, auto_install: bool = True) -> DependencyStatus:
    required = {
        "pandas": "pandas",
        "openpyxl": "openpyxl",
        "xlsxwriter": "xlsxwriter",
    }
    missing = [package for module, package in required.items() if importlib.util.find_spec(module) is None]
    installed_now: list[str] = []
    failed: list[str] = []
    if missing and not skip_install and auto_install:
        for package in missing:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", package, "--disable-pip-version-check"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                installed_now.append(package)
            else:
                failed.append(package)
        # 安装成功后从 missing 中移除，使其反映安装后的真实状态
        missing = [p for p in missing if p not in installed_now]
    return DependencyStatus(missing=missing, installed_now=installed_now, failed=failed)


def configure_runtime(max_workers: int | None = None) -> int:
    cpu_count = max_workers or max(1, multiprocessing.cpu_count())
    os.environ.setdefault("OMP_NUM_THREADS", str(cpu_count))
    os.environ.setdefault("MKL_NUM_THREADS", str(cpu_count))
    os.environ.setdefault("OPENBLAS_NUM_THREADS", str(cpu_count))
    return cpu_count
