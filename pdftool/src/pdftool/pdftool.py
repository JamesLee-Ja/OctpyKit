import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinterdnd2 import *
from pypdf import PdfReader, PdfWriter


class PdfToolApp(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title("PDFツール")
        self.geometry("800x680")
        self.minsize(800, 680)

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.merge_tab = tk.Frame(notebook)
        self.split_tab = tk.Frame(notebook)
        notebook.add(self.merge_tab, text="結合")
        notebook.add(self.split_tab, text="分割")

        self.merge_files = []
        self.merge_output_path = tk.StringVar(value="")
        self._build_merge_tab()

        self.split_file = tk.StringVar(value="")
        self.split_mode = tk.StringVar(value="per_page")
        self.split_ranges = tk.StringVar(value="")
        self.split_output_dir = tk.StringVar(value="")
        self._build_split_tab()

    # ---------------- 結合タブ ----------------
    def _build_merge_tab(self):
        parent = self.merge_tab

        drop_label = tk.Label(
            parent,
            text="ここにPDFファイルをドラッグ＆ドロップしてください（複数可）\nまたは下のボタンをクリックして選択",
            bg="#e0f0ff",
            fg="#333",
            font=("Meiryo", 12),
            width=70,
            height=6,
            relief="groove",
            justify="center"
        )
        drop_label.pack(pady=15, padx=20, fill="x")
        drop_label.drop_target_register(DND_FILES)
        drop_label.dnd_bind('<<Drop>>', self._on_merge_drop)

        select_frame = tk.Frame(parent)
        select_frame.pack(pady=(0, 8), padx=20, fill="x")
        tk.Button(select_frame, text="PDFファイルを選択", width=18, height=2,
                  font=("Meiryo", 10), command=self._select_merge_files).pack(side="left", padx=10)

        self.merge_status = tk.Label(parent, text="準備完了", fg="gray", font=("Meiryo", 9))
        self.merge_status.pack(side="bottom", pady=6)

        merge_btn_frame = tk.Frame(parent)
        merge_btn_frame.pack(side="bottom", pady=10, padx=20, fill="x")
        tk.Button(merge_btn_frame, text="結合開始", width=16, height=2, bg="#4CAF50", fg="white",
                  font=("Meiryo", 10, "bold"), command=self._start_merge).pack(side="left", padx=10)

        out_frame = tk.Frame(parent)
        out_frame.pack(side="bottom", pady=(4, 0), padx=20, fill="x")
        tk.Label(out_frame, text="出力ファイル：", font=("Meiryo", 10), width=12, anchor="w").pack(side="left")
        tk.Entry(out_frame, textvariable=self.merge_output_path, width=45, font=("Meiryo", 10),
                 state="readonly").pack(side="left", padx=6)
        tk.Button(out_frame, text="参照...", font=("Meiryo", 9),
                  command=self._select_merge_output).pack(side="left", padx=6)

        list_frame = tk.Frame(parent)
        list_frame.pack(pady=5, padx=20, fill="both", expand=True)
        tk.Label(list_frame, text="結合する順番（上から下へ結合されます）：", font=("Meiryo", 10)).pack(anchor="w")

        inner = tk.Frame(list_frame)
        inner.pack(fill="both", expand=True)

        self.merge_listbox = tk.Listbox(inner, font=("Meiryo", 10), height=10)
        scrollbar = tk.Scrollbar(inner, orient="vertical", command=self.merge_listbox.yview)
        self.merge_listbox.configure(yscrollcommand=scrollbar.set)
        self.merge_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        order_frame = tk.Frame(list_frame)
        order_frame.pack(fill="x", pady=6)
        tk.Button(order_frame, text="↑ 上へ", width=10, font=("Meiryo", 9),
                  command=self._merge_move_up).pack(side="left", padx=4)
        tk.Button(order_frame, text="↓ 下へ", width=10, font=("Meiryo", 9),
                  command=self._merge_move_down).pack(side="left", padx=4)
        tk.Button(order_frame, text="選択削除", width=10, font=("Meiryo", 9),
                  command=self._merge_remove_selected).pack(side="left", padx=4)
        tk.Button(order_frame, text="全てクリア", width=10, font=("Meiryo", 9),
                  command=self._merge_clear).pack(side="left", padx=4)

    def _on_merge_drop(self, event):
        dropped = self.tk.splitlist(event.data)
        for path in dropped:
            if os.path.isfile(path) and path.lower().endswith(".pdf") and path not in self.merge_files:
                self.merge_files.append(path)
                self.merge_listbox.insert(tk.END, os.path.basename(path))
        self.merge_status.config(text=f"{len(self.merge_files)} 個のファイルを追加しました")

    def _select_merge_files(self):
        files = filedialog.askopenfilenames(title="PDFファイルを選択", filetypes=[("PDFファイル", "*.pdf")])
        for path in files:
            if path not in self.merge_files:
                self.merge_files.append(path)
                self.merge_listbox.insert(tk.END, os.path.basename(path))
        self.merge_status.config(text=f"{len(self.merge_files)} 個のファイルを追加しました")

    def _merge_move_up(self):
        sel = self.merge_listbox.curselection()
        if not sel or sel[0] == 0:
            return
        i = sel[0]
        self.merge_files[i - 1], self.merge_files[i] = self.merge_files[i], self.merge_files[i - 1]
        self._refresh_merge_listbox(select_index=i - 1)

    def _merge_move_down(self):
        sel = self.merge_listbox.curselection()
        if not sel or sel[0] == len(self.merge_files) - 1:
            return
        i = sel[0]
        self.merge_files[i + 1], self.merge_files[i] = self.merge_files[i], self.merge_files[i + 1]
        self._refresh_merge_listbox(select_index=i + 1)

    def _merge_remove_selected(self):
        sel = self.merge_listbox.curselection()
        if not sel:
            return
        del self.merge_files[sel[0]]
        self._refresh_merge_listbox()

    def _merge_clear(self):
        self.merge_files.clear()
        self._refresh_merge_listbox()
        self.merge_status.config(text="リストをクリアしました")

    def _refresh_merge_listbox(self, select_index=None):
        self.merge_listbox.delete(0, tk.END)
        for path in self.merge_files:
            self.merge_listbox.insert(tk.END, os.path.basename(path))
        if select_index is not None and 0 <= select_index < len(self.merge_files):
            self.merge_listbox.selection_set(select_index)

    def _select_merge_output(self):
        path = filedialog.asksaveasfilename(
            title="出力ファイル名を指定",
            defaultextension=".pdf",
            filetypes=[("PDFファイル", "*.pdf")]
        )
        if path:
            self.merge_output_path.set(path)

    def _start_merge(self):
        if len(self.merge_files) < 2:
            messagebox.showwarning("警告", "結合するには2つ以上のPDFファイルを追加してください！")
            return
        if not self.merge_output_path.get():
            messagebox.showwarning("警告", "出力ファイルを指定してください！")
            return

        self.merge_status.config(text="結合処理中...")
        self.update()

        writer = PdfWriter()
        try:
            for path in self.merge_files:
                writer.append(path)
            with open(self.merge_output_path.get(), "wb") as f:
                writer.write(f)
        except Exception as e:
            messagebox.showerror("エラー", f"結合に失敗しました：{e}")
            self.merge_status.config(text="準備完了")
            return
        finally:
            writer.close()

        messagebox.showinfo("完了", f"結合が完了しました！\n出力先：{self.merge_output_path.get()}")
        self.merge_status.config(text="準備完了")

    # ---------------- 分割タブ ----------------
    def _build_split_tab(self):
        parent = self.split_tab

        drop_label = tk.Label(
            parent,
            text="ここに分割したいPDFファイルを1つドラッグ＆ドロップしてください\nまたは下のボタンをクリックして選択",
            bg="#e0f0ff",
            fg="#333",
            font=("Meiryo", 12),
            width=70,
            height=6,
            relief="groove",
            justify="center"
        )
        drop_label.pack(pady=15, padx=20, fill="x")
        drop_label.drop_target_register(DND_FILES)
        drop_label.dnd_bind('<<Drop>>', self._on_split_drop)

        select_frame = tk.Frame(parent)
        select_frame.pack(pady=(0, 8), padx=20, fill="x")
        tk.Button(select_frame, text="PDFファイルを選択", width=18, height=2,
                  font=("Meiryo", 10), command=self._select_split_file).pack(side="left", padx=10)

        self.split_file_label = tk.Label(select_frame, text="（ファイル未選択）", font=("Meiryo", 10), fg="gray")
        self.split_file_label.pack(side="left", padx=10)

        mode_frame = tk.LabelFrame(parent, text="分割方法", font=("Meiryo", 10), padx=10, pady=8)
        mode_frame.pack(pady=(0, 8), padx=20, fill="x")

        tk.Radiobutton(mode_frame, text="1ページごとに分割", variable=self.split_mode,
                        value="per_page", font=("Meiryo", 10)).pack(anchor="w")

        range_row = tk.Frame(mode_frame)
        range_row.pack(fill="x", pady=4)
        tk.Radiobutton(range_row, text="ページ範囲を指定して分割：", variable=self.split_mode,
                        value="ranges", font=("Meiryo", 10)).pack(side="left")
        tk.Entry(range_row, textvariable=self.split_ranges, width=30, font=("Meiryo", 10)).pack(side="left", padx=6)

        tk.Label(mode_frame, text="例：1-3,4-6,10　（カンマ区切り、範囲または単一ページ）",
                 font=("Meiryo", 9), fg="gray").pack(anchor="w", padx=20)

        self.split_status = tk.Label(parent, text="準備完了", fg="gray", font=("Meiryo", 9))
        self.split_status.pack(side="bottom", pady=6)

        split_btn_frame = tk.Frame(parent)
        split_btn_frame.pack(side="bottom", pady=10, padx=20, fill="x")
        tk.Button(split_btn_frame, text="分割開始", width=16, height=2, bg="#4CAF50", fg="white",
                  font=("Meiryo", 10, "bold"), command=self._start_split).pack(side="left", padx=10)

        out_frame = tk.Frame(parent)
        out_frame.pack(side="bottom", pady=(4, 0), padx=20, fill="x")
        tk.Label(out_frame, text="出力フォルダ：", font=("Meiryo", 10), width=12, anchor="w").pack(side="left")
        tk.Entry(out_frame, textvariable=self.split_output_dir, width=45, font=("Meiryo", 10),
                 state="readonly").pack(side="left", padx=6)
        tk.Button(out_frame, text="参照...", font=("Meiryo", 9),
                  command=self._select_split_output_dir).pack(side="left", padx=6)

    def _on_split_drop(self, event):
        dropped = self.tk.splitlist(event.data)
        for path in dropped:
            if os.path.isfile(path) and path.lower().endswith(".pdf"):
                self.split_file.set(path)
                self.split_file_label.config(text=os.path.basename(path), fg="black")
                break

    def _select_split_file(self):
        path = filedialog.askopenfilename(title="PDFファイルを選択", filetypes=[("PDFファイル", "*.pdf")])
        if path:
            self.split_file.set(path)
            self.split_file_label.config(text=os.path.basename(path), fg="black")

    def _select_split_output_dir(self):
        folder = filedialog.askdirectory(title="出力フォルダを選択")
        if folder:
            self.split_output_dir.set(folder)

    @staticmethod
    def _parse_ranges(raw, total_pages):
        ranges = []
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                a_str, b_str = part.split("-", 1)
                a, b = int(a_str), int(b_str)
            else:
                a = b = int(part)
            if a < 1 or b > total_pages or a > b:
                raise ValueError(f"ページ範囲が不正です：{part}（全 {total_pages} ページ）")
            ranges.append((a, b))
        if not ranges:
            raise ValueError("ページ範囲を入力してください")
        return ranges

    def _start_split(self):
        if not self.split_file.get():
            messagebox.showwarning("警告", "分割するPDFファイルを選択してください！")
            return
        if not self.split_output_dir.get():
            messagebox.showwarning("警告", "出力フォルダを選択してください！")
            return

        src_path = self.split_file.get()
        out_dir = self.split_output_dir.get()
        base_name = os.path.splitext(os.path.basename(src_path))[0]

        self.split_status.config(text="分割処理中...")
        self.update()

        try:
            reader = PdfReader(src_path)
            total_pages = len(reader.pages)

            if self.split_mode.get() == "per_page":
                digits = len(str(total_pages))
                for i, page in enumerate(reader.pages, start=1):
                    writer = PdfWriter()
                    writer.add_page(page)
                    out_name = f"{base_name}_p{str(i).zfill(digits)}.pdf"
                    with open(os.path.join(out_dir, out_name), "wb") as f:
                        writer.write(f)
                    writer.close()
                count = total_pages
            else:
                ranges = self._parse_ranges(self.split_ranges.get(), total_pages)
                for a, b in ranges:
                    writer = PdfWriter()
                    for p in range(a - 1, b):
                        writer.add_page(reader.pages[p])
                    label = f"{a}" if a == b else f"{a}-{b}"
                    out_name = f"{base_name}_p{label}.pdf"
                    with open(os.path.join(out_dir, out_name), "wb") as f:
                        writer.write(f)
                    writer.close()
                count = len(ranges)
        except ValueError as e:
            messagebox.showerror("エラー", str(e))
            self.split_status.config(text="準備完了")
            return
        except Exception as e:
            messagebox.showerror("エラー", f"分割に失敗しました：{e}")
            self.split_status.config(text="準備完了")
            return

        messagebox.showinfo("完了", f"分割が完了しました！\n{count} 個のファイルを出力しました。\n出力先：{out_dir}")
        self.split_status.config(text="準備完了")


if __name__ == "__main__":
    app = PdfToolApp()
    app.mainloop()
