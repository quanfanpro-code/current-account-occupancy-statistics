from __future__ import annotations

import queue
import threading
import time
import traceback


class UserCancelledError(Exception):
    pass


class FinanceController:
    def __init__(self, pipeline, report_builder, excel_repository, view):
        self.pipeline = pipeline
        self.report_builder = report_builder
        self.excel_repository = excel_repository
        self.view = view
        self.view.bind_actions(self.start_processing, self.cancel_processing)
        self.msg_queue: queue.Queue = queue.Queue()
        self._cancel_requested = False
        self._worker_thread = None

    def run(self) -> None:
        self.view.mainloop()

    def start_processing(self) -> None:
        try:
            config = self.view.build_process_config()
        except ValueError as exc:
            self.view.show_error("配置错误", str(exc))
            return
        self._cancel_requested = False
        self.view.set_running(True)
        self.view.append_log("开始处理数据...")
        self._worker_thread = threading.Thread(target=self.worker, args=(config,), daemon=True)
        self._worker_thread.start()
        self.view.root.after(100, self.check_queue)

    def cancel_processing(self) -> None:
        self._cancel_requested = True
        self.view.append_log("已发出取消指令...")

    def worker(self, config) -> None:
        def callback(percent, message, phase=None):
            if self._cancel_requested:
                raise UserCancelledError("任务已被用户取消。")
            self.msg_queue.put(("progress", percent, message, phase))

        try:
            start_time = time.perf_counter()
            callback(0, "正在读取Excel文件", "数据读取阶段")
            df_balance, df_trans = self.excel_repository.read_dataframes(config)
            df_balance, df_trans = self.pipeline.preprocess_data(df_balance, df_trans, config, callback)
            trans_count = len(df_trans)
            balance_result, supplier_columns, new_suppliers = self.pipeline.calculate_balances(df_balance, df_trans, config, callback)
            total_suppliers = len(supplier_columns) + len(new_suppliers)
            total_days = len(balance_result)
            bundle = self.report_builder.build_bundle(balance_result, supplier_columns, new_suppliers, callback)
            output_path = config.build_output_path()
            self.excel_repository.save_results(output_path, bundle.to_sheet_map(), callback)
            elapsed = time.perf_counter() - start_time
            summary = (
                f"处理完成：共 {total_suppliers} 家往来单位，"
                f"{total_days} 天，"
                f"{trans_count} 条交易记录，"
                f"耗时 {elapsed:.1f} 秒"
            )
            self.msg_queue.put(("success", output_path, summary))
        except UserCancelledError as exc:
            self.msg_queue.put(("cancelled", str(exc)))
        except Exception:
            self.msg_queue.put(("error", traceback.format_exc()))

    def check_queue(self) -> None:
        try:
            while True:
                message = self.msg_queue.get_nowait()
                message_type = message[0]
                if message_type == "progress":
                    self.view.update_progress(message[1], message[2], message[3])
                elif message_type == "success":
                    summary = message[2] if len(message) > 2 else None
                    self.view.show_success(message[1], summary)
                    return
                elif message_type == "cancelled":
                    self.view.show_cancelled(message[1])
                    return
                elif message_type == "error":
                    self.view.show_error("运行错误", message[1])
                    return
        except queue.Empty:
            self.view.root.after(100, self.check_queue)
