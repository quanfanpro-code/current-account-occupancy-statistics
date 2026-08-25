from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    import customtkinter as ctk
    USE_CUSTOMTKINTER = True
except ImportError:  # pragma: no cover
    ctk = None
    USE_CUSTOMTKINTER = False

from .config import AppMetadata, UiConfig
from .models import ProcessConfig


class ProgressAdapter:
    def __init__(self, progress_widget, label_widget, use_customtkinter: bool):
        self.progress_widget = progress_widget
        self.label_widget = label_widget
        self.use_customtkinter = use_customtkinter

    def set_value(self, percent: float, text: str) -> None:
        if self.use_customtkinter:
            self.progress_widget.set(percent / 100.0)
        else:
            self.progress_widget["value"] = percent
        self.label_widget.configure(text=text)

    def set_success(self, text: str) -> None:
        if self.use_customtkinter:
            self.progress_widget.set(1.0)
            self.label_widget.configure(text=text, text_color="green")
        else:
            self.progress_widget["value"] = 100
            self.label_widget.configure(text=text, foreground="green")


class FinanceView:
    """往来占用统计分析系统 - 主界面

    布局结构（按 desktop-gui-style 规范）：
    ┌─────────────────────────────────┐
    │ 页眉卡片：标题 + 版本            │
    ├─────────────────────────────────┤
    │ 输入卡片：序时账 + 余额表        │
    ├─────────────────────────────────┤
    │ 列映射卡片：4个列下拉框           │
    ├─────────────────────────────────┤
    │ 执行卡片：主按钮 + 进度条 + 状态  │
    ├─────────────────────────────────┤
    │ 日志卡片：日志文本框 + 复制按钮   │
    └─────────────────────────────────┘
    """

    def __init__(self, excel_repository, use_customtkinter: bool | None = None):
        self.excel_repository = excel_repository
        self.use_customtkinter = USE_CUSTOMTKINTER if use_customtkinter is None else use_customtkinter
        self.metadata = AppMetadata()
        self.ui_config = UiConfig()
        self._is_running = False

        self.root = ctk.CTk() if self.use_customtkinter else tk.Tk()
        self.root.title(self.metadata.name)
        self.root.geometry(self.ui_config.main_window_size)
        self.root.minsize(800, 600)
        # 注册窗口关闭协议，防止处理过程中直接关闭导致文件损坏
        self.root.protocol("WM_DELETE_WINDOW", self._on_exit)

        self.trans_path_var = tk.StringVar()
        self.balance_path_var = tk.StringVar()
        self.trans_sheet_var = tk.StringVar()
        self.balance_sheet_var = tk.StringVar()
        self.col_name_var = tk.StringVar()
        self.col_debit_var = tk.StringVar()
        self.col_credit_var = tk.StringVar()
        self.col_date_var = tk.StringVar()

        self.trans_columns: list[str] = []
        self.start_callback = None
        self.cancel_callback = None
        self._build_ui()

    # ============================================================
    # UI 构建
    # ============================================================

    def _build_ui(self) -> None:
        if self.use_customtkinter:
            ctk.set_appearance_mode("system")
            ctk.set_default_color_theme("blue")
        self._build_main_frame()
        self.progress_adapter = ProgressAdapter(self.progress_bar, self.progress_label, self.use_customtkinter)
        self.set_running(False)

    def _build_main_frame(self) -> None:
        """构建主框架，使用 grid 实现精确布局"""
        if self.use_customtkinter:
            main = ctk.CTkFrame(self.root, fg_color="transparent")
        else:
            main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)

        # 按从上到下的顺序构建 5 张卡片
        self._build_header_card(main)
        self._build_input_card(main)
        self._build_mapping_card(main)
        self._build_action_card(main)
        self._build_log_card(main)

    # ----------------------------------------------------------
    # 页眉卡片
    # ----------------------------------------------------------

    def _build_header_card(self, parent) -> None:
        if self.use_customtkinter:
            card = ctk.CTkFrame(parent)
        else:
            card = ttk.Frame(parent, relief="groove", borderwidth=1)
        card.pack(fill="x", pady=(0, 6))

        if self.use_customtkinter:
            ctk.CTkLabel(
                card,
                text=self.metadata.name,
                font=ctk.CTkFont(size=20, weight="bold"),
            ).pack(side="left", padx=15, pady=8)
            ctk.CTkLabel(
                card,
                text=f"{self.metadata.version}  {self.metadata.version_date}",
                font=ctk.CTkFont(size=12),
                text_color="gray",
            ).pack(side="right", padx=15, pady=8)
        else:
            ttk.Label(
                card, text=self.metadata.name, font=("Microsoft YaHei UI", 16, "bold"),
            ).pack(side="left", padx=12, pady=6)
            ttk.Label(
                card, text=f"{self.metadata.version}  {self.metadata.version_date}",
                font=("Microsoft YaHei UI", 9), foreground="gray",
            ).pack(side="right", padx=12, pady=6)

    # ----------------------------------------------------------
    # 输入卡片（序时账 + 余额表）
    # ----------------------------------------------------------

    def _build_input_card(self, parent) -> None:
        if self.use_customtkinter:
            card = ctk.CTkFrame(parent)
        else:
            card = ttk.LabelFrame(parent, text=" 数据导入 ", padding=8)
        card.pack(fill="x", pady=4)

        if self.use_customtkinter:
            ctk.CTkLabel(card, text="数据导入", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=(8, 4))

        self._build_file_row(card, "发生额序时账", self.trans_path_var, self.trans_sheet_var, "trans")
        self._build_file_row(card, "期初余额表(可选)", self.balance_path_var, self.balance_sheet_var, "balance")

    def _build_file_row(self, parent, label_text, path_var, sheet_var, file_type) -> None:
        """一行：标签 + 路径框 + 浏览按钮 + Sheet选择"""
        if self.use_customtkinter:
            row = ctk.CTkFrame(parent, fg_color="transparent")
        else:
            row = ttk.Frame(parent)
        row.pack(fill="x", padx=15, pady=3)

        if self.use_customtkinter:
            ctk.CTkLabel(row, text=f"{label_text}:", width=100, anchor="w").pack(side="left", padx=(0, 6))
            ctk.CTkEntry(row, textvariable=path_var, width=320).pack(side="left", padx=2)
            ctk.CTkButton(row, text="浏览", command=lambda: self.browse_file(file_type), width=60, fg_color="#4a90d9").pack(side="left", padx=4)
            ctk.CTkLabel(row, text="Sheet:").pack(side="left", padx=(10, 4))
            combo = ctk.CTkComboBox(row, values=[""], variable=sheet_var, width=150)
            combo.pack(side="left", padx=2)
        else:
            ttk.Label(row, text=f"{label_text}:", width=12, anchor="w").pack(side="left", padx=(0, 4))
            ttk.Entry(row, textvariable=path_var, width=40).pack(side="left", padx=2)
            ttk.Button(row, text="浏览", command=lambda: self.browse_file(file_type), width=6).pack(side="left", padx=4)
            ttk.Label(row, text="Sheet:").pack(side="left", padx=(8, 2))
            combo = ttk.Combobox(row, textvariable=sheet_var, width=18, state="readonly")
            combo.pack(side="left", padx=2)

        if file_type == "trans":
            self.trans_sheet_combo = combo
            if self.use_customtkinter:
                combo.configure(command=lambda _v: self._refresh_trans_columns())
            else:
                combo.bind("<<ComboboxSelected>>", lambda _: self._refresh_trans_columns())
        else:
            self.balance_sheet_combo = combo

    # ----------------------------------------------------------
    # 列映射卡片
    # ----------------------------------------------------------

    def _build_mapping_card(self, parent) -> None:
        if self.use_customtkinter:
            card = ctk.CTkFrame(parent)
        else:
            card = ttk.LabelFrame(parent, text=" 列映射配置 ", padding=8)
        card.pack(fill="x", pady=4)

        if self.use_customtkinter:
            ctk.CTkLabel(card, text="列映射配置", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=(8, 4))

        if self.use_customtkinter:
            row = ctk.CTkFrame(card, fg_color="transparent")
        else:
            row = ttk.Frame(card)
        row.pack(fill="x", padx=15, pady=(0, 10))

        self.col_name_combo = self._add_combo(row, "往来单位", self.col_name_var)
        self.col_debit_combo = self._add_combo(row, "借方发生额", self.col_debit_var)
        self.col_credit_combo = self._add_combo(row, "贷方发生额", self.col_credit_var)
        self.col_date_combo = self._add_combo(row, "记账日期", self.col_date_var)

    def _add_combo(self, parent, label_text, variable):
        if self.use_customtkinter:
            ctk.CTkLabel(parent, text=f"{label_text}:", width=80, anchor="w").pack(side="left", padx=(0, 2))
            combo = ctk.CTkComboBox(parent, values=[""], variable=variable, width=130)
            combo.pack(side="left", padx=(0, 14))
        else:
            ttk.Label(parent, text=f"{label_text}:", width=10, anchor="w").pack(side="left", padx=(0, 2))
            combo = ttk.Combobox(parent, textvariable=variable, width=16, state="readonly")
            combo.pack(side="left", padx=(0, 10))
        return combo

    # ----------------------------------------------------------
    # 执行卡片（主按钮 + 进度 + 状态 + 退出）
    # ----------------------------------------------------------

    def _build_action_card(self, parent) -> None:
        if self.use_customtkinter:
            card = ctk.CTkFrame(parent)
        else:
            card = ttk.Frame(parent, relief="groove", borderwidth=1)
        card.pack(fill="x", pady=6)

        # 上排：主按钮区
        if self.use_customtkinter:
            btn_row = ctk.CTkFrame(card, fg_color="transparent")
        else:
            btn_row = ttk.Frame(card)
        btn_row.pack(fill="x", padx=15, pady=(10, 6))

        if self.use_customtkinter:
            self.start_button = ctk.CTkButton(
                btn_row, text="▶ 开始处理", command=self._on_start_clicked,
                width=140, height=36, font=ctk.CTkFont(size=13, weight="bold"),
                fg_color="#2ecc71", hover_color="#27ae60",
            )
            self.start_button.pack(side="left", padx=(0, 8))
            self.cancel_button = ctk.CTkButton(
                btn_row, text="取消处理", command=self._on_cancel_clicked,
                width=100, height=36,
            )
            self.cancel_button.pack(side="left", padx=(0, 8))
            ctk.CTkButton(
                btn_row, text="退出", command=self._on_exit, width=70, height=36,
                fg_color="transparent", border_width=1, text_color="gray",
            ).pack(side="right")
        else:
            self.start_button = ttk.Button(btn_row, text="▶ 开始处理", command=self._on_start_clicked, width=16)
            self.start_button.pack(side="left", padx=(0, 6))
            self.cancel_button = ttk.Button(btn_row, text="取消处理", command=self._on_cancel_clicked, width=10)
            self.cancel_button.pack(side="left", padx=(0, 6))
            ttk.Button(btn_row, text="退出", command=self._on_exit, width=6).pack(side="right")

        # 下排：进度条 + 状态文字
        if self.use_customtkinter:
            prog_row = ctk.CTkFrame(card, fg_color="transparent")
        else:
            prog_row = ttk.Frame(card)
        prog_row.pack(fill="x", padx=15, pady=(0, 10))

        if self.use_customtkinter:
            self.progress_bar = ctk.CTkProgressBar(prog_row, width=400)
            self.progress_bar.pack(side="left", padx=(0, 10))
            self.progress_bar.set(0)
            self.progress_label = ctk.CTkLabel(prog_row, text="就绪")
        else:
            self.progress_bar = ttk.Progressbar(prog_row, length=400, maximum=100)
            self.progress_bar.pack(side="left", padx=(0, 10))
            self.progress_label = ttk.Label(prog_row, text="就绪")
        self.progress_label.pack(side="left")

    # ----------------------------------------------------------
    # 日志卡片
    # ----------------------------------------------------------

    def _build_log_card(self, parent) -> None:
        if self.use_customtkinter:
            card = ctk.CTkFrame(parent)
        else:
            card = ttk.LabelFrame(parent, text=" 日志输出 ", padding=4)
        card.pack(fill="both", expand=True, pady=(4, 0))

        # 日志头部：标题 + 复制按钮
        if self.use_customtkinter:
            header = ctk.CTkFrame(card, fg_color="transparent")
        else:
            header = ttk.Frame(card)
        header.pack(fill="x", padx=15, pady=(8, 2))

        if self.use_customtkinter:
            ctk.CTkLabel(header, text="日志输出", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
            ctk.CTkButton(
                header, text="复制日志", command=self.copy_log, width=80,
                fg_color="transparent", border_width=1, text_color="gray",
            ).pack(side="right")
            self.log_text = ctk.CTkTextbox(card, height=200)
        else:
            ttk.Label(header, text="日志输出", font=("Microsoft YaHei UI", 10, "bold")).pack(side="left")
            ttk.Button(header, text="复制日志", command=self.copy_log, width=8).pack(side="right")
            self.log_text = tk.Text(card, height=200, wrap="word")

        self.log_text.pack(fill="both", expand=True, padx=15, pady=(2, 10))
        self.log_text.configure(state="disabled")

    # ============================================================
    # 事件处理
    # ============================================================

    def _on_exit(self) -> None:
        """退出按钮：处理中需确认"""
        if self._is_running:
            if not messagebox.askyesno("确认退出", "正在处理中，确定要退出吗？\n退出后可能留下不完整的结果文件。"):
                return
        self.root.destroy()

    def bind_actions(self, start_callback, cancel_callback) -> None:
        self.start_callback = start_callback
        self.cancel_callback = cancel_callback

    def browse_file(self, file_type: str) -> None:
        title = "请选择Excel文件"
        path = filedialog.askopenfilename(title=title, filetypes=[("Excel files", "*.xlsx *.xlsm")])
        if not path:
            return
        if file_type == "trans":
            self.trans_path_var.set(path)
            self._set_sheet_values(self.trans_sheet_combo, self.trans_sheet_var, self.excel_repository.get_sheet_names(path))
            self._refresh_trans_columns()
        else:
            self.balance_path_var.set(path)
            self._set_sheet_values(self.balance_sheet_combo, self.balance_sheet_var, self.excel_repository.get_sheet_names(path))

    def _set_sheet_values(self, combo, variable, values: list[str]) -> None:
        values = values or [""]
        if self.use_customtkinter:
            combo.configure(values=values)
            combo.set(values[0])
        else:
            combo["values"] = values
            combo.set(values[0])
        variable.set(values[0])

    def _refresh_trans_columns(self) -> None:
        file_path = self.trans_path_var.get()
        sheet_name = self.trans_sheet_var.get()
        if not file_path or not sheet_name:
            return
        self.trans_columns = self.excel_repository.get_columns(file_path, sheet_name)
        values = self.trans_columns or [""]
        for combo in [self.col_name_combo, self.col_debit_combo, self.col_credit_combo, self.col_date_combo]:
            if self.use_customtkinter:
                combo.configure(values=values)
            else:
                combo["values"] = values
        self._auto_fill_mapping()

    def _auto_fill_mapping(self) -> None:
        mapping = {
            self.col_name_var: ["核算项目名称", "单位名称", "客户", "供应商", "往来单位"],
            self.col_debit_var: ["借方发生额", "借方", "借方金额"],
            self.col_credit_var: ["贷方发生额", "贷方", "贷方金额"],
            self.col_date_var: ["记账时间", "日期", "业务日期", "凭证日期"],
        }
        for variable, keywords in mapping.items():
            for column in self.trans_columns:
                if any(keyword in str(column) for keyword in keywords):
                    variable.set(str(column))
                    break

    def build_process_config(self) -> ProcessConfig:
        config = ProcessConfig(
            trans_file=self.trans_path_var.get().strip(),
            trans_sheet=self.trans_sheet_var.get().strip(),
            balance_file=self.balance_path_var.get().strip(),
            balance_sheet=self.balance_sheet_var.get().strip(),
            output_dir=os.path.dirname(self.balance_path_var.get().strip() or self.trans_path_var.get().strip()),
            col_name=self.col_name_var.get().strip(),
            col_debit=self.col_debit_var.get().strip(),
            col_credit=self.col_credit_var.get().strip(),
            col_date=self.col_date_var.get().strip(),
        )
        config.validate()
        for field_name in ["trans_file", "balance_file"]:
            file_path = getattr(config, field_name)
            # 期初余额表可选，留空时跳过存在性检查
            if file_path and not os.path.isfile(file_path):
                raise ValueError(f"文件不存在: {file_path}")
        return config

    def _on_start_clicked(self) -> None:
        if callable(self.start_callback):
            self.start_callback()

    def _on_cancel_clicked(self) -> None:
        if callable(self.cancel_callback):
            self.cancel_callback()

    def set_running(self, running: bool) -> None:
        self._is_running = running
        start_state = "disabled" if running else "normal"
        cancel_state = "normal" if running else "disabled"
        if self.use_customtkinter:
            self.start_button.configure(state=start_state)
            self.cancel_button.configure(state=cancel_state)
        else:
            self.start_button.configure(state=start_state)
            self.cancel_button.configure(state=cancel_state)

    def update_progress(self, percent: float, message: str, phase: str | None = None) -> None:
        text = f"[{phase}] {percent:.0f}% - {message}" if phase else f"{percent:.0f}% - {message}"
        self.progress_adapter.set_value(percent, text)
        self.append_log(text)

    def append_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def copy_log(self) -> None:
        self.log_text.configure(state="normal")
        content = self.log_text.get("1.0", "end-1c")
        self.log_text.configure(state="disabled")
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        messagebox.showinfo("提示", "日志已复制到剪贴板")

    def show_success(self, output_path: str, summary: str | None = None) -> None:
        self.progress_adapter.set_success("处理完成")
        if summary:
            self.append_log(summary)
        self.append_log(f"文件已保存至: {output_path}")
        self.set_running(False)

    def show_error(self, title: str, message: str) -> None:
        self.append_log(f"[错误] {message}")
        self.set_running(False)
        # 弹窗只显示简短提示，详细错误信息在日志区查看（可复制）
        messagebox.showerror(title, f"{title}，详细信息请查看日志区域。")

    def show_cancelled(self, message: str) -> None:
        self.append_log(f"[取消] {message}")
        self.set_running(False)
        messagebox.showinfo("已取消", message)

    def mainloop(self) -> None:
        self.root.mainloop()
