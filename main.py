import sys
from pathlib import Path

# 支持直接 python main.py 和 python -m 往来占用统计.main 两种方式运行
if __name__ == "__main__" and __package__ is None:
    _parent = str(Path(__file__).resolve().parent.parent)
    if _parent not in sys.path:
        sys.path.insert(0, _parent)
    __package__ = "往来占用统计"

from .bootstrap import check_dependencies, configure_runtime
from .controller import FinanceController
from .excel_io import ExcelRepository
from .gui import FinanceView
from .pipeline import FinancePipeline
from .reporting import ReportBuilder


def main() -> int:
    status = check_dependencies(skip_install="--skip-install" in sys.argv)
    if status.failed:
        missing = ", ".join(status.failed)
        raise SystemExit(f"依赖安装失败: {missing}")
    cpu_count = configure_runtime()
    repository = ExcelRepository()
    view = FinanceView(excel_repository=repository)
    controller = FinanceController(
        pipeline=FinancePipeline(),
        report_builder=ReportBuilder(max_workers=cpu_count),
        excel_repository=repository,
        view=view,
    )
    controller.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
