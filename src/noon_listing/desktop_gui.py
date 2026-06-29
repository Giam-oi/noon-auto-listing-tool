from __future__ import annotations

import json
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from .batch import BatchItem, BatchRunner, parse_1688_urls, read_urls_from_excel
from .config import deep_merge, load_config, project_root
from .content_submit import submit_run_payloads
from .desktop_settings import (
    DesktopSettings,
    apply_settings_to_environment,
    default_desktop_settings_path,
    load_desktop_settings,
    save_desktop_settings,
    settings_to_config_override,
)
from .pipeline import ListingPipeline


SETTINGS_PATH = default_desktop_settings_path()


class NoonListingWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Noon 铺货助手")
        self.root.geometry("1100x720")
        self.event_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.settings = load_desktop_settings(SETTINGS_PATH)
        self._build_variables()
        self._build_layout()
        self._pump_events()

    def _build_variables(self) -> None:
        self.gemini_key = tk.StringVar(value=self.settings.gemini_api_key)
        self.gemini_model = tk.StringVar(value=self.settings.gemini_model)
        self.credentials_path = tk.StringVar(value=self.settings.noon_credentials_path)
        self.default_stock = tk.IntVar(value=self.settings.default_stock or 1000)
        self.auto_submit = tk.BooleanVar(value=self.settings.auto_submit)
        self.excel_path = tk.StringVar(value="")

    def _build_layout(self) -> None:
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.config_tab = ttk.Frame(notebook)
        self.links_tab = ttk.Frame(notebook)
        self.excel_tab = ttk.Frame(notebook)
        self.tasks_tab = ttk.Frame(notebook)
        self.results_tab = ttk.Frame(notebook)

        notebook.add(self.config_tab, text="1. 配置")
        notebook.add(self.links_tab, text="2. 批量链接")
        notebook.add(self.excel_tab, text="3. Excel 导入")
        notebook.add(self.tasks_tab, text="4. 任务")
        notebook.add(self.results_tab, text="5. 结果")

        self._build_config_tab()
        self._build_links_tab()
        self._build_excel_tab()
        self._build_tasks_tab()
        self._build_results_tab()

    def _build_config_tab(self) -> None:
        frame = ttk.Frame(self.config_tab, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Gemini API Key").grid(row=0, column=0, sticky=tk.W, pady=6)
        ttk.Entry(frame, textvariable=self.gemini_key, show="*", width=80).grid(row=0, column=1, sticky=tk.EW, pady=6)

        ttk.Label(frame, text="Gemini 模型").grid(row=1, column=0, sticky=tk.W, pady=6)
        ttk.Entry(frame, textvariable=self.gemini_model, width=40).grid(row=1, column=1, sticky=tk.W, pady=6)

        ttk.Label(frame, text="Noon API 凭证").grid(row=2, column=0, sticky=tk.W, pady=6)
        credentials_row = ttk.Frame(frame)
        credentials_row.grid(row=2, column=1, sticky=tk.EW, pady=6)
        credentials_row.columnconfigure(0, weight=1)
        ttk.Entry(credentials_row, textvariable=self.credentials_path).grid(row=0, column=0, sticky=tk.EW)
        ttk.Button(credentials_row, text="选择文件", command=self._choose_credentials).grid(row=0, column=1, padx=(8, 0))

        ttk.Label(frame, text="1688 Cookie").grid(row=3, column=0, sticky=tk.NW, pady=6)
        self.cookie_text = tk.Text(frame, height=5, wrap=tk.WORD)
        self.cookie_text.grid(row=3, column=1, sticky=tk.EW, pady=6)
        self.cookie_text.insert("1.0", self.settings.ali1688_cookie)

        ttk.Label(frame, text="默认库存").grid(row=4, column=0, sticky=tk.W, pady=6)
        ttk.Spinbox(frame, from_=0, to=999999, textvariable=self.default_stock, width=12).grid(row=4, column=1, sticky=tk.W, pady=6)

        ttk.Checkbutton(frame, text="达到条件后自动提交 Noon", variable=self.auto_submit).grid(row=5, column=1, sticky=tk.W, pady=6)

        ttk.Button(frame, text="保存配置", command=self._save_settings).grid(row=6, column=1, sticky=tk.W, pady=(16, 0))

    def _build_links_tab(self) -> None:
        frame = ttk.Frame(self.links_tab, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.urls_text = tk.Text(frame, wrap=tk.WORD)
        self.urls_text.grid(row=0, column=0, sticky=tk.NSEW)
        self.urls_text.insert("1.0", "一行一个 1688 商品链接，例如：https://detail.1688.com/offer/695867996979.html")
        button_row = ttk.Frame(frame)
        button_row.grid(row=1, column=0, sticky=tk.EW, pady=(10, 0))
        ttk.Button(button_row, text="开始批量采集", command=self._start_urls).pack(side=tk.LEFT)
        ttk.Button(button_row, text="清空", command=lambda: self.urls_text.delete("1.0", tk.END)).pack(side=tk.LEFT, padx=8)

    def _build_excel_tab(self) -> None:
        frame = ttk.Frame(self.excel_tab, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        frame.columnconfigure(0, weight=1)
        ttk.Label(frame, text="选择包含 1688 链接的 Excel 文件").grid(row=0, column=0, sticky=tk.W, pady=6)
        row = ttk.Frame(frame)
        row.grid(row=1, column=0, sticky=tk.EW, pady=6)
        row.columnconfigure(0, weight=1)
        ttk.Entry(row, textvariable=self.excel_path).grid(row=0, column=0, sticky=tk.EW)
        ttk.Button(row, text="选择 Excel", command=self._choose_excel).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(frame, text="导入并开始采集", command=self._start_excel).grid(row=2, column=0, sticky=tk.W, pady=(14, 0))

    def _build_tasks_tab(self) -> None:
        frame = ttk.Frame(self.tasks_tab, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.tasks = ttk.Treeview(frame, columns=("status", "run_dir", "error"), show="tree headings")
        self.tasks.heading("#0", text="1688 链接")
        self.tasks.heading("status", text="状态")
        self.tasks.heading("run_dir", text="结果目录")
        self.tasks.heading("error", text="错误")
        self.tasks.column("#0", width=420)
        self.tasks.column("status", width=110)
        self.tasks.column("run_dir", width=280)
        self.tasks.column("error", width=260)
        self.tasks.grid(row=0, column=0, sticky=tk.NSEW)
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.tasks.yview)
        scrollbar.grid(row=0, column=1, sticky=tk.NS)
        self.tasks.configure(yscrollcommand=scrollbar.set)

    def _build_results_tab(self) -> None:
        frame = ttk.Frame(self.results_tab, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.log_text = tk.Text(frame, wrap=tk.WORD, state=tk.DISABLED)
        self.log_text.grid(row=0, column=0, sticky=tk.NSEW)

    def _choose_credentials(self) -> None:
        path = filedialog.askopenfilename(title="选择 Noon api.json", filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if path:
            self.credentials_path.set(path)

    def _choose_excel(self) -> None:
        path = filedialog.askopenfilename(title="选择 Excel", filetypes=[("Excel", "*.xlsx *.xlsm"), ("All files", "*.*")])
        if path:
            self.excel_path.set(path)

    def _current_settings(self) -> DesktopSettings:
        return DesktopSettings(
            gemini_api_key=self.gemini_key.get().strip(),
            gemini_model=self.gemini_model.get().strip() or "gemini-3-flash-preview",
            noon_credentials_path=self.credentials_path.get().strip(),
            ali1688_cookie=self.cookie_text.get("1.0", tk.END).strip(),
            default_stock=int(self.default_stock.get() or 1000),
            auto_submit=bool(self.auto_submit.get()),
        )

    def _save_settings(self) -> DesktopSettings:
        settings = self._current_settings()
        save_desktop_settings(settings, SETTINGS_PATH)
        self.settings = settings
        self._log(f"配置已保存到 {SETTINGS_PATH}")
        return settings

    def _start_urls(self) -> None:
        urls = parse_1688_urls(self.urls_text.get("1.0", tk.END))
        if not urls:
            messagebox.showwarning("没有链接", "请粘贴至少一个有效的 1688 商品链接。")
            return
        self._start_batch(urls)

    def _start_excel(self) -> None:
        path = self.excel_path.get().strip()
        if not path:
            messagebox.showwarning("没有文件", "请先选择 Excel 文件。")
            return
        try:
            urls = read_urls_from_excel(path)
        except Exception as exc:
            messagebox.showerror("读取失败", str(exc))
            return
        if not urls:
            messagebox.showwarning("没有链接", "Excel 里没有识别到有效 1688 商品链接。")
            return
        self._start_batch(urls)

    def _start_batch(self, urls: list[str]) -> None:
        settings = self._save_settings()
        apply_settings_to_environment(settings)
        self.tasks.delete(*self.tasks.get_children())
        for url in urls:
            self.tasks.insert("", tk.END, iid=url, text=url, values=("pending", "", ""))
        self._log(f"开始批量任务，共 {len(urls)} 个链接。")
        thread = threading.Thread(target=self._run_batch_worker, args=(urls, settings), daemon=True)
        thread.start()

    def _run_batch_worker(self, urls: list[str], settings: DesktopSettings) -> None:
        try:
            cfg = deep_merge(load_config(), settings_to_config_override(settings))

            def make_pipeline() -> ListingPipeline:
                return ListingPipeline(cfg)

            runner = BatchRunner(make_pipeline)
            result = runner.run_urls(urls, progress_callback=lambda item: self.event_queue.put(("item", item)))
            self.event_queue.put(("result", result.to_dict()))

            if settings.auto_submit:
                self._submit_successful_runs(result.to_dict(), cfg, settings)
        except Exception as exc:
            self.event_queue.put(("error", str(exc)))

    def _submit_successful_runs(self, result: dict[str, Any], cfg: dict[str, Any], settings: DesktopSettings) -> None:
        credentials = settings.noon_credentials_path.strip()
        if not credentials:
            self.event_queue.put(("log", "已勾选自动提交，但未配置 Noon API 凭证，跳过提交。"))
            return
        for item in result["items"]:
            if item["status"] != "succeeded" or not item["run_dir"]:
                continue
            try:
                submit_result = submit_run_payloads(Path(item["run_dir"]), cfg, Path(credentials), live=True, force=False)
                self.event_queue.put(("log", f"Noon 提交完成：{json.dumps(submit_result, ensure_ascii=False)}"))
            except Exception as exc:
                self.event_queue.put(("log", f"Noon 提交失败：{item['source']} - {exc}"))

    def _pump_events(self) -> None:
        while True:
            try:
                event, payload = self.event_queue.get_nowait()
            except queue.Empty:
                break
            if event == "item":
                self._update_item(payload)
            elif event == "result":
                self._log(json.dumps(payload, ensure_ascii=False, indent=2))
            elif event == "log":
                self._log(str(payload))
            elif event == "error":
                self._log(f"任务失败：{payload}")
                messagebox.showerror("任务失败", str(payload))
        self.root.after(250, self._pump_events)

    def _update_item(self, item: BatchItem) -> None:
        if not self.tasks.exists(item.source):
            self.tasks.insert("", tk.END, iid=item.source, text=item.source)
        self.tasks.item(item.source, values=(item.status, item.run_dir, item.error))
        if item.status in {"succeeded", "failed"}:
            self._log(f"{item.status}: {item.source} {item.run_dir or item.error}")

    def _log(self, message: str) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, message.rstrip() + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)


def main() -> int:
    root = tk.Tk()
    NoonListingWindow(root)
    root.mainloop()
    return 0
