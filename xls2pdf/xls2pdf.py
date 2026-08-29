import os
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinterdnd2 import *
import win32com.client as win32
import time

class ExcelToPDFApp(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title("Excel → PDF 変換ツール (A3 + 縦横交互レイアウト)")
        self.geometry("800x650")
        self.minsize(800, 650)
        self.files = []
        self.orient_mode = tk.IntVar(value=2)

        self.drop_label = tk.Label(
            self,
            text="ここにExcelファイルをドラッグ＆ドロップしてください\nまたは下の「ファイルを選択」ボタンをクリック",
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

        orient_frame = tk.LabelFrame(
            self,
            text="ページ向きの設定",
            font=("Meiryo", 10),
            padx=10, pady=6
        )
        orient_frame.pack(pady=(0, 8), padx=20, fill="x")

        options = [
            ("すべて縦向き",            0),
            ("すべて横向き",            1),
            ("縦横交互（縦→横→縦…）", 2),
            ("縦横交互（横→縦→横…）", 3),
        ]
        for label, val in options:
            tk.Radiobutton(
                orient_frame,
                text=label,
                variable=self.orient_mode,
                value=val,
                font=("Meiryo", 10)
            ).pack(side="left", padx=14)

        list_frame = tk.Frame(self)
        list_frame.pack(pady=5, padx=20, fill="both", expand=True)
        tk.Label(list_frame, text="追加されたファイル：", font=("Meiryo", 10)).pack(anchor="w")
        
        self.listbox = tk.Listbox(list_frame, font=("Meiryo", 10), height=10)
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=12, padx=20, fill="x")

        tk.Button(btn_frame, text="ファイルを選択", width=16, height=2,
                  font=("Meiryo", 10), command=self.select_files).pack(side="left", padx=10)
        tk.Button(btn_frame, text="変換開始", width=16, height=2, bg="#4CAF50", fg="white",
                  font=("Meiryo", 10, "bold"), command=self.start_convert).pack(side="left", padx=10)
        tk.Button(btn_frame, text="リストをクリア", width=16, height=2,
                  font=("Meiryo", 10), command=self.clear_list).pack(side="left", padx=10)

        self.status = tk.Label(self, text="準備完了 - Excelファイルをドラッグしてください", fg="gray", font=("Meiryo", 9))
        self.status.pack(side="bottom", pady=10)

    def on_drop(self, event):
        dropped = self.tk.splitlist(event.data)
        for path in dropped:
            if path.lower().endswith(('.xlsx', '.xls')) and path not in self.files:
                self.files.append(path)
                self.listbox.insert(tk.END, os.path.basename(path))
        self.status.config(text=f"{len(self.files)} 個のファイルを追加しました")

    def select_files(self):
        files = filedialog.askopenfilenames(
            title="Excelファイルを選択",
            filetypes=[("Excelファイル", "*.xlsx *.xls")]
        )
        for path in files:
            if path not in self.files:
                self.files.append(path)
                self.listbox.insert(tk.END, os.path.basename(path))
        self.status.config(text=f"{len(self.files)} 個のファイルを追加しました")

    def clear_list(self):
        self.files.clear()
        self.listbox.delete(0, tk.END)
        self.status.config(text="リストをクリアしました")

    def start_convert(self):
        if not self.files:
            messagebox.showwarning("警告", "先にExcelファイルを追加してください！")
            return

        self.status.config(text="変換処理中... しばらくお待ちください（ファイル数が多いと時間がかかります）")
        self.update()

        success = 0
        failed = []
        for excel_path in self.files[:]:
            try:
                self.convert_one_file(excel_path)
                success += 1
                self.status.config(text=f"処理中... {success}/{len(self.files)} 完了")
                self.update()
            except Exception as e:
                failed.append((os.path.basename(excel_path), str(e)))

        if failed:
            err_msg = "\n".join([f"{name}：{err[:100]}" for name, err in failed[:3]])
            messagebox.showerror("一部失敗", f"成功：{success} 個\n失敗：{len(failed)} 個\n\n{err_msg}")
        else:
            messagebox.showinfo("完了", f"すべての変換が完了しました！\n{success} 個のPDFファイルが元のフォルダに生成されました。")

        self.clear_list()
        self.status.config(text="準備完了")

    def convert_one_file(self, excel_path):
        pdf_path = os.path.splitext(excel_path)[0] + ".pdf"

        excel_app = None
        wb = None
        try:
            excel_app = win32.Dispatch("Excel.Application")
            excel_app.Visible = False
            excel_app.DisplayAlerts = False

            excel_app.PrintCommunication = False

            wb = excel_app.Workbooks.Open(os.path.abspath(excel_path))

            mode = self.orient_mode.get()
            for idx, ws in enumerate(wb.Worksheets):
                ps = ws.PageSetup

                ps.PaperSize = 8
                if mode == 0:
                    orientation = 1
                elif mode == 1:
                    orientation = 2
                elif mode == 2:
                    orientation = 1 if idx % 2 == 0 else 2
                else:
                    orientation = 2 if idx % 2 == 0 else 1
                ps.Orientation = orientation

                ps.Zoom = False
                ps.FitToPagesWide = 1
                ps.FitToPagesTall = 1

                ps.PrintArea = ""
                try:
                    used = ws.UsedRange
                    if used is not None:
                        used_addr = used.Address
                        max_row = used.Row + used.Rows.Count - 1
                        max_col = used.Column + used.Columns.Count - 1
                        for shape in ws.Shapes:
                            br = shape.BottomRightCell
                            tl = shape.TopLeftCell
                            if br.Row > max_row:
                                max_row = br.Row
                            if br.Column > max_col:
                                max_col = br.Column
                        top_left = ws.Cells(used.Row, used.Column)
                        bottom_right = ws.Cells(max_row, max_col)
                        ps.PrintArea = ws.Range(top_left, bottom_right).Address
                except Exception:
                    ps.PrintArea = ""

                ps.LeftMargin = 5
                ps.RightMargin = 5
                ps.TopMargin = 10
                ps.BottomMargin = 10
                ps.CenterHorizontally = True
                ps.CenterVertically = True

            excel_app.PrintCommunication = True
            wb.ExportAsFixedFormat(0, pdf_path)

        except Exception as e:
            raise Exception(f"変換エラー: {str(e)}")
        finally:
            if wb:
                wb.Close(False)
            if excel_app:
                excel_app.Quit()


if __name__ == "__main__":
    app = ExcelToPDFApp()
    app.mainloop()