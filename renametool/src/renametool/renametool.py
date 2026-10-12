import fnmatch
import json
import os
import re
import stat
import uuid
from collections import Counter
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinterdnd2 import *

# ------------------------------------------------------------------
# 定数
# ------------------------------------------------------------------
ILLEGAL_CHARS = set('\\/:*?"<>|')
RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL"}
RESERVED_NAMES |= {f"COM{i}" for i in range(1, 10)}
RESERVED_NAMES |= {f"LPT{i}" for i in range(1, 10)}

ST_OK = "変更"
ST_SAME = "変更なし"
ST_CONFLICT = "競合"
ST_INVALID = "不正な名前"
ST_ERROR = "エラー"
BAD_STATUSES = (ST_CONFLICT, ST_INVALID, ST_ERROR)

FILTER_MODES = ["ワイルドカード", "含む文字", "正規表現"]
DATE_SOURCES = ["更新日時", "作成日時", "現在日時"]
DATE_FORMATS = {
    "YYYYMMDD": lambda d: d.strftime("%Y%m%d"),
    "YYYY-MM-DD": lambda d: d.strftime("%Y-%m-%d"),
    "YYYYMMDD_HHMMSS": lambda d: d.strftime("%Y%m%d_%H%M%S"),
    "YYYY年MM月DD日": lambda d: f"{d.year}年{d.month:02d}月{d.day:02d}日",
}
DATE_POSITIONS = ["先頭", "末尾（拡張子の前）"]
CASE_STEM = ["変更しない", "すべて大文字", "すべて小文字", "先頭のみ大文字"]
CASE_EXT = ["変更しない", "小文字にする", "大文字にする", "指定した拡張子に変更"]

MODE_LABELS = [
    ("replace", "検索して置換"),
    ("affix", "前後に文字を追加"),
    ("serial", "連番"),
    ("date", "日付を付加"),
    ("case", "大文字小文字・拡張子"),
]


# ------------------------------------------------------------------
# コアロジック（画面に依存しない関数群）
# ------------------------------------------------------------------
def natural_key(text):
    """数字を数値として比較する自然順ソート用キー（file2 < file10）。"""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", text)]


def is_hidden_or_system(path):
    """Windowsの隠し属性／システム属性が付いているか（Windows以外はFalse）。"""
    try:
        attrs = os.stat(path).st_file_attributes
    except (AttributeError, OSError):
        return False
    return bool(attrs & (stat.FILE_ATTRIBUTE_HIDDEN | stat.FILE_ATTRIBUTE_SYSTEM))


def collect_files(sources, include_sub):
    """ドロップ／選択された対象（フォルダ・ファイル）から、ファイルの絶対パス一覧を集める。
    フォルダ走査では隠し・システムファイルは除外する（desktop.ini などを壊さないため）。
    """
    files, seen = [], set()

    def add(path, check_hidden):
        full = os.path.abspath(path)
        key = os.path.normcase(full)
        if key in seen:
            return
        if check_hidden and is_hidden_or_system(full):
            return
        seen.add(key)
        files.append(full)

    for src in sources:
        if os.path.isdir(src):
            if include_sub:
                for root, dirs, names in os.walk(src):
                    dirs[:] = [d for d in dirs if not is_hidden_or_system(os.path.join(root, d))]
                    for n in names:
                        add(os.path.join(root, n), True)
            else:
                try:
                    names = os.listdir(src)
                except OSError:
                    continue
                for n in names:
                    p = os.path.join(src, n)
                    if os.path.isfile(p):
                        add(p, True)
        elif os.path.isfile(src):
            add(src, False)  # 明示的に指定されたファイルは隠し属性でも対象にする
    return files


def build_matcher(mode, text, case_sensitive):
    """絞り込み条件から判定関数を作る。条件が空なら None（＝すべて対象）。"""
    text = text.strip()
    if not text:
        return None

    if mode == "正規表現":
        try:
            pattern = re.compile(text, 0 if case_sensitive else re.IGNORECASE)
        except re.error as e:
            raise ValueError(f"正規表現が不正です：{e}")
        return lambda name: pattern.search(name) is not None

    tokens = [t.strip() for t in re.split(r"[;；]", text) if t.strip()]
    if not tokens:
        return None
    if not case_sensitive:
        tokens = [t.lower() for t in tokens]

    def norm(name):
        return name if case_sensitive else name.lower()

    if mode == "含む文字":
        return lambda name: any(t in norm(name) for t in tokens)
    return lambda name: any(fnmatch.fnmatchcase(norm(name), t) for t in tokens)


def build_renamer(mode, p):
    """リネームルールから変換関数 f(path, stem, ext, index) -> (新stem, 新ext) を作る。
    入力に問題があれば ValueError（メッセージは画面表示用）。
    """
    if mode == "replace":
        find, repl = p["find"], p["replace"]
        if find == "":
            raise ValueError("検索する文字列を入力してください")
        if p["regex"]:
            try:
                pattern = re.compile(find)
            except re.error as e:
                raise ValueError(f"正規表現が不正です：{e}")
            return lambda path, stem, ext, i: (pattern.sub(repl, stem), ext)
        return lambda path, stem, ext, i: (stem.replace(find, repl), ext)

    if mode == "affix":
        prefix, suffix = p["prefix"], p["suffix"]
        if not prefix and not suffix:
            raise ValueError("先頭に追加する文字、または末尾に追加する文字を入力してください")
        return lambda path, stem, ext, i: (prefix + stem + suffix, ext)

    if mode == "serial":
        template = p["template"]
        if "{n}" not in template:
            raise ValueError("名前テンプレートに {n} を含めてください（例：写真_{n}）")
        try:
            start, step, digits = int(p["start"]), int(p["step"]), int(p["digits"])
        except ValueError:
            raise ValueError("開始番号・増分・桁数は整数で入力してください")
        if start < 0 or step < 1 or not (1 <= digits <= 10):
            raise ValueError("開始番号は0以上、増分は1以上、桁数は1～10で入力してください")

        def serial(path, stem, ext, i):
            num = str(start + i * step).zfill(digits)
            return template.replace("{n}", num).replace("{name}", stem), ext

        return serial

    if mode == "date":
        source, position, sep = p["source"], p["position"], p["sep"]
        fmt = DATE_FORMATS[p["format"]]
        now = datetime.now()

        def date_rule(path, stem, ext, i):
            if source == "現在日時":
                dt = now
            elif source == "更新日時":
                dt = datetime.fromtimestamp(os.path.getmtime(path))
            else:
                dt = datetime.fromtimestamp(os.path.getctime(path))
            d = fmt(dt)
            return (d + sep + stem if position == DATE_POSITIONS[0] else stem + sep + d), ext

        return date_rule

    if mode == "case":
        stem_mode, ext_mode = p["stem_case"], p["ext_case"]
        new_ext = p["new_ext"].strip().lstrip(".")
        if stem_mode == CASE_STEM[0] and ext_mode == CASE_EXT[0]:
            raise ValueError("変更する項目（ファイル名または拡張子）を選択してください")
        if ext_mode == CASE_EXT[3] and not new_ext:
            raise ValueError("変更後の拡張子を入力してください")

        def case_rule(path, stem, ext, i):
            s, e = stem, ext
            if stem_mode == CASE_STEM[1]:
                s = stem.upper()
            elif stem_mode == CASE_STEM[2]:
                s = stem.lower()
            elif stem_mode == CASE_STEM[3]:
                s = stem[:1].upper() + stem[1:].lower()
            if ext_mode == CASE_EXT[1]:
                e = ext.lower()
            elif ext_mode == CASE_EXT[2]:
                e = ext.upper()
            elif ext_mode == CASE_EXT[3]:
                e = "." + new_ext
            return s, e

        return case_rule

    raise ValueError("不明なルールです")


def validate_name(new_stem, new_name):
    """Windowsのファイル名として使えるか検査。問題があれば理由、なければ None。"""
    if not new_stem.strip():
        return "名前が空になります"
    if any(ch in ILLEGAL_CHARS or ord(ch) < 32 for ch in new_name):
        return "使用できない文字を含みます"
    if new_name[-1] in " .":
        return "末尾にスペース／ピリオドは使えません"
    if len(new_name) > 255:
        return "名前が長すぎます"
    if new_name.split(".")[0].upper() in RESERVED_NAMES:
        return "予約された名前です"
    return None


def _key(path):
    return os.path.normcase(os.path.abspath(path))


def detect_conflicts(items):
    """競合（変更後の名前の重複／既存ファイルとの衝突）を検出して status を更新する。
    連鎖（a→b, b→c）や入れ替え（a↔b）は実行時に一時名を経由するため、競合扱いにしない。
    """
    changing = [it for it in items if it["status"] == ST_OK]
    src_keys = {_key(it["src"]) for it in changing}

    counts = Counter()
    for it in items:
        if it["status"] in (ST_OK, ST_SAME):
            counts[_key(os.path.join(it["dir"], it["new"]))] += 1

    for it in changing:
        dst = os.path.join(it["dir"], it["new"])
        k = _key(dst)
        if counts[k] > 1:
            it["status"] = ST_CONFLICT
            it["note"] = "変更後の名前が他のファイルと重複しています"
        elif os.path.exists(dst) and k not in src_keys:
            it["status"] = ST_CONFLICT
            it["note"] = "同名のファイルが既に存在します"


def build_plan(files, renamer):
    """ファイル一覧とルールから、リネーム計画（プレビュー内容）を作る。"""
    items = []
    for i, path in enumerate(files):
        d, name = os.path.split(path)
        stem, ext = os.path.splitext(name)
        item = {"src": path, "dir": d, "old": name, "new": name, "status": ST_OK, "note": ""}
        try:
            new_stem, new_ext = renamer(path, stem, ext, i)
            new_name = new_stem + new_ext
        except Exception as e:
            item["status"] = ST_ERROR
            item["note"] = str(e)
            items.append(item)
            continue

        item["new"] = new_name
        if new_name == name:
            item["status"] = ST_SAME
        else:
            reason = validate_name(new_stem, new_name)
            if reason:
                item["status"] = ST_INVALID
                item["note"] = reason
        items.append(item)

    detect_conflicts(items)
    return items


def apply_renames(pairs):
    """(元パス, 新パス) のリストを実行する。いったん一時名に退避してから最終名へ変更するため、
    入れ替えや連鎖、大文字小文字だけの変更でも途中で衝突しない。
    戻り値: (成功した (元, 新) のリスト, 失敗した (元パス, 理由) のリスト)
    """
    staged, failures = [], []
    for src, dst in pairs:
        tmp = os.path.join(os.path.dirname(src), f".rt_{uuid.uuid4().hex}.tmp")
        try:
            os.rename(src, tmp)
            staged.append((src, tmp, dst))
        except OSError as e:
            failures.append((src, str(e)))

    done = []
    for src, tmp, dst in staged:
        try:
            if os.path.exists(dst):
                raise FileExistsError("同名のファイルが既に存在します")
            os.rename(tmp, dst)
            done.append((src, dst))
        except OSError as e:
            try:
                os.rename(tmp, src)
                failures.append((src, str(e)))
            except OSError:
                failures.append((src, f"{e}（一時名 {os.path.basename(tmp)} のまま残っています）"))
    return done, failures


# ---- 元に戻す用のログ ----
def undo_log_path():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "OctpyKit", "renametool_last.json")


def save_undo_log(pairs):
    try:
        path = undo_log_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"time": datetime.now().isoformat(timespec="seconds"),
                       "pairs": [[a, b] for a, b in pairs]}, f, ensure_ascii=False)
        return True
    except OSError:
        return False


def load_undo_log():
    try:
        with open(undo_log_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        pairs = [(a, b) for a, b in data.get("pairs", [])]
        return pairs or None
    except (OSError, ValueError, TypeError):
        return None


def clear_undo_log():
    try:
        os.remove(undo_log_path())
    except OSError:
        pass


# ------------------------------------------------------------------
# 画面
# ------------------------------------------------------------------
FONT = ("Meiryo", 10)
FONT_S = ("Meiryo", 9)


class RenameToolApp(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title("ファイル一括リネームツール")
        self.geometry("920x740")
        self.minsize(920, 680)

        self.sources = []
        self.plan = None
        self.plan_sig = None

        self._init_vars()
        self._build_ui()
        self._show_mode_frame()
        self._refresh_undo_button()

    # ---------------- 変数 ----------------
    def _init_vars(self):
        self.include_sub = tk.BooleanVar(value=False)
        self.filter_mode = tk.StringVar(value=FILTER_MODES[0])
        self.filter_text = tk.StringVar(value="")
        self.filter_case = tk.BooleanVar(value=False)
        self.mode = tk.StringVar(value="replace")

        self.rep_find = tk.StringVar(value="")
        self.rep_with = tk.StringVar(value="")
        self.rep_regex = tk.BooleanVar(value=False)
        self.aff_prefix = tk.StringVar(value="")
        self.aff_suffix = tk.StringVar(value="")
        self.ser_template = tk.StringVar(value="ファイル_{n}")
        self.ser_start = tk.StringVar(value="1")
        self.ser_step = tk.StringVar(value="1")
        self.ser_digits = tk.StringVar(value="3")
        self.date_source = tk.StringVar(value=DATE_SOURCES[0])
        self.date_format = tk.StringVar(value="YYYYMMDD")
        self.date_position = tk.StringVar(value=DATE_POSITIONS[0])
        self.date_sep = tk.StringVar(value="_")
        self.case_stem = tk.StringVar(value=CASE_STEM[0])
        self.case_ext = tk.StringVar(value=CASE_EXT[0])
        self.case_new_ext = tk.StringVar(value="")

        self._all_vars = [
            self.include_sub, self.filter_mode, self.filter_text, self.filter_case, self.mode,
            self.rep_find, self.rep_with, self.rep_regex, self.aff_prefix, self.aff_suffix,
            self.ser_template, self.ser_start, self.ser_step, self.ser_digits,
            self.date_source, self.date_format, self.date_position, self.date_sep,
            self.case_stem, self.case_ext, self.case_new_ext,
        ]

    def _signature(self):
        """プレビュー時点の設定を記録しておき、実行時に変更されていないか確認する。"""
        return (tuple(self.sources), tuple(v.get() for v in self._all_vars))

    def _rule_params(self):
        return {
            "find": self.rep_find.get(), "replace": self.rep_with.get(), "regex": self.rep_regex.get(),
            "prefix": self.aff_prefix.get(), "suffix": self.aff_suffix.get(),
            "template": self.ser_template.get(), "start": self.ser_start.get(),
            "step": self.ser_step.get(), "digits": self.ser_digits.get(),
            "source": self.date_source.get(), "format": self.date_format.get(),
            "position": self.date_position.get(), "sep": self.date_sep.get(),
            "stem_case": self.case_stem.get(), "ext_case": self.case_ext.get(),
            "new_ext": self.case_new_ext.get(),
        }

    # ---------------- 部品ヘルパー ----------------
    @staticmethod
    def _label(parent, text, **kw):
        return tk.Label(parent, text=text, font=kw.pop("font", FONT), **kw)

    @staticmethod
    def _entry(parent, var, width):
        return tk.Entry(parent, textvariable=var, width=width, font=FONT)

    @staticmethod
    def _combo(parent, var, values, width):
        return ttk.Combobox(parent, textvariable=var, values=values, state="readonly", width=width, font=FONT)

    # ---------------- 画面構築 ----------------
    def _build_ui(self):
        style = ttk.Style(self)
        style.configure("Treeview", font=FONT_S, rowheight=22)
        style.configure("Treeview.Heading", font=("Meiryo", 9, "bold"))

        # 下部（先にpackして常に表示されるようにする）
        self.status = tk.Label(self, text="準備完了 - フォルダまたはファイルをドラッグしてください",
                               fg="gray", font=FONT_S)
        self.status.pack(side="bottom", pady=6)

        btn_frame = tk.Frame(self)
        btn_frame.pack(side="bottom", pady=8, padx=20, fill="x")
        tk.Button(btn_frame, text="プレビュー", width=14, height=2, font=("Meiryo", 10, "bold"),
                  command=self.on_preview).pack(side="left", padx=8)
        tk.Button(btn_frame, text="リネーム実行", width=14, height=2, bg="#4CAF50", fg="white",
                  font=("Meiryo", 10, "bold"), command=self.on_execute).pack(side="left", padx=8)
        self.undo_btn = tk.Button(btn_frame, text="直前の操作を元に戻す", width=20, height=2,
                                  font=FONT, command=self.on_undo)
        self.undo_btn.pack(side="left", padx=8)
        tk.Button(btn_frame, text="クリア", width=10, height=2, font=FONT,
                  command=self.on_clear).pack(side="left", padx=8)

        # ドロップ領域
        drop_label = tk.Label(
            self,
            text="ここにフォルダまたはファイルをドラッグ＆ドロップしてください",
            bg="#e0f0ff", fg="#333", font=("Meiryo", 12), height=3, relief="groove", justify="center"
        )
        drop_label.pack(pady=(12, 6), padx=20, fill="x")
        drop_label.drop_target_register(DND_FILES)
        drop_label.dnd_bind("<<Drop>>", self.on_drop)

        select_frame = tk.Frame(self)
        select_frame.pack(pady=(0, 6), padx=20, fill="x")
        tk.Button(select_frame, text="フォルダを選択", width=14, font=FONT,
                  command=self.select_folder).pack(side="left", padx=(0, 8))
        tk.Button(select_frame, text="ファイルを選択", width=14, font=FONT,
                  command=self.select_files).pack(side="left", padx=8)
        tk.Checkbutton(select_frame, text="サブフォルダも含める", variable=self.include_sub,
                       font=FONT).pack(side="left", padx=12)
        self.sources_label = tk.Label(select_frame, text="対象：未選択", font=FONT, fg="gray")
        self.sources_label.pack(side="left", padx=8)
        tk.Label(self, text="※フォルダ走査では隠しファイル・システムファイルは対象外です",
                 font=("Meiryo", 8), fg="gray").pack(anchor="w", padx=24)

        # 絞り込み条件
        filter_frame = tk.LabelFrame(self, text="絞り込み条件（空欄＝すべてのファイルが対象）",
                                     font=FONT, padx=10, pady=6)
        filter_frame.pack(pady=(4, 6), padx=20, fill="x")
        row = tk.Frame(filter_frame)
        row.pack(fill="x")
        self._label(row, "一致方法：").pack(side="left")
        self._combo(row, self.filter_mode, FILTER_MODES, 14).pack(side="left", padx=6)
        self._label(row, "条件：").pack(side="left", padx=(12, 0))
        self._entry(row, self.filter_text, 34).pack(side="left", padx=6)
        tk.Checkbutton(row, text="大文字小文字を区別", variable=self.filter_case,
                       font=FONT_S).pack(side="left", padx=6)
        tk.Label(filter_frame, text="例：*.jpg;*.png（; で複数指定）／ 含む文字：IMG ／ 正規表現：^IMG_\\d+",
                 font=("Meiryo", 8), fg="gray").pack(anchor="w")

        # リネームルール
        rule_frame = tk.LabelFrame(self, text="リネームルール", font=FONT, padx=10, pady=6)
        rule_frame.pack(pady=(0, 6), padx=20, fill="x")
        radio_row = tk.Frame(rule_frame)
        radio_row.pack(fill="x")
        for key, label in MODE_LABELS:
            tk.Radiobutton(radio_row, text=label, variable=self.mode, value=key, font=FONT,
                           command=self._show_mode_frame).pack(side="left", padx=6)
        self.param_container = tk.Frame(rule_frame)
        self.param_container.pack(fill="x", pady=(6, 0))
        self.mode_frames = {
            "replace": self._build_replace_frame(),
            "affix": self._build_affix_frame(),
            "serial": self._build_serial_frame(),
            "date": self._build_date_frame(),
            "case": self._build_case_frame(),
        }

        # プレビュー表
        tk.Label(self, text="プレビュー：", font=FONT).pack(anchor="w", padx=22)
        tree_frame = tk.Frame(self)
        tree_frame.pack(pady=(0, 4), padx=20, fill="both", expand=True)
        cols = ("status", "old", "new", "dir", "note")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=6)
        for col, text, width in (("status", "状態", 80), ("old", "元のファイル名", 200),
                                 ("new", "新しいファイル名", 200), ("dir", "フォルダ", 220),
                                 ("note", "備考", 160)):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="w")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.tag_configure("bad", foreground="#c62828")
        self.tree.tag_configure("same", foreground="gray")

    def _new_mode_frame(self):
        return tk.Frame(self.param_container)

    def _build_replace_frame(self):
        f = self._new_mode_frame()
        self._label(f, "検索：").pack(side="left")
        self._entry(f, self.rep_find, 22).pack(side="left", padx=6)
        self._label(f, "置換後：").pack(side="left", padx=(10, 0))
        self._entry(f, self.rep_with, 22).pack(side="left", padx=6)
        tk.Checkbutton(f, text="正規表現を使う", variable=self.rep_regex, font=FONT_S).pack(side="left", padx=6)
        return f

    def _build_affix_frame(self):
        f = self._new_mode_frame()
        self._label(f, "先頭に追加：").pack(side="left")
        self._entry(f, self.aff_prefix, 22).pack(side="left", padx=6)
        self._label(f, "末尾に追加（拡張子の前）：").pack(side="left", padx=(10, 0))
        self._entry(f, self.aff_suffix, 22).pack(side="left", padx=6)
        return f

    def _build_serial_frame(self):
        f = self._new_mode_frame()
        r1 = tk.Frame(f)
        r1.pack(fill="x")
        self._label(r1, "名前テンプレート：").pack(side="left")
        self._entry(r1, self.ser_template, 26).pack(side="left", padx=6)
        tk.Label(r1, text="{n}＝連番（必須）　{name}＝元の名前（任意）", font=("Meiryo", 8),
                 fg="gray").pack(side="left", padx=6)
        r2 = tk.Frame(f)
        r2.pack(fill="x", pady=(4, 0))
        self._label(r2, "開始番号：").pack(side="left")
        self._entry(r2, self.ser_start, 6).pack(side="left", padx=6)
        self._label(r2, "増分：").pack(side="left", padx=(10, 0))
        self._entry(r2, self.ser_step, 6).pack(side="left", padx=6)
        self._label(r2, "桁数（ゼロ埋め）：").pack(side="left", padx=(10, 0))
        self._entry(r2, self.ser_digits, 6).pack(side="left", padx=6)
        return f

    def _build_date_frame(self):
        f = self._new_mode_frame()
        r1 = tk.Frame(f)
        r1.pack(fill="x")
        self._label(r1, "日付の種類：").pack(side="left")
        self._combo(r1, self.date_source, DATE_SOURCES, 10).pack(side="left", padx=6)
        self._label(r1, "書式：").pack(side="left", padx=(10, 0))
        self._combo(r1, self.date_format, list(DATE_FORMATS.keys()), 18).pack(side="left", padx=6)
        r2 = tk.Frame(f)
        r2.pack(fill="x", pady=(4, 0))
        self._label(r2, "付加位置：").pack(side="left")
        self._combo(r2, self.date_position, DATE_POSITIONS, 18).pack(side="left", padx=6)
        self._label(r2, "区切り文字：").pack(side="left", padx=(10, 0))
        self._entry(r2, self.date_sep, 6).pack(side="left", padx=6)
        return f

    def _build_case_frame(self):
        f = self._new_mode_frame()
        r1 = tk.Frame(f)
        r1.pack(fill="x")
        self._label(r1, "ファイル名：").pack(side="left")
        self._combo(r1, self.case_stem, CASE_STEM, 16).pack(side="left", padx=6)
        self._label(r1, "拡張子：").pack(side="left", padx=(10, 0))
        self._combo(r1, self.case_ext, CASE_EXT, 20).pack(side="left", padx=6)
        r2 = tk.Frame(f)
        r2.pack(fill="x", pady=(4, 0))
        self._label(r2, "変更後の拡張子：").pack(side="left")
        self._entry(r2, self.case_new_ext, 10).pack(side="left", padx=6)
        tk.Label(r2, text="（「指定した拡張子に変更」選択時のみ使用。例：jpg）", font=("Meiryo", 8),
                 fg="gray").pack(side="left", padx=6)
        return f

    def _show_mode_frame(self):
        for f in self.mode_frames.values():
            f.pack_forget()
        self.mode_frames[self.mode.get()].pack(fill="x")

    # ---------------- 対象の追加 ----------------
    def _add_source(self, path):
        path = os.path.abspath(path)
        if not os.path.exists(path):
            return
        if _key(path) in {_key(s) for s in self.sources}:
            return
        self.sources.append(path)

    def _sources_changed(self):
        dirs = sum(1 for s in self.sources if os.path.isdir(s))
        files = len(self.sources) - dirs
        if self.sources:
            self.sources_label.config(text=f"対象：フォルダ {dirs} 個、ファイル {files} 個", fg="black")
        else:
            self.sources_label.config(text="対象：未選択", fg="gray")
        self._reset_preview()

    def on_drop(self, event):
        for path in self.tk.splitlist(event.data):
            self._add_source(path)
        self._sources_changed()
        self.status.config(text="対象を追加しました。ルールを設定して「プレビュー」を押してください")

    def select_folder(self):
        folder = filedialog.askdirectory(title="フォルダを選択")
        if folder:
            self._add_source(folder)
            self._sources_changed()

    def select_files(self):
        files = filedialog.askopenfilenames(title="ファイルを選択")
        for p in files:
            self._add_source(p)
        if files:
            self._sources_changed()

    def _remap_sources(self, pairs):
        """リネームしたファイルが対象に直接指定されていた場合、新しいパスに置き換える。"""
        mapping = {_key(old): new for old, new in pairs}
        self.sources = [mapping.get(_key(s), s) for s in self.sources]
        self._sources_changed()

    def on_clear(self):
        self.sources = []
        self._sources_changed()
        self.status.config(text="クリアしました")

    # ---------------- プレビュー ----------------
    def _reset_preview(self):
        self.plan = None
        self.plan_sig = None
        for row in self.tree.get_children():
            self.tree.delete(row)

    def _make_plan(self):
        matcher = build_matcher(self.filter_mode.get(), self.filter_text.get(), self.filter_case.get())
        renamer = build_renamer(self.mode.get(), self._rule_params())
        files = collect_files(self.sources, self.include_sub.get())
        if matcher:
            files = [f for f in files if matcher(os.path.basename(f))]
        files.sort(key=lambda p: (natural_key(os.path.dirname(p)), natural_key(os.path.basename(p))))
        return build_plan(files, renamer)

    def on_preview(self):
        if not self.sources:
            messagebox.showwarning("警告", "先にフォルダまたはファイルを指定してください！")
            return
        try:
            items = self._make_plan()
        except ValueError as e:
            messagebox.showwarning("警告", str(e))
            return

        self._reset_preview()
        self.plan = items
        self.plan_sig = self._signature()

        for it in items:
            tags = ()
            if it["status"] in BAD_STATUSES:
                tags = ("bad",)
            elif it["status"] == ST_SAME:
                tags = ("same",)
            self.tree.insert("", "end", values=(it["status"], it["old"], it["new"], it["dir"], it["note"]),
                             tags=tags)

        total = len(items)
        n_ok = sum(1 for it in items if it["status"] == ST_OK)
        n_same = sum(1 for it in items if it["status"] == ST_SAME)
        n_bad = sum(1 for it in items if it["status"] in BAD_STATUSES)
        if total == 0:
            self.status.config(text="条件に一致するファイルがありません")
        else:
            msg = f"プレビュー：対象 {total} 件 ／ 変更 {n_ok} 件 ／ 変更なし {n_same} 件"
            if n_bad:
                msg += f" ／ 要修正 {n_bad} 件（赤字の行を確認してください）"
            self.status.config(text=msg)

    # ---------------- 実行 ----------------
    def on_execute(self):
        if self.plan is None:
            messagebox.showwarning("警告", "先に「プレビュー」で変更内容を確認してください！")
            return
        if self.plan_sig != self._signature():
            messagebox.showwarning("警告", "プレビュー後に設定が変更されています。もう一度「プレビュー」してください！")
            return
        if any(it["status"] in BAD_STATUSES for it in self.plan):
            messagebox.showwarning("警告", "競合または不正な項目（赤字の行）があるため実行できません。\n"
                                          "ルールや絞り込み条件を見直してください。")
            return

        todo = [(it["src"], os.path.join(it["dir"], it["new"])) for it in self.plan if it["status"] == ST_OK]
        if not todo:
            messagebox.showinfo("情報", "変更が必要なファイルがありません。")
            return
        if not messagebox.askyesno("確認", f"{len(todo)} 件のファイルをリネームします。よろしいですか？\n"
                                          "（実行後は「直前の操作を元に戻す」で取り消せます）"):
            return

        self.status.config(text="リネーム処理中...")
        self.update()
        done, failures = apply_renames(todo)

        saved = True
        if done:
            saved = save_undo_log(done)
            self._remap_sources(done)
        self._refresh_undo_button()

        msg = f"成功：{len(done)} 件"
        if failures:
            lines = "\n".join(f"・{os.path.basename(s)}：{reason[:80]}" for s, reason in failures[:5])
            msg += f"\n失敗：{len(failures)} 件\n{lines}"
            messagebox.showerror("一部失敗", msg)
        else:
            if not saved:
                msg += "\n（元に戻す情報を保存できませんでした）"
            messagebox.showinfo("完了", msg)
        self.status.config(text="準備完了")

    # ---------------- 元に戻す ----------------
    def _refresh_undo_button(self):
        self.undo_btn.config(state="normal" if load_undo_log() else "disabled")

    def on_undo(self):
        pairs = load_undo_log()
        if not pairs:
            messagebox.showinfo("情報", "元に戻せる操作がありません。")
            self._refresh_undo_button()
            return
        if not messagebox.askyesno("確認", f"直前のリネーム（{len(pairs)} 件）を元に戻します。よろしいですか？"):
            return

        done, failures = apply_renames([(new, old) for old, new in pairs])
        failed_src = {s for s, _ in failures}
        remaining = [(old, new) for old, new in pairs if new in failed_src]
        if remaining:
            save_undo_log(remaining)
        else:
            clear_undo_log()
        if done:
            self._remap_sources(done)
        self._refresh_undo_button()

        msg = f"元に戻しました：{len(done)} 件"
        if failures:
            lines = "\n".join(f"・{os.path.basename(s)}：{reason[:80]}" for s, reason in failures[:5])
            msg += f"\n失敗：{len(failures)} 件\n{lines}"
            messagebox.showerror("一部失敗", msg)
        else:
            messagebox.showinfo("完了", msg)
        self.status.config(text="準備完了")


if __name__ == "__main__":
    app = RenameToolApp()
    app.mainloop()
