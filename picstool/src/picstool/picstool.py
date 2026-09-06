import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinterdnd2 import *
from PIL import Image

SUPPORTED_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp'}
FORMAT_MAP = {
    'JPG': ('JPEG', '.jpg'),
    'PNG': ('PNG', '.png'),
    'GIF': ('GIF', '.gif'),
    'BMP': ('BMP', '.bmp'),
}


class PicsToolApp(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title("画像一括変換ツール")
        self.geometry("800x680")
        self.minsize(800, 680)
        self.files = []
        self.output_dir = tk.StringVar(value="")
        self.output_format = tk.StringVar(value="JPG")
        self.resize_percent = tk.StringVar(value="100")

        self.drop_label = tk.Label(
            self,
            text="ここに画像ファイルまたはフォルダをドラッグ＆ドロップしてください\nまたは下のボタンをクリックして選択",
            bg="#e0f0ff",
            fg="#333",
            font=("Meiryo", 12),
            width=70,
            height=8,
            relief="groove",
            justify="center"
        )
        self.drop_label.pack(pady=15, padx=20, fill="x")
        self.drop_label.drop_target_register(DND_FILES)
        self.drop_label.dnd_bind('<<Drop>>', self.on_drop)

        select_frame = tk.Frame(self)
        select_frame.pack(pady=(0, 8), padx=20, fill="x")
        tk.Button(select_frame, text="画像ファイルを選択", width=18, height=2,
                  font=("Meiryo", 10), command=self.select_files).pack(side="left", padx=10)
        tk.Button(select_frame, text="フォルダを選択", width=18, height=2,
                  font=("Meiryo", 10), command=self.select_folder).pack(side="left", padx=10)

        settings_frame = tk.LabelFrame(
            self, text="変換設定", font=("Meiryo", 10), padx=10, pady=8
        )
        settings_frame.pack(pady=(0, 8), padx=20, fill="x")

        fmt_frame = tk.Frame(settings_frame)
        fmt_frame.pack(fill="x", pady=4)
        tk.Label(fmt_frame, text="出力形式：", font=("Meiryo", 10), width=12, anchor="w").pack(side="left")
        fmt_combo = ttk.Combobox(
            fmt_frame, textvariable=self.output_format,
            values=list(FORMAT_MAP.keys()), state="readonly", width=10, font=("Meiryo", 10)
        )
        fmt_combo.pack(side="left", padx=6)

        resize_frame = tk.Frame(settings_frame)
        resize_frame.pack(fill="x", pady=4)
        tk.Label(resize_frame, text="圧縮率(%)：", font=("Meiryo", 10), width=12, anchor="w").pack(side="left")
        resize_entry = tk.Entry(resize_frame, textvariable=self.resize_percent, width=8, font=("Meiryo", 10))
        resize_entry.pack(side="left", padx=6)
        tk.Label(
            resize_frame, text="(1～99の整数、元のサイズに対する割合)",
            font=("Meiryo", 9), fg="gray"
        ).pack(side="left", padx=6)

        out_frame = tk.Frame(settings_frame)
        out_frame.pack(fill="x", pady=4)
        tk.Label(out_frame, text="出力フォルダ：", font=("Meiryo", 10), width=12, anchor="w").pack(side="left")
        self.out_entry = tk.Entry(
            out_frame, textvariable=self.output_dir, width=45, font=("Meiryo", 10), state="readonly"
        )
        self.out_entry.pack(side="left", padx=6)
        tk.Button(out_frame, text="参照...", font=("Meiryo", 9), command=self.select_output_dir).pack(side="left", padx=6)

        list_frame = tk.Frame(self)
        list_frame.pack(pady=5, padx=20, fill="both", expand=True)
        tk.Label(list_frame, text="追加された画像ファイル：", font=("Meiryo", 10)).pack(anchor="w")

        self.listbox = tk.Listbox(list_frame, font=("Meiryo", 10), height=10)
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=12, padx=20, fill="x")
        tk.Button(btn_frame, text="変換開始", width=16, height=2, bg="#4CAF50", fg="white",
                  font=("Meiryo", 10, "bold"), command=self.start_convert).pack(side="left", padx=10)
        tk.Button(btn_frame, text="リストをクリア", width=16, height=2,
                  font=("Meiryo", 10), command=self.clear_list).pack(side="left", padx=10)

        self.status = tk.Label(
            self, text="準備完了 - 画像ファイルをドラッグしてください", fg="gray", font=("Meiryo", 9)
        )
        self.status.pack(side="bottom", pady=10)

    def _is_supported(self, path):
        return os.path.splitext(path)[1].lower() in SUPPORTED_EXTS

    def _add_file(self, path):
        if self._is_supported(path) and path not in self.files:
            self.files.append(path)
            self.listbox.insert(tk.END, os.path.basename(path))

    def _add_folder(self, folder):
        try:
            for name in sorted(os.listdir(folder)):
                full = os.path.join(folder, name)
                if os.path.isfile(full):
                    self._add_file(full)
        except OSError as e:
            messagebox.showerror("エラー", f"フォルダの読み込みに失敗しました：{e}")

    def on_drop(self, event):
        dropped = self.tk.splitlist(event.data)
        for path in dropped:
            if os.path.isdir(path):
                self._add_folder(path)
            elif os.path.isfile(path):
                self._add_file(path)
        self.status.config(text=f"{len(self.files)} 個のファイルを追加しました")

    def select_files(self):
        files = filedialog.askopenfilenames(
            title="画像ファイルを選択",
            filetypes=[("画像ファイル", "*.jpg *.jpeg *.png *.gif *.bmp")]
        )
        for path in files:
            self._add_file(path)
        self.status.config(text=f"{len(self.files)} 個のファイルを追加しました")

    def select_folder(self):
        folder = filedialog.askdirectory(title="画像フォルダを選択")
        if folder:
            self._add_folder(folder)
            self.status.config(text=f"{len(self.files)} 個のファイルを追加しました")

    def select_output_dir(self):
        folder = filedialog.askdirectory(title="出力フォルダを選択")
        if folder:
            self.output_dir.set(folder)

    def clear_list(self):
        self.files.clear()
        self.listbox.delete(0, tk.END)
        self.status.config(text="リストをクリアしました")

    def _validate_percent(self):
        raw = self.resize_percent.get().strip()
        if not raw.isdigit():
            return None
        value = int(raw)
        if 1 <= value <= 99:
            return value
        return None

    def start_convert(self):
        if not self.files:
            messagebox.showwarning("警告", "先に画像ファイルを追加してください！")
            return
        if not self.output_dir.get():
            messagebox.showwarning("警告", "出力フォルダを選択してください！")
            return
        percent = self._validate_percent()
        if percent is None:
            messagebox.showwarning("警告", "圧縮率は1～99の整数で入力してください！")
            return

        out_format_key = self.output_format.get()
        pil_format, ext = FORMAT_MAP[out_format_key]
        out_dir = self.output_dir.get()

        self.status.config(text="変換処理中... しばらくお待ちください（ファイル数が多いと時間がかかります）")
        self.update()

        success = 0
        failed = []
        for src_path in self.files[:]:
            try:
                self._convert_one(src_path, out_dir, pil_format, ext, percent)
                success += 1
                self.status.config(text=f"処理中... {success}/{len(self.files)} 完了")
                self.update()
            except Exception as e:
                failed.append((os.path.basename(src_path), str(e)))

        if failed:
            err_msg = "\n".join([f"{name}：{err[:100]}" for name, err in failed[:3]])
            messagebox.showerror("一部失敗", f"成功：{success} 個\n失敗：{len(failed)} 個\n\n{err_msg}")
        else:
            messagebox.showinfo("完了", f"すべての変換が完了しました！\n{success} 個のファイルが出力されました。")

        self.clear_list()
        self.status.config(text="準備完了")

    def _convert_one(self, src_path, out_dir, pil_format, ext, percent):
        base_name = os.path.splitext(os.path.basename(src_path))[0]
        dst_path = os.path.join(out_dir, base_name + ext)

        with Image.open(src_path) as img:
            new_w = max(1, int(img.width * percent / 100))
            new_h = max(1, int(img.height * percent / 100))
            resized = img.resize((new_w, new_h), Image.LANCZOS)

            if pil_format == 'JPEG' and resized.mode in ('RGBA', 'P', 'LA'):
                resized = resized.convert('RGB')
            elif pil_format == 'GIF' and resized.mode not in ('P', 'L'):
                resized = resized.convert('P', palette=Image.ADAPTIVE)

            resized.save(dst_path, pil_format)


if __name__ == "__main__":
    app = PicsToolApp()
    app.mainloop()
