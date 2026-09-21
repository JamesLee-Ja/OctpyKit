import io
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinterdnd2 import *
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont

pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiMin-W3'))

BUILTIN_FONTS = {
    "(組み込み) ゴシック体": "HeiseiKakuGo-W5",
    "(組み込み) 明朝体": "HeiseiMin-W3",
}


def _scan_windows_fonts():
    """Windowsのレジストリからインストール済みフォント（名前→実ファイルパス）を取得する。
    Windows以外の環境や取得に失敗した場合は空の辞書を返す（組み込みフォントのみ利用可能）。
    """
    font_map = {}
    try:
        import winreg
    except ImportError:
        return font_map

    fonts_dir = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    reg_roots = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"),
    ]
    for hive, subkey in reg_roots:
        try:
            key = winreg.OpenKey(hive, subkey)
        except OSError:
            continue
        i = 0
        while True:
            try:
                name, file_name, _ = winreg.EnumValue(key, i)
            except OSError:
                break
            i += 1
            ext = os.path.splitext(file_name)[1].lower()
            if ext not in (".ttf", ".ttc", ".otf"):
                continue
            clean_name = (
                name.replace("(TrueType)", "")
                    .replace("(OpenType)", "")
                    .replace("(All res)", "")
                    .strip()
            )
            path = file_name if os.path.isabs(file_name) else os.path.join(fonts_dir, file_name)
            if os.path.exists(path):
                font_map[clean_name] = path
    return font_map


class PdfToolApp(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title("PDFツール")
        self.geometry("800x680")
        self.minsize(800, 680)

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.system_font_map = _scan_windows_fonts()

        self.merge_tab = tk.Frame(notebook)
        self.split_tab = tk.Frame(notebook)
        self.watermark_tab = tk.Frame(notebook)
        self.crypto_tab = tk.Frame(notebook)
        notebook.add(self.merge_tab, text="結合")
        notebook.add(self.split_tab, text="分割")
        notebook.add(self.watermark_tab, text="透かし")
        notebook.add(self.crypto_tab, text="暗号化/復号")

        self.merge_files = []
        self.merge_output_path = tk.StringVar(value="")
        self._build_merge_tab()

        self.split_file = tk.StringVar(value="")
        self.split_mode = tk.StringVar(value="per_page")
        self.split_ranges = tk.StringVar(value="")
        self.split_output_dir = tk.StringVar(value="")
        self._build_split_tab()

        self.wm_file = tk.StringVar(value="")
        self.wm_text = tk.StringVar(value="")
        self.wm_font_choice = tk.StringVar(value="(組み込み) ゴシック体")
        self.wm_font_size = tk.StringVar(value="40")
        self.wm_opacity = tk.StringVar(value="30")
        self.wm_rotation = tk.StringVar(value="45")
        self.wm_position = tk.StringVar(value="中央")
        self.wm_output_path = tk.StringVar(value="")
        self._build_watermark_tab()

        self.crypto_file = tk.StringVar(value="")
        self.crypto_mode = tk.StringVar(value="encrypt")
        self.crypto_password = tk.StringVar(value="")
        self.crypto_password_confirm = tk.StringVar(value="")
        self.crypto_output_path = tk.StringVar(value="")
        self._build_crypto_tab()

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


    # ---------------- 透かしタブ ----------------
    def _build_watermark_tab(self):
        parent = self.watermark_tab

        drop_label = tk.Label(
            parent,
            text="ここに透かしを追加したいPDFファイルを1つドラッグ＆ドロップしてください\nまたは下のボタンをクリックして選択",
            bg="#e0f0ff",
            fg="#333",
            font=("Meiryo", 12),
            width=70,
            height=5,
            relief="groove",
            justify="center"
        )
        drop_label.pack(pady=15, padx=20, fill="x")
        drop_label.drop_target_register(DND_FILES)
        drop_label.dnd_bind('<<Drop>>', self._on_wm_drop)

        select_frame = tk.Frame(parent)
        select_frame.pack(pady=(0, 8), padx=20, fill="x")
        tk.Button(select_frame, text="PDFファイルを選択", width=18, height=2,
                  font=("Meiryo", 10), command=self._select_wm_file).pack(side="left", padx=10)
        self.wm_file_label = tk.Label(select_frame, text="（ファイル未選択）", font=("Meiryo", 10), fg="gray")
        self.wm_file_label.pack(side="left", padx=10)

        settings_frame = tk.LabelFrame(parent, text="透かし設定", font=("Meiryo", 10), padx=10, pady=8)
        settings_frame.pack(pady=(0, 8), padx=20, fill="x")

        text_row = tk.Frame(settings_frame)
        text_row.pack(fill="x", pady=4)
        tk.Label(text_row, text="透かし文字：", font=("Meiryo", 10), width=14, anchor="w").pack(side="left")
        tk.Entry(text_row, textvariable=self.wm_text, width=30, font=("Meiryo", 10)).pack(side="left", padx=6)

        font_row = tk.Frame(settings_frame)
        font_row.pack(fill="x", pady=4)
        tk.Label(font_row, text="フォント：", font=("Meiryo", 10), width=14, anchor="w").pack(side="left")
        font_values = list(BUILTIN_FONTS.keys()) + sorted(self.system_font_map.keys())
        font_combo = ttk.Combobox(
            font_row, textvariable=self.wm_font_choice,
            values=font_values, state="readonly", width=28, font=("Meiryo", 10)
        )
        font_combo.pack(side="left", padx=6)
        if not self.system_font_map:
            tk.Label(
                font_row, text="（システムフォントを検出できませんでした。組み込みフォントのみ利用可）",
                font=("Meiryo", 8), fg="gray"
            ).pack(side="left", padx=6)

        size_row = tk.Frame(settings_frame)
        size_row.pack(fill="x", pady=4)
        tk.Label(size_row, text="フォントサイズ：", font=("Meiryo", 10), width=14, anchor="w").pack(side="left")
        tk.Entry(size_row, textvariable=self.wm_font_size, width=8, font=("Meiryo", 10)).pack(side="left", padx=6)
        tk.Label(size_row, text="透明度(%)：", font=("Meiryo", 10)).pack(side="left", padx=(20, 6))
        tk.Entry(size_row, textvariable=self.wm_opacity, width=8, font=("Meiryo", 10)).pack(side="left", padx=6)
        tk.Label(size_row, text="(1～100)", font=("Meiryo", 9), fg="gray").pack(side="left", padx=4)

        pos_row = tk.Frame(settings_frame)
        pos_row.pack(fill="x", pady=4)
        tk.Label(pos_row, text="位置：", font=("Meiryo", 10), width=14, anchor="w").pack(side="left")
        pos_combo = ttk.Combobox(
            pos_row, textvariable=self.wm_position,
            values=["中央", "左上", "右上", "左下", "右下"], state="readonly", width=10, font=("Meiryo", 10)
        )
        pos_combo.pack(side="left", padx=6)
        tk.Label(pos_row, text="回転角度(度)：", font=("Meiryo", 10)).pack(side="left", padx=(20, 6))
        tk.Entry(pos_row, textvariable=self.wm_rotation, width=8, font=("Meiryo", 10)).pack(side="left", padx=6)

        out_frame = tk.Frame(parent)
        out_frame.pack(pady=(4, 0), padx=20, fill="x")
        tk.Label(out_frame, text="出力ファイル：", font=("Meiryo", 10), width=14, anchor="w").pack(side="left")
        tk.Entry(out_frame, textvariable=self.wm_output_path, width=42, font=("Meiryo", 10),
                 state="readonly").pack(side="left", padx=6)
        tk.Button(out_frame, text="参照...", font=("Meiryo", 9),
                  command=self._select_wm_output).pack(side="left", padx=6)

        self.wm_status = tk.Label(parent, text="準備完了", fg="gray", font=("Meiryo", 9))
        self.wm_status.pack(side="bottom", pady=6)

        wm_btn_frame = tk.Frame(parent)
        wm_btn_frame.pack(side="bottom", pady=10, padx=20, fill="x")
        tk.Button(wm_btn_frame, text="透かし追加開始", width=16, height=2, bg="#4CAF50", fg="white",
                  font=("Meiryo", 10, "bold"), command=self._start_watermark).pack(side="left", padx=10)

    def _on_wm_drop(self, event):
        dropped = self.tk.splitlist(event.data)
        for path in dropped:
            if os.path.isfile(path) and path.lower().endswith(".pdf"):
                self.wm_file.set(path)
                self.wm_file_label.config(text=os.path.basename(path), fg="black")
                break

    def _select_wm_file(self):
        path = filedialog.askopenfilename(title="PDFファイルを選択", filetypes=[("PDFファイル", "*.pdf")])
        if path:
            self.wm_file.set(path)
            self.wm_file_label.config(text=os.path.basename(path), fg="black")

    def _select_wm_output(self):
        path = filedialog.asksaveasfilename(
            title="出力ファイル名を指定",
            defaultextension=".pdf",
            filetypes=[("PDFファイル", "*.pdf")]
        )
        if path:
            self.wm_output_path.set(path)

    def _resolve_font(self, font_choice):
        """フォント選択肢を、実際にReportLabで使えるフォント名に解決する。
        システムフォントの読み込みに失敗した場合は組み込みフォントにフォールバックする。
        """
        if font_choice in BUILTIN_FONTS:
            return BUILTIN_FONTS[font_choice]

        path = self.system_font_map.get(font_choice)
        if not path:
            return BUILTIN_FONTS["(組み込み) ゴシック体"]

        internal_name = "WMFONT_" + str(abs(hash(path)))
        if internal_name not in pdfmetrics.getRegisteredFontNames():
            try:
                ext = os.path.splitext(path)[1].lower()
                if ext == ".ttc":
                    pdfmetrics.registerFont(TTFont(internal_name, path, subfontIndex=0))
                else:
                    pdfmetrics.registerFont(TTFont(internal_name, path))
            except Exception:
                return BUILTIN_FONTS["(組み込み) ゴシック体"]
        return internal_name

    def _make_watermark_page(self, width, height, text, font_name, font_size, opacity, rotation, position):
        buffer = io.BytesIO()
        c = rl_canvas.Canvas(buffer, pagesize=(width, height))
        c.setFont(font_name, font_size)
        c.setFillColorRGB(0.5, 0.5, 0.5)
        c.setFillAlpha(opacity / 100)

        margin = 40
        text_width = c.stringWidth(text, font_name, font_size)

        positions = {
            "中央": (width / 2, height / 2),
            "左上": (margin + text_width / 2, height - margin),
            "右上": (width - margin - text_width / 2, height - margin),
            "左下": (margin + text_width / 2, margin),
            "右下": (width - margin - text_width / 2, margin),
        }
        x, y = positions.get(position, (width / 2, height / 2))

        c.saveState()
        c.translate(x, y)
        c.rotate(rotation)
        c.drawCentredString(0, 0, text)
        c.restoreState()
        c.save()
        buffer.seek(0)
        return PdfReader(buffer).pages[0]

    def _start_watermark(self):
        if not self.wm_file.get():
            messagebox.showwarning("警告", "透かしを追加するPDFファイルを選択してください！")
            return
        if not self.wm_text.get().strip():
            messagebox.showwarning("警告", "透かし文字を入力してください！")
            return
        if not self.wm_output_path.get():
            messagebox.showwarning("警告", "出力ファイルを指定してください！")
            return

        try:
            font_size = int(self.wm_font_size.get())
            opacity = int(self.wm_opacity.get())
            rotation = int(self.wm_rotation.get())
            if not (1 <= opacity <= 100):
                raise ValueError
        except ValueError:
            messagebox.showwarning("警告", "フォントサイズ・透明度(1～100)・回転角度は整数で入力してください！")
            return

        self.wm_status.config(text="透かし追加処理中...")
        self.update()

        try:
            reader = PdfReader(self.wm_file.get())
            if not reader.pages:
                raise ValueError("PDFにページがありません")

            first_page = reader.pages[0]
            page_width = float(first_page.mediabox.width)
            page_height = float(first_page.mediabox.height)
            font_name = self._resolve_font(self.wm_font_choice.get())
            wm_page = self._make_watermark_page(
                page_width, page_height, self.wm_text.get(), font_name,
                font_size, opacity, rotation, self.wm_position.get()
            )

            writer = PdfWriter()
            for page in reader.pages:
                page.merge_page(wm_page)
                writer.add_page(page)

            with open(self.wm_output_path.get(), "wb") as f:
                writer.write(f)
        except Exception as e:
            messagebox.showerror("エラー", f"透かしの追加に失敗しました：{e}")
            self.wm_status.config(text="準備完了")
            return

        messagebox.showinfo("完了", f"透かしの追加が完了しました！\n出力先：{self.wm_output_path.get()}")
        self.wm_status.config(text="準備完了")

    # ---------------- 暗号化/復号タブ ----------------
    def _build_crypto_tab(self):
        parent = self.crypto_tab

        drop_label = tk.Label(
            parent,
            text="ここに対象のPDFファイルを1つドラッグ＆ドロップしてください\nまたは下のボタンをクリックして選択",
            bg="#e0f0ff",
            fg="#333",
            font=("Meiryo", 12),
            width=70,
            height=5,
            relief="groove",
            justify="center"
        )
        drop_label.pack(pady=15, padx=20, fill="x")
        drop_label.drop_target_register(DND_FILES)
        drop_label.dnd_bind('<<Drop>>', self._on_crypto_drop)

        select_frame = tk.Frame(parent)
        select_frame.pack(pady=(0, 8), padx=20, fill="x")
        tk.Button(select_frame, text="PDFファイルを選択", width=18, height=2,
                  font=("Meiryo", 10), command=self._select_crypto_file).pack(side="left", padx=10)
        self.crypto_file_label = tk.Label(select_frame, text="（ファイル未選択）", font=("Meiryo", 10), fg="gray")
        self.crypto_file_label.pack(side="left", padx=10)

        mode_frame = tk.LabelFrame(parent, text="操作", font=("Meiryo", 10), padx=10, pady=8)
        mode_frame.pack(pady=(0, 8), padx=20, fill="x")
        tk.Radiobutton(mode_frame, text="暗号化（開くパスワードを設定する）", variable=self.crypto_mode,
                        value="encrypt", font=("Meiryo", 10), command=self._refresh_crypto_fields).pack(anchor="w")
        tk.Radiobutton(mode_frame, text="復号（開くパスワードを解除する）", variable=self.crypto_mode,
                        value="decrypt", font=("Meiryo", 10), command=self._refresh_crypto_fields).pack(anchor="w")

        pwd_frame = tk.LabelFrame(parent, text="パスワード", font=("Meiryo", 10), padx=10, pady=8)
        pwd_frame.pack(pady=(0, 8), padx=20, fill="x")

        self.crypto_pwd_label = tk.Label(pwd_frame, text="新しいパスワード：", font=("Meiryo", 10), width=16, anchor="w")
        self.crypto_pwd_label.pack(anchor="w")
        pwd_row = tk.Frame(pwd_frame)
        pwd_row.pack(fill="x", pady=2)
        tk.Entry(pwd_row, textvariable=self.crypto_password, show="*", width=25, font=("Meiryo", 10)).pack(side="left")

        self.crypto_pwd_confirm_frame = tk.Frame(pwd_frame)
        self.crypto_pwd_confirm_frame.pack(fill="x", pady=2)
        tk.Label(self.crypto_pwd_confirm_frame, text="確認用パスワード：", font=("Meiryo", 10),
                  width=16, anchor="w").pack(side="left")
        tk.Entry(self.crypto_pwd_confirm_frame, textvariable=self.crypto_password_confirm, show="*",
                  width=25, font=("Meiryo", 10)).pack(side="left")

        out_frame = tk.Frame(parent)
        out_frame.pack(pady=(4, 0), padx=20, fill="x")
        tk.Label(out_frame, text="出力ファイル：", font=("Meiryo", 10), width=14, anchor="w").pack(side="left")
        tk.Entry(out_frame, textvariable=self.crypto_output_path, width=42, font=("Meiryo", 10),
                 state="readonly").pack(side="left", padx=6)
        tk.Button(out_frame, text="参照...", font=("Meiryo", 9),
                  command=self._select_crypto_output).pack(side="left", padx=6)

        self.crypto_status = tk.Label(parent, text="準備完了", fg="gray", font=("Meiryo", 9))
        self.crypto_status.pack(side="bottom", pady=6)

        crypto_btn_frame = tk.Frame(parent)
        crypto_btn_frame.pack(side="bottom", pady=10, padx=20, fill="x")
        tk.Button(crypto_btn_frame, text="実行", width=16, height=2, bg="#4CAF50", fg="white",
                  font=("Meiryo", 10, "bold"), command=self._start_crypto).pack(side="left", padx=10)

        self._refresh_crypto_fields()

    def _refresh_crypto_fields(self):
        if self.crypto_mode.get() == "encrypt":
            self.crypto_pwd_label.config(text="新しいパスワード：")
            self.crypto_pwd_confirm_frame.pack(fill="x", pady=2)
        else:
            self.crypto_pwd_label.config(text="現在のパスワード：")
            self.crypto_pwd_confirm_frame.pack_forget()

    def _on_crypto_drop(self, event):
        dropped = self.tk.splitlist(event.data)
        for path in dropped:
            if os.path.isfile(path) and path.lower().endswith(".pdf"):
                self.crypto_file.set(path)
                self.crypto_file_label.config(text=os.path.basename(path), fg="black")
                break

    def _select_crypto_file(self):
        path = filedialog.askopenfilename(title="PDFファイルを選択", filetypes=[("PDFファイル", "*.pdf")])
        if path:
            self.crypto_file.set(path)
            self.crypto_file_label.config(text=os.path.basename(path), fg="black")

    def _select_crypto_output(self):
        path = filedialog.asksaveasfilename(
            title="出力ファイル名を指定",
            defaultextension=".pdf",
            filetypes=[("PDFファイル", "*.pdf")]
        )
        if path:
            self.crypto_output_path.set(path)

    def _start_crypto(self):
        if not self.crypto_file.get():
            messagebox.showwarning("警告", "対象のPDFファイルを選択してください！")
            return
        if not self.crypto_output_path.get():
            messagebox.showwarning("警告", "出力ファイルを指定してください！")
            return

        mode = self.crypto_mode.get()
        pwd = self.crypto_password.get()

        if mode == "encrypt":
            if not pwd:
                messagebox.showwarning("警告", "新しいパスワードを入力してください！")
                return
            if pwd != self.crypto_password_confirm.get():
                messagebox.showwarning("警告", "確認用パスワードが一致しません！")
                return
        else:
            if not pwd:
                messagebox.showwarning("警告", "現在のパスワードを入力してください！")
                return

        self.crypto_status.config(text="処理中...")
        self.update()

        try:
            reader = PdfReader(self.crypto_file.get())

            if mode == "decrypt" and reader.is_encrypted:
                result = reader.decrypt(pwd)
                if not result:
                    messagebox.showerror("エラー", "パスワードが正しくありません")
                    self.crypto_status.config(text="準備完了")
                    return
            elif mode == "decrypt" and not reader.is_encrypted:
                messagebox.showwarning("警告", "このPDFは暗号化されていません")
                self.crypto_status.config(text="準備完了")
                return

            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)

            if mode == "encrypt":
                writer.encrypt(pwd)

            with open(self.crypto_output_path.get(), "wb") as f:
                writer.write(f)
        except Exception as e:
            messagebox.showerror("エラー", f"処理に失敗しました：{e}")
            self.crypto_status.config(text="準備完了")
            return

        action_label = "暗号化" if mode == "encrypt" else "復号"
        messagebox.showinfo("完了", f"{action_label}が完了しました！\n出力先：{self.crypto_output_path.get()}")
        self.crypto_status.config(text="準備完了")


if __name__ == "__main__":
    app = PdfToolApp()
    app.mainloop()
