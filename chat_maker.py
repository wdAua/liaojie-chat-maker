# -*- coding: utf-8 -*-
"""
聊界  -  微信 / QQ 风格聊天记录生成器
版本：莉依娜专属
开发者：我的Au啊
官网：http://wdaua.github.io/audgw

特性：
  * 全部数据 / 资源使用“程序目录”绝对路径，任意工作目录启动均正常
  * 健壮的图片处理（自动转换色彩模式、限制尺寸、圆角显示）
  * 现代化卡片式界面
  * 完整调试日志（debug.log）
  * 保存 PNG 时按当前样式真实渲染气泡 / 头像 / 三角 / 图片
"""

import os
import sys
import json
import shutil
import logging
import webbrowser
from datetime import datetime

import customtkinter as ctk
from tkinter import messagebox, filedialog, colorchooser
from PIL import Image, ImageTk, ImageDraw, ImageFont

# ----------------------------------------------------------------------------
# 路径：无论从哪个工作目录启动、是否被 PyInstaller 打包，都能定位到程序目录
# ----------------------------------------------------------------------------
if getattr(sys, "frozen", False):  # PyInstaller 打包后
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
    BUNDLE_DIR = getattr(sys, "_MEIPASS", BASE_DIR)  # 打包进 exe 的只读资源
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = BASE_DIR

DATA_FILE = os.path.join(BASE_DIR, "chat_data.json")
BACKUP_FILE = os.path.join(BASE_DIR, "chat_data.bak.json")
AVATAR_DIR = os.path.join(BASE_DIR, "avatars")
CHAT_IMAGES_DIR = os.path.join(BASE_DIR, "chat_images")
ICON_FILE = os.path.join(BASE_DIR, "软件不是.png")
WECHAT_ICON = os.path.join(BASE_DIR, "微信.png")
QQ_ICON = os.path.join(BASE_DIR, "qq.png")
LOG_FILE = os.path.join(BASE_DIR, "debug.log")

for _d in (AVATAR_DIR, CHAT_IMAGES_DIR):
    try:
        os.makedirs(_d, exist_ok=True)
    except Exception as _e:
        # 极端情况下程序目录不可写，退回到用户目录
        BASE_DIR = os.path.expanduser("~")
        DATA_FILE = os.path.join(BASE_DIR, "chat_data.json")
        AVATAR_DIR = os.path.join(BASE_DIR, "avatars")
        CHAT_IMAGES_DIR = os.path.join(BASE_DIR, "chat_images")
        os.makedirs(AVATAR_DIR, exist_ok=True)
        os.makedirs(CHAT_IMAGES_DIR, exist_ok=True)

# ----------------------------------------------------------------------------
# 日志
# ----------------------------------------------------------------------------
logger = logging.getLogger("liaojie")
logger.setLevel(logging.DEBUG)
try:
    _fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    _fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(_fh)
except Exception:
    pass
_sh = logging.StreamHandler()
_sh.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
logger.addHandler(_sh)


def resource_path(name):
    """优先程序目录，其次打包资源目录。"""
    p1 = os.path.join(BASE_DIR, name)
    if os.path.exists(p1):
        return p1
    p2 = os.path.join(BUNDLE_DIR, name)
    return p2 if os.path.exists(p2) else p1


# ----------------------------------------------------------------------------
# 配色 / 主题
# ----------------------------------------------------------------------------
class C:
    APP_BG = "#e9edf3"       # 最外层背景
    PANEL = "#ffffff"        # 卡片 / 面板
    BRAND = "#07c160"        # 微信绿 / 主色
    BRAND_D = "#06a050"
    QQ = "#12b7f5"           # QQ 蓝
    QQ_D = "#0e9cd4"
    INK = "#1f2329"          # 主文字
    SUB = "#8a919f"          # 次文字
    LINE = "#eceff3"         # 分隔线
    CHAT_BG = "#ededed"      # 聊天默认灰
    WX_ME = "#95ec69"        # 微信自己气泡
    OTHER = "#ffffff"        # 对方气泡
    DANGER = "#ff4d4f"
    WARN_BG = "#fff6f0"
    WARN_INK = "#d4691e"
    SIDEBAR = "#10241d"      # 品牌侧栏深色


ctk.set_appearance_mode("light")

FONT_CANDIDATES = ["Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC",
                   "Noto Sans CJK SC", "Source Han Sans SC", "Segoe UI", "Arial"]
FONT_FAMILY = None  # 建 root 后确定


def f(size, weight="normal"):
    fam = FONT_FAMILY or "Microsoft YaHei UI"
    return (fam, size, weight)


def pil_font(size, bold=False):
    candidates = [
        "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold
        else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


# ----------------------------------------------------------------------------
# 图片工具
# ----------------------------------------------------------------------------
def load_pil(path):
    """打开图片并统一为 RGBA，兼容 CMYK / P / L / GIF 等所有模式。"""
    img = Image.open(path)
    img.load()
    mode = img.mode
    if mode == "CMYK":
        img = img.convert("RGB")
    if mode in ("P", "LA", "L", "1", "I;16", "I"):
        img = img.convert("RGBA")
    if img.mode not in ("RGBA", "RGB"):
        img = img.convert("RGBA")
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return img


def shape_mask(size, style):
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    if style == "qq":
        d.ellipse((0, 0, size, size), fill=255)
    else:
        # 微信是“较方的圆角矩形”，圆角很小（约 10%）
        r = max(2, int(size * 0.10))
        try:
            d.rounded_rectangle((0, 0, size, size), radius=r, fill=255)
        except AttributeError:
            d.rectangle((0, 0, size, size), fill=255)
    return mask


def shaped_avatar(path, size, style):
    """读取头像并按样式裁剪形状，返回 CTkImage。"""
    if not path or not os.path.exists(path):
        return None
    try:
        img = load_pil(path)
        # 居中正方形裁切（cover，铺满不留黑边）
        w, h = img.size
        s = min(w, h)
        img = img.crop(((w - s) // 2, (h - s) // 2, (w + s) // 2, (h + s) // 2))
        img = img.resize((size, size), Image.Resampling.LANCZOS)
        # 把透明 / 旧烤形状的边缘统一铺白底，避免黑边、蓝边伪影
        bg = Image.new("RGBA", (size, size), (255, 255, 255, 255))
        bg.alpha_composite(img)
        bg.putalpha(shape_mask(size, style))
        return ctk.CTkImage(bg, size=(size, size))
    except Exception as e:
        logger.warning("头像加载失败 %s: %s", path, e)
        return None


def chat_image(path, max_side=200):
    """读取聊天图片，限制最大边，统一 RGBA，返回 (CTkImage, PIL)。"""
    img = load_pil(path)
    w, h = img.size
    scale = min(1.0, max_side / max(w, h))
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    img = img.resize((nw, nh), Image.Resampling.LANCZOS)
    # 轻微圆角，观感更现代
    r = 8
    m = Image.new("L", (nw, nh), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, nw, nh), radius=r, fill=255)
    img.putalpha(m)
    return ctk.CTkImage(img, size=(nw, nh)), img


# ----------------------------------------------------------------------------
# 头像裁剪窗口（正方形裁切，拖拽 / 滚轮缩放，任意缩放比例下拖拽都准确）
# ----------------------------------------------------------------------------
class ImageCropper(ctk.CTkToplevel):
    def __init__(self, parent, image_path, callback, size=320):
        super().__init__(parent)
        self.image_path = image_path
        self.callback = callback
        self.size = size
        self.zoom = 1.0
        self.cx = self.cy = None
        self.drag = None
        try:
            self.src = load_pil(image_path)
        except Exception as e:
            messagebox.showerror("错误", f"无法打开图片：{e}")
            self.destroy()
            return
        w, h = self.src.size
        self.scale0 = size / min(w, h)   # 覆盖式铺满
        self.cx, self.cy = w / 2, h / 2

        self.title("裁剪头像")
        self.geometry(f"{size + 40}x{size + 150}")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        ctk.CTkLabel(self, text="拖动调整位置 · 滚轮缩放", font=f(12), text_color=C.SUB).pack(pady=(12, 4))
        self.preview = ctk.CTkLabel(self, text="", width=size, height=size)
        self.preview.pack(pady=4)
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=6)
        ctk.CTkButton(row, text="－", width=52, command=lambda: self.do_zoom(1 / 1.15)).pack(side="left", padx=4)
        ctk.CTkButton(row, text="＋", width=52, command=lambda: self.do_zoom(1.15)).pack(side="left", padx=4)
        ctk.CTkButton(row, text="重置", width=64, command=self.reset).pack(side="left", padx=4)
        row2 = ctk.CTkFrame(self, fg_color="transparent")
        row2.pack(pady=8)
        ctk.CTkButton(row2, text="确认裁剪", width=110, fg_color=C.BRAND, hover_color=C.BRAND_D,
                      command=self.confirm).pack(side="left", padx=8)
        ctk.CTkButton(row2, text="取消", width=80, fg_color="#c2c7d0", hover_color="#a8aeb8",
                      command=self.destroy).pack(side="left", padx=8)

        self.preview.bind("<Button-1>", self.start_drag)
        self.preview.bind("<B1-Motion>", self.on_drag)
        self.preview.bind("<MouseWheel>", self.on_wheel)
        self.preview.bind("<Button-4>", lambda e: self.do_zoom(1.1))
        self.preview.bind("<Button-5>", lambda e: self.do_zoom(1 / 1.1))
        self.redraw()

    def do_zoom(self, factor):
        self.zoom = max(1.0, min(6.0, self.zoom * factor))
        self.redraw()

    def on_wheel(self, e):
        self.do_zoom(1.1 if e.delta > 0 else 1 / 1.1)

    def reset(self):
        self.zoom = 1.0
        w, h = self.src.size
        self.cx, self.cy = w / 2, h / 2
        self.redraw()

    def start_drag(self, e):
        self.drag = (e.x, e.y)

    def on_drag(self, e):
        if not self.drag:
            return
        disp_scale = self.scale0 * self.zoom
        dx = (e.x - self.drag[0]) / disp_scale
        dy = (e.y - self.drag[1]) / disp_scale
        self.cx -= dx
        self.cy -= dy
        self.drag = (e.x, e.y)
        self.redraw()

    def _crop_square(self):
        w, h = self.src.size
        disp_scale = self.scale0 * self.zoom
        half = self.size / (2 * disp_scale)
        cx = min(max(half, self.cx), w - half)
        cy = min(max(half, self.cy), h - half)
        box = (cx - half, cy - half, cx + half, cy + half)
        sq = self.src.crop(box).resize((self.size, self.size), Image.Resampling.LANCZOS)
        return sq

    def redraw(self):
        sq = self._crop_square()
        self._photo = ImageTk.PhotoImage(sq)
        self.preview.configure(image=self._photo)

    def confirm(self):
        try:
            sq = self._crop_square().resize((240, 240), Image.Resampling.LANCZOS)
            tmp = os.path.join(AVATAR_DIR, f"crop_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.png")
            sq.save(tmp, "PNG")
            logger.info("头像裁剪完成: %s", tmp)
            if self.callback:
                self.callback(tmp)
            self.destroy()
        except Exception as e:
            logger.exception("裁剪保存失败")
            messagebox.showerror("错误", str(e))


# ----------------------------------------------------------------------------
# 主程序
# ----------------------------------------------------------------------------
class ChatMaker(ctk.CTk):
    def __init__(self):
        super().__init__()
        global FONT_FAMILY
        self.title("聊界")
        self.geometry("1380x800")
        self.minsize(1180, 700)

        # 数据
        self.users = []
        self.groups = []
        self.messages_dict = {}
        self.current_target = None
        self.current_style = "wechat"
        self.bg_color = C.CHAT_BG
        self.bg_image_path = None
        self.my_avatar = None
        self.current_role = "我"
        self.next_user_id = 1
        self.next_group_id = 1
        self._bg_photo = None
        self._img_cache = {}

        self.load_data()

        # 确定字体
        try:
            from tkinter import font as tkfont
            avail = set(tkfont.families(self))
            for cand in FONT_CANDIDATES:
                if cand in avail:
                    FONT_FAMILY = cand
                    break
        except Exception:
            FONT_FAMILY = "Microsoft YaHei UI"

        self.set_icon()
        self.build_layout()
        self.refresh_all()

        # 快捷键
        self.bind("<Control-s>", lambda e: self.save_png())
        self.bind("<Control-z>", self._global_recall)
        self.bind("<Control-c>", self._global_clear)

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        logger.info("聊界启动完成，样式=%s 用户数=%d 群数=%d",
                    self.current_style, len(self.users), len(self.groups))

    # ---------------- 布局 ----------------
    def set_icon(self):
        # Windows 任务栏需要显式 AppUserModelID，否则会显示 Python 默认图标
        if sys.platform.startswith("win"):
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    "liaojie.linayina.app")
            except Exception as e:
                logger.warning("设置 AppUserModelID 失败: %s", e)

        ico = resource_path("软件不是.ico")
        png = resource_path("软件不是.png")
        try:
            if os.path.exists(ico):
                self.iconbitmap(ico)
            if os.path.exists(png):
                # 必须保留引用，否则被垃圾回收后任务栏图标丢失
                self._icon_photo = ImageTk.PhotoImage(Image.open(png))
                self.iconphoto(True, self._icon_photo)
        except Exception as e:
            logger.warning("设置窗口图标失败: %s", e)

    def build_layout(self):
        root = ctk.CTkFrame(self, fg_color=C.APP_BG, corner_radius=0)
        root.pack(fill="both", expand=True)
        root.grid_columnconfigure(0, weight=0, minsize=190)
        root.grid_columnconfigure(1, weight=0, minsize=235)
        root.grid_columnconfigure(2, weight=1, minsize=340)
        root.grid_columnconfigure(3, weight=2, minsize=420)
        root.grid_rowconfigure(0, weight=1)

        self.a1 = ctk.CTkFrame(root, fg_color=C.SIDEBAR, corner_radius=0)
        self.a1.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=0)
        self.build_a1()

        self.a2 = ctk.CTkFrame(root, fg_color=C.PANEL, corner_radius=14)
        self.a2.grid(row=0, column=1, sticky="nsew", padx=(0, 8), pady=10)
        self.build_a2()

        self.a3 = ctk.CTkFrame(root, fg_color=C.PANEL, corner_radius=14)
        self.a3.grid(row=0, column=2, sticky="nsew", padx=(0, 8), pady=10)
        self.build_a3()

        self.a4 = ctk.CTkFrame(root, fg_color=self.bg_color, corner_radius=14)
        self.a4.grid(row=0, column=3, sticky="nsew", pady=10)
        self.build_a4()

    # ---------------- 区域1 ----------------
    def build_a1(self):
        wrap = ctk.CTkFrame(self.a1, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=16)

        p = resource_path("软件不是.png")
        if os.path.exists(p):
            try:
                logo = Image.open(p).resize((64, 64), Image.Resampling.LANCZOS)
                self._logo = ctk.CTkImage(logo, size=(64, 64))
                ctk.CTkLabel(wrap, image=self._logo, text="").pack(pady=(26, 8))
            except Exception:
                pass
        ctk.CTkLabel(wrap, text="聊 界", font=f(24, "bold"), text_color="#ffffff").pack()
        ctk.CTkLabel(wrap, text="莉依娜专属", font=f(12), text_color="#9fb8ac").pack(pady=(2, 14))

        warn = ctk.CTkFrame(wrap, fg_color="#1b3a2e", corner_radius=10)
        warn.pack(fill="x", pady=6)
        ctk.CTkLabel(warn,
                     text="⚠ 警 示\n\n仅用于合法用途\n禁止制造虚假证据\n禁止诈骗 / 敲诈\n禁止诽谤他人\n\n使用者自负法律责任",
                     font=f(11), text_color="#ffd9a8", justify="left").pack(padx=12, pady=12, anchor="w")

        bottom = ctk.CTkFrame(wrap, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", pady=14)
        ctk.CTkLabel(bottom, text="👨‍💻 开发者：我的Au啊", font=f(11), text_color="#cfe0d6").pack(anchor="w")
        ctk.CTkButton(bottom, text="🌐 官方网站", font=f(12), fg_color=C.BRAND, hover_color=C.BRAND_D,
                      height=34, command=lambda: webbrowser.open("http://wdaua.github.io/audgw")).pack(
            fill="x", pady=8)
        ctk.CTkLabel(bottom, text="© 2026 聊界", font=f(10), text_color="#7d9587").pack()

    # ---------------- 区域2 ----------------
    def build_a2(self):
        top = ctk.CTkFrame(self.a2, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(16, 10))
        ctk.CTkLabel(top, text="用户 / 群聊", font=f(16, "bold"), text_color=C.INK).pack(side="left")
        ctk.CTkButton(top, text="＋ 添加", width=74, height=32, fg_color=C.BRAND, hover_color=C.BRAND_D,
                      font=f(13), command=self.add_dialog).pack(side="right")
        self.user_list = ctk.CTkScrollableFrame(self.a2, fg_color="transparent")
        self.user_list.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def display_name(self, u):
        n = (u.get("name") or "?").strip()
        note = (u.get("note") or "").strip()
        return f"{n}（{note}）" if note else n

    def refresh_user_list(self):
        for w in self.user_list.winfo_children():
            w.destroy()
        for u in self.users:
            self.user_row(u)
        for g in self.groups:
            self.group_row(g)
        if not self.users and not self.groups:
            ctk.CTkLabel(self.user_list, text="还没有用户\n点击右上角「添加」",
                         font=f(13), text_color=C.SUB, justify="center").pack(pady=40)

    def _item_frame(self, selected):
        return ctk.CTkFrame(self.user_list, fg_color="#eafaf1" if selected else "#f7f9fa",
                            corner_radius=10, border_width=2 if selected else 1,
                            border_color=C.BRAND if selected else "#eef0f3")

    def user_row(self, u):
        sel = self._is_sel("user", u["id"])
        fr = self._item_frame(sel)
        fr.pack(fill="x", pady=3)
        av = shaped_avatar(u.get("avatar"), 38, self.current_style)
        avw = ctk.CTkLabel(fr, image=av, text="") if av else ctk.CTkLabel(
            fr, text=(u.get("name") or "?")[0], width=38, height=38, fg_color=C.BRAND,
            text_color="white", corner_radius=19 if self.current_style == "qq" else 8, font=f(14, "bold"))
        avw.pack(side="left", padx=(8, 8), pady=8)
        ctk.CTkLabel(fr, text=self.display_name(u), font=f(13), text_color=C.INK,
                     anchor="w").pack(side="left", fill="x", expand=True)
        if sel:
            ctk.CTkLabel(fr, text="✓", font=f(14, "bold"), text_color=C.BRAND).pack(side="left", padx=2)
        bf = ctk.CTkFrame(fr, fg_color="transparent")
        bf.pack(side="right", padx=6)
        ctk.CTkButton(bf, text="🖼", width=28, height=28, fg_color="#eef2ff", hover_color="#dce5ff",
                      text_color="#3b5bdb", font=f(12), command=lambda: self.change_avatar(u)).pack(
            side="left", padx=1)
        ctk.CTkButton(bf, text="✕", width=28, height=28, fg_color="#ffecec", hover_color="#ffd9d9",
                      text_color=C.DANGER, font=f(12), command=lambda: self.delete_user(u)).pack(
            side="left", padx=1)
        for w in (fr, avw):
            w.bind("<Button-1>", lambda e, x=u: self.select_user(x))

    def group_row(self, g):
        sel = self._is_sel("group", g["id"])
        fr = self._item_frame(sel)
        fr.pack(fill="x", pady=3)
        ctk.CTkLabel(fr, text="👥", width=38, height=38, fg_color="#eef4ff",
                     corner_radius=10, font=f(17)).pack(side="left", padx=(8, 8), pady=8)
        ctk.CTkLabel(fr, text=f"{g['name']}（{len(g.get('members', []))}人）",
                     font=f(13), text_color=C.INK, anchor="w").pack(side="left", fill="x", expand=True)
        if sel:
            ctk.CTkLabel(fr, text="✓", font=f(14, "bold"), text_color=C.BRAND).pack(side="left", padx=2)
        bf = ctk.CTkFrame(fr, fg_color="transparent")
        bf.pack(side="right", padx=6)
        ctk.CTkButton(bf, text="👤", width=28, height=28, fg_color="#eef2ff", hover_color="#dce5ff",
                      text_color="#3b5bdb", font=f(12), command=lambda: self.group_avatars(g)).pack(
            side="left", padx=1)
        ctk.CTkButton(bf, text="✕", width=28, height=28, fg_color="#ffecec", hover_color="#ffd9d9",
                      text_color=C.DANGER, font=f(12), command=lambda: self.delete_group(g)).pack(
            side="left", padx=1)
        fr.bind("<Button-1>", lambda e, x=g: self.select_group(x))

    def _is_sel(self, t, i):
        return bool(self.current_target and self.current_target["type"] == t
                    and self.current_target["id"] == i)

    # ---------------- 区域3 ----------------
    def build_a3(self):
        head = ctk.CTkFrame(self.a3, fg_color="transparent")
        head.pack(fill="x", padx=18, pady=(16, 6))
        ctk.CTkLabel(head, text="编辑对话", font=f(16, "bold"), text_color=C.INK).pack(side="left")
        self.target_lbl = ctk.CTkLabel(head, text="未选择", font=f(12), text_color=C.SUB)
        self.target_lbl.pack(side="right")

        body = ctk.CTkScrollableFrame(self.a3, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        def section(title):
            ctk.CTkLabel(body, text=title, font=f(12, "bold"), text_color=C.SUB).pack(
                anchor="w", padx=6, pady=(10, 4))

        section("发送人")
        self.role_box = ctk.CTkComboBox(body, values=["请选择"], state="readonly", height=36,
                                        font=f(13), dropdown_font=f(13),
                                        button_color=C.BRAND, button_hover_color=C.BRAND_D)
        self.role_box.pack(fill="x", padx=4)

        section("消息内容（Enter 发送 · Shift+Enter 换行）")
        self.msg_box = ctk.CTkTextbox(body, height=84, font=f(14), corner_radius=10, wrap="word")
        self.msg_box.pack(fill="x", padx=4)
        try:
            self.msg_box.configure(undo=True, autoseparators=True, maxundo=-1)
        except Exception:
            pass
        self.msg_box.bind("<Return>", self._on_enter)
        self.msg_box.bind("<Control-z>", lambda e: (self.msg_box.event_generate("<<Undo>>"), "break")[1])

        section("时间（留空取当前，格式 14:30）")
        self.time_box = ctk.CTkEntry(body, height=36, font=f(13), placeholder_text="例如 14:30")
        self.time_box.pack(fill="x", padx=4)

        btns = ctk.CTkFrame(body, fg_color="transparent")
        btns.pack(fill="x", padx=2, pady=12)
        ctk.CTkButton(btns, text="📤 发送", height=36, fg_color=C.BRAND, hover_color=C.BRAND_D,
                      font=f(13), command=self.send_text).pack(side="left", expand=True, fill="x", padx=2)
        ctk.CTkButton(btns, text="🖼 图片", height=36, fg_color="#3b5bdb", hover_color="#3251c4",
                      font=f(13), command=self.send_image).pack(side="left", expand=True, fill="x", padx=2)
        ctk.CTkButton(btns, text="↩ 撤回", height=36, fg_color="#f0a020", hover_color="#d4881a",
                      font=f(13), command=lambda: self.recall(False)).pack(side="left", expand=True, fill="x", padx=2)
        ctk.CTkButton(btns, text="🗑 清空", height=36, fg_color=C.DANGER, hover_color="#e03e40",
                      font=f(13), command=self.clear).pack(side="left", expand=True, fill="x", padx=2)

        ctk.CTkFrame(body, height=1, fg_color=C.LINE).pack(fill="x", pady=6)
        section("聊天样式")
        self.style_seg = ctk.CTkSegmentedButton(
            body, values=["微信", "QQ"], height=36, font=f(13),
            selected_color=C.BRAND, selected_hover_color=C.BRAND_D,
            unselected_color="#eef1f5", unselected_hover_color="#e0e6ee",
            text_color=C.INK, command=self._seg_style)
        self.style_seg.pack(fill="x", padx=4)
        self.style_seg.set("微信" if self.current_style == "wechat" else "QQ")

        section("聊天背景")
        bg = ctk.CTkFrame(body, fg_color="transparent")
        bg.pack(fill="x", padx=2)
        ctk.CTkButton(bg, text="🎨 纯色", height=32, fg_color="#7950f2", hover_color="#6741d9",
                      font=f(12), command=self.pick_bg_color).pack(side="left", expand=True, fill="x", padx=2)
        ctk.CTkButton(bg, text="🖼 图片", height=32, fg_color="#7950f2", hover_color="#6741d9",
                      font=f(12), command=self.pick_bg_image).pack(side="left", expand=True, fill="x", padx=2)
        ctk.CTkButton(bg, text="恢复默认", height=32, fg_color="#adb5bd", hover_color="#959ca5",
                      font=f(12), command=self.reset_bg).pack(side="left", expand=True, fill="x", padx=2)

        section("我的头像")
        ar = ctk.CTkFrame(body, fg_color="#f7f9fa", corner_radius=10)
        ar.pack(fill="x", padx=4, pady=4)
        self.my_av_lbl = ctk.CTkLabel(ar, text="未设置", font=f(12), text_color=C.SUB)
        self.my_av_lbl.pack(side="left", padx=12, pady=8)
        ctk.CTkButton(ar, text="更换头像", width=92, height=32, fg_color=C.BRAND, hover_color=C.BRAND_D,
                      font=f(12), command=self.change_my_avatar).pack(side="right", padx=10, pady=8)

        section("快捷操作")
        ctk.CTkButton(body, text="💾 保存当前聊天为 PNG", height=36, fg_color=C.BRAND,
                      hover_color=C.BRAND_D, font=f(13), command=self.save_png).pack(
            fill="x", padx=4, pady=(0, 6))
        q = ctk.CTkFrame(body, fg_color="transparent")
        q.pack(fill="x", padx=2)
        ctk.CTkButton(q, text="📥 导入 JSON", height=32, fg_color="#7950f2", hover_color="#6741d9",
                      font=f(12), command=self.import_json).pack(side="left", expand=True, fill="x", padx=2)
        ctk.CTkButton(q, text="📤 导出 JSON", height=32, fg_color="#7950f2", hover_color="#6741d9",
                      font=f(12), command=self.export_json).pack(side="left", expand=True, fill="x", padx=2)

    def _seg_style(self, value):
        self.set_style("wechat" if value == "微信" else "qq")

    def _on_enter(self, e):
        # Shift+Enter 走默认换行；普通 Enter 发送
        if e.state & 0x0001:
            return
        self.send_text()
        return "break"

    # ---------------- 区域4 ----------------
    def build_a4(self):
        topbar = ctk.CTkFrame(self.a4, fg_color="#f7f8fa", height=52, corner_radius=14)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        self.chat_title = ctk.CTkLabel(topbar, text="聊界", font=f(15, "bold"), text_color=C.INK)
        self.chat_title.pack(pady=12)

        import tkinter as tk
        self.chat_body_wrap = ctk.CTkFrame(self.a4, fg_color=self.bg_color, corner_radius=0)
        self.chat_body_wrap.pack(fill="both", expand=True)
        # 原生 Canvas：背景图 / 纯色直接画在画布上，气泡作为 window 元素定位
        self.chat_canvas = tk.Canvas(self.chat_body_wrap, highlightthickness=0,
                                     bg=self.bg_color, borderwidth=0)
        self.chat_canvas.pack(fill="both", expand=True, padx=6, pady=6)
        # 滚动支持
        vbar = ctk.CTkScrollbar(self.chat_body_wrap, orientation="vertical",
                                command=self.chat_canvas.yview)
        self.chat_canvas.configure(yscrollcommand=vbar.set)
        vbar.place(relx=1.0, rely=0, relheight=1.0, anchor="ne")
        self.chat_canvas.bind("<MouseWheel>", self._canvas_wheel)
        self.chat_canvas.bind("<Button-4>", lambda e: self.chat_canvas.yview_scroll(-1, "units"))
        self.chat_canvas.bind("<Button-5>", lambda e: self.chat_canvas.yview_scroll(1, "units"))
        self._canvas_items = []
        self._canvas_bg_img = None

    def _canvas_wheel(self, e):
        self.chat_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

    # ---------------- 选择 / 删除 ----------------
    def select_user(self, u):
        self.current_target = {"type": "user", "id": u["id"]}
        logger.debug("选中用户 id=%s name=%s", u["id"], u.get("name"))
        self.refresh_all()

    def select_group(self, g):
        self.current_target = {"type": "group", "id": g["id"]}
        logger.debug("选中群 id=%s name=%s", g["id"], g.get("name"))
        self.refresh_all()

    def target_key(self):
        if not self.current_target:
            return None
        return f"{self.current_target['type']}_{self.current_target['id']}"

    def current_messages(self):
        k = self.target_key()
        return self.messages_dict.get(k, []) if k else []

    def role_values(self):
        if not self.current_target:
            return ["请选择"]
        if self.current_target["type"] == "user":
            u = self.find_user(self.current_target["id"])
            return ["我", u["name"]] if u else ["请选择"]
        g = self.find_group(self.current_target["id"])
        if not g:
            return ["请选择"]
        vals = ["我"]
        for mid in g.get("members", []):
            mu = self.find_user(mid)
            if mu:
                vals.append(mu["name"])
        return vals

    def find_user(self, uid):
        return next((x for x in self.users if x["id"] == uid), None)

    def find_group(self, gid):
        return next((x for x in self.groups if x["id"] == gid), None)

    def delete_user(self, u):
        if not messagebox.askyesno("确认", f"删除「{self.display_name(u)}」？\n相关聊天记录也会一并删除。"):
            return
        self.users = [x for x in self.users if x["id"] != u["id"]]
        for g in self.groups:
            if u["id"] in g.get("members", []):
                g["members"].remove(u["id"])
        self.messages_dict.pop(f"user_{u['id']}", None)
        if self._is_sel("user", u["id"]):
            self.current_target = None
        logger.info("删除用户 id=%s", u["id"])
        self.save_data()
        self.refresh_all()

    def delete_group(self, g):
        if not messagebox.askyesno("确认", f"删除群「{g['name']}」？\n该群聊天记录会一并删除，成员保留。"):
            return
        self.groups = [x for x in self.groups if x["id"] != g["id"]]
        self.messages_dict.pop(f"group_{g['id']}", None)
        if self._is_sel("group", g["id"]):
            self.current_target = None
        logger.info("删除群 id=%s", g["id"])
        self.save_data()
        self.refresh_all()

    # ---------------- 添加对话框 ----------------
    def add_dialog(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("添加")
        dlg.geometry("300x170")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()
        ctk.CTkLabel(dlg, text="选择创建类型", font=f(15, "bold"), text_color=C.INK).pack(pady=(22, 14))
        r = ctk.CTkFrame(dlg, fg_color="transparent")
        r.pack()
        ctk.CTkButton(r, text="👤 个人", width=110, height=40, fg_color=C.BRAND, hover_color=C.BRAND_D,
                      font=f(14), command=lambda: (dlg.destroy(), self.add_user_dialog())).pack(
            side="left", padx=8)
        ctk.CTkButton(r, text="👥 群聊", width=110, height=40, fg_color=C.QQ, hover_color=C.QQ_D,
                      font=f(14), command=lambda: (dlg.destroy(), self.add_group_dialog())).pack(
            side="left", padx=8)

    def add_user_dialog(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("添加个人用户")
        dlg.geometry("380x380")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()
        ctk.CTkLabel(dlg, text="姓名 *", font=f(13), text_color=C.SUB).pack(pady=(18, 4))
        ne = ctk.CTkEntry(dlg, width=240, height=36, font=f(13))
        ne.pack()
        ctk.CTkLabel(dlg, text="备注（选填）", font=f(13), text_color=C.SUB).pack(pady=(12, 4))
        te = ctk.CTkEntry(dlg, width=240, height=36, font=f(13))
        te.pack()
        state = {"path": None}
        ctk.CTkButton(dlg, text="选择头像", width=140, height=36, fg_color="#3b5bdb", hover_color="#3251c4",
                      font=f(13), command=lambda: self._pick_for(state, mark)).pack(pady=16)
        mark = ctk.CTkLabel(dlg, text="未选择头像（可稍后再设）", font=f(12), text_color=C.SUB)
        mark.pack()

        def confirm():
            name = ne.get().strip()
            if not name:
                messagebox.showwarning("提示", "请输入姓名")
                return
            uid = self.next_user_id
            avatar = ""
            if state["path"]:
                dest = os.path.join(AVATAR_DIR, f"user_{uid}.png")
                shutil.copy2(state["path"], dest)
                avatar = dest
            self.users.append({"id": uid, "name": name, "note": te.get().strip(), "avatar": avatar})
            self.next_user_id += 1
            logger.info("创建用户 id=%s name=%s avatar=%s", uid, name, bool(avatar))
            self.save_data()
            self.refresh_all()
            dlg.destroy()

        ctk.CTkButton(dlg, text="确认创建", width=160, height=40, fg_color=C.BRAND, hover_color=C.BRAND_D,
                      font=f(14), command=confirm).pack(pady=14)

    def _pick_for(self, state, mark):
        p = filedialog.askopenfilename(filetypes=[("图片", "*.png *.jpg *.jpeg *.gif *.bmp *.webp")])
        if p:
            state["path"] = p
            try:
                mark.configure(text="✅ 已选择：" + os.path.basename(p))
            except Exception:
                pass

    def add_group_dialog(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("添加群聊")
        dlg.geometry("430x540")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()
        ctk.CTkLabel(dlg, text="群聊名称 *", font=f(13), text_color=C.SUB).pack(pady=(16, 4))
        ne = ctk.CTkEntry(dlg, width=260, height=36, font=f(13))
        ne.pack()
        ctk.CTkLabel(dlg, text="群人数（2-20，不含“我”）", font=f(13), text_color=C.SUB).pack(pady=(10, 4))
        cnt = ctk.IntVar(value=3)
        ctk.CTkEntry(dlg, width=80, height=34, textvariable=cnt, font=f(13)).pack()
        mf = ctk.CTkScrollableFrame(dlg, height=210, fg_color="#f7f9fa", corner_radius=10)
        mf.pack(fill="both", expand=True, padx=16, pady=10)
        entries = []

        def rebuild(*_):
            try:
                n = max(2, min(20, int(cnt.get())))
            except Exception:
                n = 2
            for w in mf.winfo_children():
                w.destroy()
            entries.clear()
            for i in range(n):
                row = ctk.CTkFrame(mf, fg_color="transparent")
                row.pack(fill="x", pady=3, padx=8)
                ctk.CTkLabel(row, text=f"{i+1}", width=20, font=f(12), text_color=C.SUB).pack(side="left")
                a = ctk.CTkEntry(row, placeholder_text="姓名", width=110, height=32, font=f(12))
                a.pack(side="left", padx=3)
                b = ctk.CTkEntry(row, placeholder_text="备注", width=120, height=32, font=f(12))
                b.pack(side="left", padx=3)
                entries.append((a, b))

        cnt.trace_add("write", rebuild)
        rebuild()

        def confirm():
            name = ne.get().strip()
            if not name:
                messagebox.showwarning("提示", "请输入群聊名称")
                return
            member_ids = []
            for a, b in entries:
                nm = a.get().strip()
                if nm:
                    uid = self.next_user_id
                    self.users.append({"id": uid, "name": nm, "note": b.get().strip(), "avatar": ""})
                    member_ids.append(uid)
                    self.next_user_id += 1
            if len(member_ids) < 2:
                messagebox.showwarning("提示", "至少需要 2 名成员")
                return
            gid = self.next_group_id
            self.groups.append({"id": gid, "name": name, "members": member_ids})
            self.next_group_id += 1
            logger.info("创建群 id=%s name=%s 成员=%d", gid, name, len(member_ids))
            self.save_data()
            self.refresh_all()
            dlg.destroy()

        ctk.CTkButton(dlg, text="确认创建", width=160, height=40, fg_color=C.BRAND, hover_color=C.BRAND_D,
                      font=f(14), command=confirm).pack(pady=10)

    # ---------------- 头像更换 ----------------
    def _crop_into(self, dest, after):
        p = filedialog.askopenfilename(filetypes=[("图片", "*.png *.jpg *.jpeg *.gif *.bmp *.webp")])
        if not p:
            return

        def cb(cropped):
            shutil.copy2(cropped, dest)
            try:
                os.remove(cropped)
            except Exception:
                pass
            after(dest)

        ImageCropper(self, p, cb)

    def change_avatar(self, u):
        dest = os.path.join(AVATAR_DIR, f"user_{u['id']}.png")

        def after(path):
            u["avatar"] = path
            self.save_data()
            self.refresh_all()
            messagebox.showinfo("成功", f"「{u['name']}」头像已更新")

        self._crop_into(dest, after)

    def change_my_avatar(self):
        dest = os.path.join(AVATAR_DIR, "my_avatar.png")

        def after(path):
            self.my_avatar = path
            self.save_data()
            self.refresh_all()
            messagebox.showinfo("成功", "我的头像已更新")

        self._crop_into(dest, after)

    def group_avatars(self, g):
        dlg = ctk.CTkToplevel(self)
        dlg.title(f"群成员头像 - {g['name']}")
        dlg.geometry("340x440")
        dlg.transient(self)
        dlg.grab_set()
        ctk.CTkLabel(dlg, text="选择要修改头像的成员", font=f(14, "bold"), text_color=C.INK).pack(pady=12)
        sc = ctk.CTkScrollableFrame(dlg, fg_color="transparent")
        sc.pack(fill="both", expand=True, padx=12)
        for mid in g.get("members", []):
            u = self.find_user(mid)
            if not u:
                continue
            row = ctk.CTkFrame(sc, fg_color="#f7f9fa", corner_radius=8)
            row.pack(fill="x", pady=3)
            av = shaped_avatar(u.get("avatar"), 30, self.current_style)
            w0 = ctk.CTkLabel(row, image=av, text="") if av else ctk.CTkLabel(
                row, text=u["name"][0], width=30, height=30, fg_color=C.BRAND, text_color="white",
                corner_radius=15, font=f(12, "bold"))
            w0.pack(side="left", padx=8, pady=6)
            ctk.CTkLabel(row, text=self.display_name(u), font=f(12), text_color=C.INK).pack(
                side="left", fill="x", expand=True)
            ctk.CTkButton(row, text="更换", width=56, height=28, fg_color="#3b5bdb", hover_color="#3251c4",
                          font=f(11), command=lambda x=u: self.change_avatar(x)).pack(side="right", padx=8)
        ctk.CTkButton(dlg, text="关闭", fg_color="#adb5bd", hover_color="#959ca5",
                      command=dlg.destroy).pack(pady=10)

    # ---------------- 样式 / 背景 ----------------
    def set_style(self, style):
        self.current_style = style
        # 切换样式时自动恢复该样式的默认聊天背景（微信/QQ 默认都是 #ededed）
        self.bg_color = C.CHAT_BG
        self.bg_image_path = None
        logger.info("切换样式 -> %s（背景已恢复默认）", style)
        try:
            self.style_seg.set("微信" if style == "wechat" else "QQ")
        except Exception:
            pass
        self.save_data()
        self.refresh_all()

    def pick_bg_color(self):
        c = colorchooser.askcolor(title="选择背景色", initialcolor=self.bg_color)
        if c and c[1]:
            self.bg_color = c[1]
            self.bg_image_path = None
            logger.info("背景色 -> %s", self.bg_color)
            self.save_data()
            self.refresh_all()

    def pick_bg_image(self):
        p = filedialog.askopenfilename(filetypes=[("图片", "*.png *.jpg *.jpeg *.bmp *.webp")])
        if p:
            dest = os.path.join(BASE_DIR, f"bg_{datetime.now().strftime('%Y%m%d%H%M%S')}" +
                                os.path.splitext(p)[1])
            shutil.copy2(p, dest)
            self.bg_image_path = dest
            logger.info("背景图 -> %s", dest)
            self.save_data()
            self.refresh_all()

    def reset_bg(self):
        # 一键恢复微信默认聊天背景（同时清除自定义颜色和背景图）
        self.bg_color = C.CHAT_BG
        self.bg_image_path = None
        logger.info("背景已恢复默认 %s", C.CHAT_BG)
        self.save_data()
        self.refresh_all()

    # ---------------- 发送 ----------------
    def _selected_role(self):
        role = self.role_box.get()
        if not role or role == "请选择":
            return None
        return role

    def _now_time(self):
        t = self.time_box.get().strip()
        if t:
            return t
        return datetime.now().strftime("%H:%M")

    def send_text(self):
        if not self.current_target:
            messagebox.showinfo("提示", "请先在左侧选择用户或群聊")
            return
        text = self.msg_box.get("1.0", "end").strip()
        if not text:
            return
        role = self._selected_role()
        if not role:
            messagebox.showinfo("提示", "请选择发送人")
            return
        self.current_role = role
        self.add_message(role, text, self._now_time())
        self.msg_box.delete("1.0", "end")
        logger.debug("发送文本 role=%s len=%d", role, len(text))

    def send_image(self):
        if not self.current_target:
            messagebox.showinfo("提示", "请先在左侧选择用户或群聊")
            return
        p = filedialog.askopenfilename(filetypes=[("图片", "*.png *.jpg *.jpeg *.gif *.bmp *.webp")])
        if not p:
            return
        role = self._selected_role()
        if not role:
            messagebox.showinfo("提示", "请选择发送人")
            return
        ext = os.path.splitext(p)[1] or ".png"
        dest = os.path.join(CHAT_IMAGES_DIR,
                            datetime.now().strftime("%Y%m%d%H%M%S%f") + ext)
        try:
            shutil.copy2(p, dest)
            # 验证图片确实可被 PIL 打开
            with Image.open(dest) as check:
                check.verify()
        except Exception as e:
            logger.exception("图片复制/校验失败")
            messagebox.showerror("错误", f"图片发送失败：{e}")
            return
        self.current_role = role
        self.add_message(role, "[图片]", self._now_time(), image=dest)
        logger.info("发送图片 -> %s", dest)

    def add_message(self, role, text, t, image=None):
        sid = 0 if role == "我" else next(
            (u["id"] for u in self.users if u["name"] == role), None)
        msg = {"sid": sid, "name": role, "text": text, "time": t}
        if image:
            msg["img"] = True
            msg["img_path"] = image
        k = self.target_key()
        if k:
            self.messages_dict.setdefault(k, []).append(msg)
        self.save_data()
        self.refresh_display()

    # ---------------- 撤回 / 清空 / 删除 ----------------
    def recall(self, ask=True):
        msgs = self.current_messages()
        if not msgs:
            if not ask:
                messagebox.showinfo("提示", "没有可撤回的消息")
            return
        last = msgs[-1]
        if ask and not messagebox.askyesno("撤回", f"撤回「{last['name']}」的上一条消息？"):
            return
        k = self.target_key()
        if k:
            self.messages_dict[k].pop()
        logger.info("撤回上一条消息")
        self.save_data()
        self.refresh_display()

    def clear(self):
        if not self.current_target:
            messagebox.showinfo("提示", "请先选择用户或群聊")
            return
        if messagebox.askyesno("确认", "清空当前对话的所有消息？"):
            k = self.target_key()
            if k:
                self.messages_dict[k] = []
            logger.info("清空对话 %s", k)
            self.save_data()
            self.refresh_display()

    def delete_message(self, idx):
        k = self.target_key()
        if k and 0 <= idx < len(self.messages_dict[k]):
            self.messages_dict[k].pop(idx)
            self.save_data()
            self.refresh_display()

    # ---------------- 全局快捷键（按焦点区分） ----------------
    def _focus_is_editable(self):
        w = self.focus_get()
        cls = type(w).__name__
        return cls in ("CTkTextbox", "CTkEntry", "TkText", "Entry")

    def _global_recall(self, e):
        if self._focus_is_editable():
            return  # 输入框内 Ctrl+Z 交给文本撤销
        self.recall(True)

    def _global_clear(self, e):
        if self._focus_is_editable():
            return  # 输入框内 Ctrl+C 保留复制功能
        self.clear()

    # ---------------- 聊天区渲染 ----------------
    def refresh_edit(self):
        vals = self.role_values()
        if not self.current_target:
            self.target_lbl.configure(text="未选择")
            self.role_box.configure(values=["请选择"])
            self.role_box.set("请选择")
            self.chat_title.configure(text="聊界")
            return
        if self.current_target["type"] == "user":
            u = self.find_user(self.current_target["id"])
            self.target_lbl.configure(text="👤 " + (self.display_name(u) if u else ""))
            self.chat_title.configure(text=u["name"] if u else "聊界")
        else:
            g = self.find_group(self.current_target["id"])
            self.target_lbl.configure(text="👥 " + (g["name"] if g else ""))
            self.chat_title.configure(text=g["name"] if g else "聊界")
        self.role_box.configure(values=vals)
        if self.current_role in vals:
            self.role_box.set(self.current_role)
        else:
            self.role_box.set("我")
            self.current_role = "我"

    def refresh_display(self):
        import tkinter as tk
        cv = self.chat_canvas
        cv.delete("all")
        for w in getattr(self, "_canvas_widgets", []):
            try:
                w.destroy()
            except Exception:
                pass
        self._canvas_widgets = []

        self.update_idletasks()
        W = max(320, cv.winfo_width())
        use_img = bool(self.bg_image_path and os.path.exists(self.bg_image_path))
        base_bg = "#ffffff" if use_img else self.bg_color
        cv.configure(bg=base_bg)
        self.chat_body_wrap.configure(fg_color=base_bg)

        msgs = self.current_messages()
        pad, av, gap = 14, 40, 8
        bubble_max_w = int(W - 2 * pad - av - gap - 8)
        is_group = bool(self.current_target and self.current_target["type"] == "group")

        def place(widget, x, y, anchor):
            cv.create_window(x, y, window=widget, anchor=anchor)
            self._canvas_widgets.append(widget)

        y = 14
        if not msgs:
            ph = ctk.CTkLabel(cv, text="暂无消息\n在左侧编辑并发送", font=f(14),
                              text_color=C.SUB, fg_color="transparent", justify="center")
            place(ph, W / 2, 120, "n")
            cv.configure(scrollregion=(0, 0, W, 300))
            return

        last_time = None
        for m in msgs:
            is_me = (m["sid"] == 0 or m["name"] == "我")

            # 时间胶囊（居中）
            if m.get("time") and m["time"] != last_time:
                t = ctk.CTkLabel(cv, text=m["time"], font=f(11), fg_color="#cfd4d9",
                                 text_color="#555", corner_radius=6, padx=8, pady=2)
                self.update_idletasks()
                place(t, W / 2, y, "n")
                y += t.winfo_reqheight() + 6
                last_time = m["time"]

            top = y
            # 头像
            if is_me:
                av_img = shaped_avatar(self.my_avatar, av, self.current_style)
                fb = "我"
            else:
                u = next((x for x in self.users if x["name"] == m["name"]), None)
                av_img = shaped_avatar(u.get("avatar") if u else None, av, self.current_style)
                fb = (m["name"][0] if m.get("name") else "?")
            if av_img:
                avw = ctk.CTkLabel(cv, image=av_img, text="", fg_color="transparent")
            else:
                avw = ctk.CTkLabel(cv, text=fb, width=av, height=av,
                                   fg_color=C.BRAND if is_me else "#c9cdd4", text_color="white",
                                   corner_radius=av // 2 if self.current_style == "qq" else 6,
                                   font=f(14, "bold"))

            # 群成员名字
            nm = None
            name_h = 0
            if is_group:
                nm = ctk.CTkLabel(cv, text=m["name"], font=f(11), fg_color="transparent",
                                  text_color=(C.BRAND if is_me else "#3b5bdb"))
                self.update_idletasks()
                name_h = nm.winfo_reqheight()

            # 三角（微信、非图片）
            tri = None
            show_tri = (self.current_style == "wechat" and not m.get("img"))
            if show_tri:
                bgc_tri = (C.WX_ME if is_me else C.OTHER)
                tw, th = 5, 8
                ti = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
                d = ImageDraw.Draw(ti)
                if is_me:
                    d.polygon([(0, 0), (0, th), (tw, th // 2)], fill=bgc_tri)
                else:
                    d.polygon([(tw, 0), (tw, th), (0, th // 2)], fill=bgc_tri)
                tp = ctk.CTkImage(ti, size=(tw, th))
                tri = ctk.CTkLabel(cv, image=tp, text="", fg_color="transparent")
                tri._ref = tp

            # 气泡 / 图片
            if m.get("img"):
                ip = m.get("img_path", "")
                if ip and os.path.exists(ip):
                    cimg, _ = chat_image(ip, 200)
                    bub = ctk.CTkLabel(cv, image=cimg, text="", fg_color="transparent")
                    bub._ref = cimg
                else:
                    bub = ctk.CTkLabel(cv, text="[图片缺失]", font=f(12), text_color=C.DANGER,
                                       fg_color="transparent")
            else:
                if is_me:
                    bgc = C.WX_ME if self.current_style == "wechat" else C.QQ
                    tc = "#14241a" if self.current_style == "wechat" else "#ffffff"
                else:
                    bgc, tc = C.OTHER, C.INK
                bub = ctk.CTkLabel(cv, text=m["text"], font=f(13), fg_color=bgc,
                                   text_color=tc, corner_radius=8, padx=11, pady=7,
                                   wraplength=bubble_max_w, justify="left")

            self.update_idletasks()
            bw, bh = bub.winfo_reqwidth(), bub.winfo_reqheight()
            row_h = max(av, name_h + bh)

            if is_me:
                place(avw, W - pad - av / 2, top + av / 2, "c")
                bub_right = W - pad - av - gap - (6 if show_tri else 0)
                if show_tri:
                    place(tri, bub_right + 2, top + row_h / 2, "w")
                if nm:
                    place(nm, bub_right, top, "ne")
                place(bub, bub_right, top + name_h + bh / 2, "e")
            else:
                place(avw, pad + av / 2, top + av / 2, "c")
                bub_left = pad + av + gap + (6 if show_tri else 0)
                if show_tri:
                    place(tri, bub_left - 2, top + row_h / 2, "e")
                if nm:
                    place(nm, bub_left, top, "nw")
                place(bub, bub_left, top + name_h + bh / 2, "w")

            y = top + row_h + 6

        total_h = y + 10

        # 背景图：cover 铺满整张内容，并置于最底层
        if use_img:
            try:
                bg = Image.open(self.bg_image_path).convert("RGBA")
                bg = self._cover(bg, W, total_h)
                self._canvas_bg_img = ImageTk.PhotoImage(bg)
                item = cv.create_image(0, 0, anchor="nw", image=self._canvas_bg_img)
                cv.tag_lower(item)
            except Exception as e:
                logger.warning("背景图绘制失败: %s", e)

        cv.configure(scrollregion=(0, 0, W, total_h))
        self.after(20, lambda: cv.yview_moveto(1.0))

    @staticmethod
    @staticmethod
    def _cover(img, w, h):
        iw, ih = img.size
        scale = max(w / iw, h / ih)
        nw, nh = int(iw * scale), int(ih * scale)
        img = img.resize((nw, nh), Image.Resampling.LANCZOS)
        return img.crop(((nw - w) // 2, (nh - h) // 2, (nw + w) // 2, (nh + h) // 2))

    # ---------------- 保存 PNG（按样式真实渲染） ----------------
    def save_png(self):
        msgs = self.current_messages()
        if not msgs:
            messagebox.showinfo("提示", "当前没有消息可保存")
            return
        try:
            path = filedialog.asksaveasfilename(
                defaultextension=".png",
                initialfile=f"聊天记录_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
                filetypes=[("PNG 图片", "*.png")])
            if not path:
                return
            img = self.render_to_image(msgs)
            img.save(path)
            logger.info("PNG 已保存: %s", path)
            messagebox.showinfo("成功", f"已保存：\n{path}")
        except Exception as e:
            logger.exception("保存 PNG 失败")
            messagebox.showerror("错误", f"保存失败：{e}")

    def render_to_image(self, msgs):
        W = 480
        pad = 16
        av = 40
        f_time = pil_font(13)
        f_name = pil_font(13, bold=True)
        f_text = pil_font(16)
        max_text_w = W - 2 * pad - av - 30

        is_group = self.current_target["type"] == "group"

        def wrap(text, font):
            lines, cur = [], ""
            for ch in text:
                if ch == "\n":
                    lines.append(cur); cur = ""; continue
                test = cur + ch
                if ImageDraw.Draw(Image.new("RGB", (1, 1))).textlength(test, font=font) > max_text_w:
                    lines.append(cur); cur = ch
                else:
                    cur = test
            if cur or not lines:
                lines.append(cur)
            return lines

        # 先计算高度
        blocks = []
        last_time = None
        for m in msgs:
            is_me = m["sid"] == 0 or m["name"] == "我"
            item = {"m": m, "is_me": is_me, "show_time": False}
            if m.get("time") and m["time"] != last_time:
                item["show_time"] = True
                last_time = m["time"]
            if m.get("img") and os.path.exists(m.get("img_path", "")):
                im = load_pil(m["img_path"])
                sc = min(1.0, 200 / max(im.size))
                item["img_size"] = (max(1, int(im.size[0] * sc)), max(1, int(im.size[1] * sc)))
                item["h"] = item["img_size"][1]
            else:
                lines = wrap(m["text"], f_text)
                item["lines"] = lines
                item["h"] = len(lines) * 23 + 14
            if is_group:
                item["h"] += 18
            blocks.append(item)

        H = pad
        for b in blocks:
            H += (26 if b["show_time"] else 0) + b["h"] + 8
        H += pad

        canvas = Image.new("RGB", (W, H), self.bg_color)
        draw = ImageDraw.Draw(canvas)

        # 背景图
        if self.bg_image_path and os.path.exists(self.bg_image_path):
            bg = Image.open(self.bg_image_path).convert("RGBA").resize((W, H), Image.Resampling.LANCZOS)
            canvas.paste(bg, (0, 0))
            draw = ImageDraw.Draw(canvas)

        y = pad

        def draw_avatar(is_me, path, fallback):
            x = W - pad - av if is_me else pad
            sq = Image.new("RGBA", (av, av), (200, 205, 212, 255))
            if path and os.path.exists(path):
                try:
                    im = load_pil(path)
                    s = min(im.size)
                    im = im.crop(((im.size[0]-s)//2, (im.size[1]-s)//2,
                                  (im.size[0]+s)//2, (im.size[1]+s)//2)).resize((av, av),
                                                                               Image.Resampling.LANCZOS)
                    sq = im
                except Exception:
                    pass
            sq.putalpha(shape_mask(av, self.current_style))
            canvas.paste(sq, (x, y), sq)

        for b in blocks:
            m, is_me = b["m"], b["is_me"]
            if b["show_time"]:
                tw = draw.textlength(m["time"], font=f_time)
                draw.rounded_rectangle(((W-tw)//2 - 8, y, (W+tw)//2 + 8, y + 20),
                                       radius=6, fill=(207, 212, 217))
                draw.text(((W-tw)//2, y + 3), m["time"], font=f_time, fill=(85, 85, 85))
                y += 26

            row_top = y
            draw_avatar(is_me, self.my_avatar if is_me else next(
                (u.get("avatar") for u in self.users if u["name"] == m["name"]), None), m["name"][0])

            content_x_right = W - pad - av - 10
            content_x_left = pad + av + 10
            name_h = 18 if is_group else 0
            if is_group:
                nm = m["name"]
                nw = draw.textlength(nm, font=f_name)
                nx = content_x_right - nw if is_me else content_x_left
                col = (7, 193, 96) if is_me else (59, 91, 219)
                draw.text((nx, y), nm, font=f_name, fill=col)
            by = y + name_h

            if "img_size" in b:
                iw, ih = b["img_size"]
                ix = content_x_right - iw if is_me else content_x_left
                im = load_pil(m["img_path"]).resize((iw, ih), Image.Resampling.LANCZOS)
                mm = Image.new("L", (iw, ih), 0)
                ImageDraw.Draw(mm).rounded_rectangle((0, 0, iw, ih), radius=8, fill=255)
                im.putalpha(mm)
                canvas.paste(im, (ix, by), im)
            else:
                if is_me:
                    bubble = C.WX_ME if self.current_style == "wechat" else C.QQ
                    tcol = (20, 36, 26) if self.current_style == "wechat" else (255, 255, 255)
                else:
                    bubble, tcol = C.OTHER, C.INK
                # 计算气泡尺寸
                lw = max(draw.textlength(ln, font=f_text) for ln in b["lines"])
                bw_, bh_ = int(lw) + 22, len(b["lines"]) * 23 + 12
                bx2 = content_x_right if is_me else content_x_left
                bx1 = bx2 - bw_ if is_me else bx2
                bx2 = bx2 if is_me else bx2 + bw_
                draw.rounded_rectangle((bx1, by, bx2, by + bh_), radius=8, fill=bubble)
                # 三角（很小，垂直居中）
                if self.current_style == "wechat":
                    cy = by + bh_ // 2
                    if is_me:
                        draw.polygon([(bx2, cy - 4), (bx2 + 5, cy), (bx2, cy + 4)], fill=bubble)
                    else:
                        draw.polygon([(bx1, cy - 4), (bx1 - 5, cy), (bx1, cy + 4)], fill=bubble)
                ty = by + 6
                for ln in b["lines"]:
                    draw.text((bx1 + 11, ty), ln, font=f_text, fill=tcol)
                    ty += 23
            y = row_top + b["h"] + 8
        return canvas

    # ---------------- 导入 / 导出 ----------------
    def import_json(self):
        p = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not p:
            return
        if not self.current_target:
            messagebox.showinfo("提示", "请先选择要导入到哪个用户/群聊")
            return
        try:
            with open(p, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, list):
                raise ValueError("文件内容应为消息数组")
            k = self.target_key()
            count = 0
            for m in data:
                if "name" in m and "text" in m:
                    rec = {
                        "sid": m.get("sid", 0),
                        "name": m["name"],
                        "text": m["text"],
                        "time": m.get("time", datetime.now().strftime("%H:%M")),
                    }
                    if m.get("img") and m.get("img_path"):
                        rec["img"] = True
                        rec["img_path"] = m["img_path"]
                    self.messages_dict.setdefault(k, []).append(rec)
                    count += 1
            self.save_data()
            self.refresh_display()
            messagebox.showinfo("成功", f"已导入 {count} 条消息")
            logger.info("导入 JSON %s 条数=%d", p, count)
        except Exception as e:
            logger.exception("导入失败")
            messagebox.showerror("错误", f"导入失败：{e}")

    def export_json(self):
        msgs = self.current_messages()
        if not msgs:
            messagebox.showinfo("提示", "当前没有消息可导出")
            return
        p = filedialog.asksaveasfilename(defaultextension=".json",
                                         initialfile="聊天记录.json",
                                         filetypes=[("JSON", "*.json")])
        if p:
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(msgs, fh, ensure_ascii=False, indent=2)
            messagebox.showinfo("成功", f"已导出：{p}")
            logger.info("导出 JSON %s", p)

    # ---------------- 数据读写 ----------------
    def load_data(self):
        if not os.path.exists(DATA_FILE):
            logger.info("未发现数据文件，使用默认设置")
            return
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as fh:
                d = json.load(fh)
            self.users = d.get("users", [])
            self.groups = d.get("groups", [])
            self.messages_dict = d.get("messages_dict", {})
            self.next_user_id = d.get("next_user_id", 1)
            self.next_group_id = d.get("next_group_id", 1)
            self.current_style = d.get("current_style", "wechat")
            self.bg_color = d.get("bg_color", C.CHAT_BG)
            self.bg_image_path = d.get("bg_image_path")
            self.my_avatar = d.get("my_avatar")
            self.current_role = d.get("current_role", "我")
            logger.info("数据加载成功：用户%d 群%d", len(self.users), len(self.groups))
        except Exception as e:
            logger.exception("数据文件损坏")
            try:
                shutil.copy2(DATA_FILE, BACKUP_FILE)
            except Exception:
                pass
            messagebox.showwarning("提示",
                                   f"数据文件读取失败，已备份为 chat_data.bak.json。\n原因：{e}\n将使用默认设置。")

    def save_data(self):
        try:
            d = {
                "users": self.users, "groups": self.groups,
                "messages_dict": self.messages_dict,
                "next_user_id": self.next_user_id, "next_group_id": self.next_group_id,
                "current_style": self.current_style, "bg_color": self.bg_color,
                "bg_image_path": self.bg_image_path, "my_avatar": self.my_avatar,
                "current_role": self.current_role,
            }
            tmp = DATA_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(d, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, DATA_FILE)
        except Exception as e:
            logger.exception("保存数据失败")

    def refresh_all(self):
        self.refresh_user_list()
        self.refresh_edit()
        self.refresh_display()

    def on_close(self):
        self.save_data()
        logger.info("聊界退出")
        self.destroy()

    def run(self):
        self.mainloop()


if __name__ == "__main__":
    ChatMaker().run()
