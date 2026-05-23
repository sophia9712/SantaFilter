import sys
import time
import os
import threading
import numpy as np
import sounddevice as sd
import customtkinter as ctk
import tkinter as tk
import tkinter.ttk as ttk
import winreg
import requests
import webbrowser
import subprocess
from tkinter import messagebox

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Falta Pillow. Ejecuta: pip install Pillow")
    sys.exit()

try:
    import pystray
except ImportError:
    print("Falta pystray. Ejecuta: pip install pystray")
    sys.exit()

try:
    from pyrnnoise import RNNoise
except ImportError:
    print("Falta la IA. Ejecuta: pip install pyrnnoise")
    sys.exit()


# ─── CONSTANTES DE APP ────────────────────────────────────────────────────────
APP_NAME    = "SantaFilter"
REG_RUN     = r"Software\Microsoft\Windows\CurrentVersion\Run"
GITHUB_REPO = "sophia9712/SantaFilter"   # ← CAMBIA ESTO

def get_version():
    try:
        with open("version.txt", "r", encoding="utf-8") as f:
            return f.read().strip()
    except:
        return "1.0"

APP_VERSION = get_version()

if getattr(sys, "frozen", False):
    APP_PATH = sys.executable
    BASE_DIR = os.path.dirname(sys.executable)
else:
    APP_PATH = f'"{sys.executable}" "{os.path.abspath(__file__)}"'
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ─── PALETA DE COLORES ────────────────────────────────────────────────────────
COLORS = {
    "bg_deep":      "#0D1117",
    "bg_panel":     "#161B22",
    "bg_item":      "#1C2230",
    "bg_hover":     "#1F2D42",
    "bg_selected":  "#005F7F",
    "border":       "#2A3650",
    "border_glow":  "#00A8CC",
    "text_bright":  "#F0F6FC",
    "text_muted":   "#6E8098",
    "accent_blue":  "#00D2FF",
    "accent_green": "#00C97A",
    "accent_red":   "#FF4A6E",
    "scroll_track": "#161B22",
    "scroll_thumb": "#2A4060",
}


# ─── DropdownModerno (intacto) ───────────────────────────────────────────────
class DropdownModerno:
    def __init__(self, master, boton, opciones, callback_seleccion):
        self.master = master
        self.boton = boton
        self.opciones = opciones
        self.callback = callback_seleccion
        self.ventana_flotante = None
        self.abierto = False
        self.ultimo_cierre = 0
        self._hover_idx = None
        self.boton.configure(command=self.toggle)

    def toggle(self):
        if time.time() - self.ultimo_cierre < 0.2:
            return
        if self.abierto:
            self.cerrar()
        else:
            self.abrir()

    def abrir(self):
        self.ventana_flotante = tk.Toplevel(self.master)
        self.ventana_flotante.overrideredirect(True)
        self.ventana_flotante.attributes("-topmost", True)
        self.ventana_flotante.configure(bg=COLORS["border_glow"])

        frame = tk.Frame(self.ventana_flotante, bg=COLORS["bg_panel"], padx=1, pady=1)
        frame.pack(fill="both", expand=True)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("SF.Vertical.TScrollbar",
            gripcount=0, background=COLORS["scroll_thumb"],
            darkcolor=COLORS["scroll_thumb"], lightcolor=COLORS["scroll_thumb"],
            troughcolor=COLORS["scroll_track"], bordercolor=COLORS["bg_panel"],
            arrowcolor=COLORS["bg_panel"], arrowsize=0, relief="flat", width=5)
        style.map("SF.Vertical.TScrollbar",
            background=[("active", COLORS["accent_blue"]), ("pressed", COLORS["accent_blue"])])

        self.lista = tk.Listbox(frame,
            bg=COLORS["bg_item"], fg=COLORS["text_bright"],
            selectbackground=COLORS["bg_selected"], selectforeground="#FFFFFF",
            font=("Segoe UI", 11), bd=0, highlightthickness=0,
            relief="flat", activestyle="none", cursor="hand2")

        self.scroll = ttk.Scrollbar(frame, orient="vertical",
            command=self.lista.yview, style="SF.Vertical.TScrollbar")
        self.lista.configure(yscrollcommand=self.scroll.set)

        self.scroll.pack(side="right", fill="y", pady=6, padx=(0, 3))
        self.lista.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=4)

        for op in self.opciones:
            self.lista.insert(tk.END, op)

        self.lista.bind("<Motion>", self._on_hover)
        self.lista.bind("<Leave>", self._on_leave)
        self.lista.bind("<<ListboxSelect>>", self.seleccionar)
        self.ventana_flotante.bind("<FocusOut>", lambda e: self.cerrar())
        self.lista.bind("<MouseWheel>",
            lambda e: self.lista.yview_scroll(int(-1*(e.delta/120)), "units"))

        x = self.boton.winfo_rootx()
        y = self.boton.winfo_rooty() + self.boton.winfo_height() + 4
        ancho = self.boton.winfo_width()
        self.ventana_flotante.geometry(f"{ancho}x175+{x}+{y}")
        self.abierto = True
        self.ventana_flotante.focus_set()

    def _on_hover(self, event):
        idx = self.lista.nearest(event.y)
        if idx == self._hover_idx:
            return
        if self._hover_idx is not None:
            self.lista.itemconfig(self._hover_idx, bg=COLORS["bg_item"], fg=COLORS["text_bright"])
        self.lista.itemconfig(idx, bg=COLORS["bg_hover"], fg="#FFFFFF")
        self._hover_idx = idx

    def _on_leave(self, event):
        if self._hover_idx is not None:
            self.lista.itemconfig(self._hover_idx, bg=COLORS["bg_item"], fg=COLORS["text_bright"])
            self._hover_idx = None

    def seleccionar(self, event):
        if not self.lista.curselection():
            return
        idx = self.lista.curselection()[0]
        valor = self.lista.get(idx)
        texto_corto = (valor[:36] + "…") if len(valor) > 36 else valor
        self.boton.configure(text=texto_corto + "  ▾")
        self.callback(valor)
        self.cerrar()

    def cerrar(self):
        if self.ventana_flotante:
            self.ventana_flotante.destroy()
            self.ventana_flotante = None
        self.abierto = False
        self.ultimo_cierre = time.time()


# ─── TOOLTIP FLOTANTE (con tu texto original) ─────────────────────────────────
class TooltipIA:
    DELAY_MS = 400

    def __init__(self, widget, texto):
        self.widget = widget
        self.texto = texto
        self._ventana = None
        self._job = None
        widget.bind("<Enter>", self._programar)
        widget.bind("<Leave>", self._cancelar)
        widget.bind("<ButtonPress>", self._cancelar)

    def _programar(self, event=None):
        self._cancelar()
        self._job = self.widget.after(self.DELAY_MS, self._mostrar)

    def _cancelar(self, event=None):
        if self._job:
            self.widget.after_cancel(self._job)
            self._job = None
        if self._ventana:
            self._ventana.destroy()
            self._ventana = None

    def _mostrar(self):
        if self._ventana:
            return
        x = self.widget.winfo_rootx() + self.widget.winfo_width() + 10
        y = self.widget.winfo_rooty() - 20
        self._ventana = tw = tk.Toplevel(self.widget)
        tw.overrideredirect(True)
        tw.attributes("-topmost", True)
        tw.configure(bg=COLORS["border_glow"])
        frame = tk.Frame(tw, bg=COLORS["bg_panel"], padx=14, pady=12)
        frame.pack(fill="both", expand=True, padx=1, pady=1)
        tk.Label(frame, text=self.texto, justify="left", font=("Segoe UI", 10),
                 fg=COLORS["text_bright"], bg=COLORS["bg_panel"], wraplength=270).pack()
        tw.geometry(f"+{x}+{y}")


# ─── APLICACIÓN PRINCIPAL ─────────────────────────────────────────────────────
class SantaFilterApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("520x510")
        ctk.set_appearance_mode("Dark")
        self.configure(fg_color=COLORS["bg_deep"])

        self.encendido = False
        self.hilo_audio = None
        self.fuerza_aislamiento = 0.95
        self.minimizar_a_bandeja_activo = True
        self._icono_bandeja = None

        self.dispositivos = sd.query_devices()
        self.dispositivos_entrada = self.filtrar_dispositivos(es_entrada=True)
        self.dispositivos_salida  = self.filtrar_dispositivos(es_entrada=False)
        self.mic_seleccionado  = ""
        self.cable_seleccionado = ""

        self.frame_main = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_ajustes = ctk.CTkFrame(self, fg_color="transparent")

        self._crear_pantalla_principal()
        self._crear_pantalla_ajustes()

        self.frame_main.pack(fill="both", expand=True)

        self._iniciar_bandeja()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        threading.Thread(target=self._check_for_update, daemon=True).start()

    def _crear_pantalla_principal(self):
        for widget in self.frame_main.winfo_children():
            widget.destroy()

        self.label_titulo = ctk.CTkLabel(self.frame_main, text=APP_NAME,
            font=("Segoe UI", 38, "bold"), text_color=COLORS["accent_blue"])
        self.label_titulo.pack(pady=(18, 18))

        # Todo tu código original...
        ctk.CTkLabel(self.frame_main, text="Entrada de Micrófono",
            font=("Segoe UI", 13), text_color=COLORS["text_muted"]).pack(pady=(0, 4))

        self.boton_entrada = ctk.CTkButton(self.frame_main, text="Cargando…  ▾",
            width=360, height=40, fg_color=COLORS["bg_item"],
            hover_color=COLORS["bg_hover"], border_color=COLORS["border"],
            border_width=1, text_color=COLORS["text_bright"],
            font=("Segoe UI", 12), anchor="center", corner_radius=8)
        self.boton_entrada.pack(pady=(0, 10))

        nombres_entrada = list(self.dispositivos_entrada.keys())
        self.menu_entrada = DropdownModerno(self.frame_main, self.boton_entrada, nombres_entrada, self.set_entrada)

        ctk.CTkLabel(self.frame_main, text="Salida Cable Virtual",
            font=("Segoe UI", 13), text_color=COLORS["text_muted"]).pack(pady=(0, 4))

        self.boton_salida = ctk.CTkButton(self.frame_main, text="Cargando…  ▾",
            width=360, height=40, fg_color=COLORS["bg_item"],
            hover_color=COLORS["bg_hover"], border_color=COLORS["border"],
            border_width=1, text_color=COLORS["text_bright"],
            font=("Segoe UI", 12), anchor="center", corner_radius=8)
        self.boton_salida.pack(pady=(0, 10))

        nombres_salida = list(self.dispositivos_salida.keys())
        self.menu_salida = DropdownModerno(self.frame_main, self.boton_salida, nombres_salida, self.set_salida)

        fila_slider = tk.Frame(self.frame_main, bg=COLORS["bg_deep"])
        fila_slider.pack(pady=(10, 4))

        self.label_slider = tk.Label(fila_slider,
            text="Modo: Equilibrio Natural  ·  95% IA",
            font=("Segoe UI", 11), fg=COLORS["text_muted"], bg=COLORS["bg_deep"])
        self.label_slider.pack(side="left")

        icono_info = tk.Label(fila_slider, text="  ⓘ",
            font=("Segoe UI", 13), fg=COLORS["accent_blue"],
            bg=COLORS["bg_deep"], cursor="hand2")
        icono_info.pack(side="left")

        TOOLTIP_TEXTO = (
            "Supresor de ruido por IA\n\n"
            "↓ Bajar  →  Voz más natural, pero se cuela\n"
            "            más ruido de fondo.\n\n"
            "↑ Subir  →  Ruido más suprimido, pero la\n"
            "            voz puede sonar más procesada.\n\n"
            "✦ 95% es el punto óptimo: voz clara\n"
            "  y sin ruidos molestos.\n\n"
            "⚠ Por encima de 95% la voz puede\n"
            "  sonar robótica. Úselo bajo su riesgo."
        )
        TooltipIA(icono_info, TOOLTIP_TEXTO)

        self.slider_sensibilidad = ctk.CTkSlider(self.frame_main,
            from_=0.70, to=1.0, number_of_steps=30,
            command=self.actualizar_sensibilidad, width=340,
            button_color=COLORS["accent_blue"], button_hover_color="#00B8E0",
            progress_color=COLORS["accent_blue"], fg_color=COLORS["border"])
        self.slider_sensibilidad.set(0.95)
        self.slider_sensibilidad.pack(pady=(0, 6))

        self.label_estado = ctk.CTkLabel(self.frame_main, text="● FILTRO INACTIVO",
            font=("Segoe UI", 13, "bold"), text_color=COLORS["accent_red"])
        self.label_estado.pack(pady=(14, 6))

        self.boton_encender = ctk.CTkButton(self.frame_main, text="INICIAR SANTAFILTER",
            command=self.conmutar_sistema, fg_color=COLORS["accent_green"],
            hover_color="#00A85E", font=("Segoe UI", 14, "bold"),
            height=48, width=300, corner_radius=10, text_color="#FFFFFF")
        self.boton_encender.pack(pady=6)

        btn_ajustes = tk.Label(self.frame_main, text="⚙  Ajustes",
            font=("Segoe UI", 11), fg=COLORS["text_muted"],
            bg=COLORS["bg_deep"], cursor="hand2")
        btn_ajustes.pack(pady=(10, 4))
        btn_ajustes.bind("<Button-1>", lambda e: self.mostrar_ajustes())
        btn_ajustes.bind("<Enter>", lambda e: btn_ajustes.configure(fg=COLORS["accent_blue"]))
        btn_ajustes.bind("<Leave>", lambda e: btn_ajustes.configure(fg=COLORS["text_muted"]))

        if nombres_entrada:
            t = nombres_entrada[0]
            self.boton_entrada.configure(text=(t[:36]+"…" if len(t)>36 else t)+"  ▾")
            self.set_entrada(nombres_entrada[0])

        for nombre in nombres_salida:
            if "cable" in nombre.lower():
                t = nombre
                self.boton_salida.configure(text=(t[:36]+"…" if len(t)>36 else t)+"  ▾")
                self.set_salida(nombre)
                break

    def _crear_pantalla_ajustes(self):
        for widget in self.frame_ajustes.winfo_children():
            widget.destroy()

        btn_back = tk.Label(self.frame_ajustes, text="← Inicio",
                            font=("Segoe UI", 15, "bold"), fg=COLORS["accent_blue"],
                            bg=COLORS["bg_deep"], cursor="hand2")
        btn_back.pack(pady=20, anchor="w", padx=24)
        btn_back.bind("<Button-1>", lambda e: self.mostrar_principal())

        ctk.CTkLabel(self.frame_ajustes, text="⚙   Ajustes",
                     font=("Segoe UI", 17, "bold"),
                     text_color=COLORS["accent_blue"]).pack(pady=(20, 14))

        self.sw_inicio = self._build_fila(
            "Iniciar con Windows",
            "Se abre automáticamente al encender el equipo.",
            self._toggle_inicio_windows
        )

        self.sw_bandeja = self._build_fila(
            "Minimizar a bandeja al cerrar",
            "Al cerrar la ventana, SantaFilter sigue activo en segundo plano.",
            self._toggle_bandeja
        )

        ctk.CTkLabel(self.frame_ajustes,
                     text=f"{APP_NAME} {APP_VERSION}  ·  Supresor de ruido por IA",
                     font=("Segoe UI", 10),
                     text_color=COLORS["text_muted"]).pack(pady=(10, 0))

        self._cargar_estado_ajustes()

    def _build_fila(self, texto, desc, comando):
        frame = ctk.CTkFrame(self.frame_ajustes, fg_color=COLORS["bg_panel"], corner_radius=10)
        frame.pack(fill="x", padx=22, pady=(0, 10))

        row = tk.Frame(frame, bg=COLORS["bg_panel"])
        row.pack(fill="x", padx=16, pady=(12, 4))

        tk.Label(row, text=texto, font=("Segoe UI", 12),
                 fg=COLORS["text_bright"], bg=COLORS["bg_panel"]).pack(side="left")

        sw = ctk.CTkSwitch(row, text="", width=46,
                           progress_color=COLORS["accent_blue"],
                           button_color=COLORS["text_bright"],
                           command=comando)
        sw.pack(side="right")

        tk.Label(frame, text=desc, font=("Segoe UI", 10),
                 fg=COLORS["text_muted"], bg=COLORS["bg_panel"],
                 wraplength=290, justify="left").pack(padx=16, pady=(0, 12), anchor="w")
        return sw

    def _cargar_estado_ajustes(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN, 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, APP_NAME)
            winreg.CloseKey(key)
            self.sw_inicio.select()
        except:
            self.sw_inicio.deselect()

        if self.minimizar_a_bandeja_activo:
            self.sw_bandeja.select()
        else:
            self.sw_bandeja.deselect()

    def _toggle_inicio_windows(self):
        activar = self.sw_inicio.get() == 1
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN, 0, winreg.KEY_SET_VALUE)
            if activar:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, APP_PATH)
            else:
                winreg.DeleteValue(key, APP_NAME)
            winreg.CloseKey(key)
        except:
            pass

    def _toggle_bandeja(self):
        self.minimizar_a_bandeja_activo = self.sw_bandeja.get() == 1

    def mostrar_ajustes(self):
        self.frame_main.pack_forget()
        self.frame_ajustes.pack(fill="both", expand=True)

    def mostrar_principal(self):
        self.frame_ajustes.pack_forget()
        self.frame_main.pack(fill="both", expand=True)

    # ===================== AUTO UPDATE =====================
    def _check_for_update(self):
        try:
            r = requests.get(f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest", timeout=8)
            if r.status_code == 200:
                data = r.json()
                latest = data["tag_name"].lstrip("v")
                download_url = next((a["browser_download_url"] for a in data.get("assets", []) if a["name"].endswith(".exe")), None)
                if latest > APP_VERSION and download_url:
                    self.after(0, lambda: self._mostrar_update(latest, download_url))
        except:
            pass

    def _mostrar_update(self, nueva_version, url):
        win = ctk.CTkToplevel(self)
        win.title("Actualización disponible")
        win.geometry("460x320")
        win.configure(fg_color=COLORS["bg_deep"])
        win.grab_set()

        ctk.CTkLabel(win, text="🎉 Nueva versión disponible", font=("Segoe UI", 18, "bold"), text_color=COLORS["accent_blue"]).pack(pady=20)
        ctk.CTkLabel(win, text=f"{APP_NAME} {nueva_version}", font=("Segoe UI", 16, "bold"), text_color=COLORS["text_bright"]).pack(pady=5)

        ctk.CTkButton(win, text="⬇ Descargar ahora", fg_color=COLORS["accent_green"], height=50,
                      font=("Segoe UI", 14, "bold"),
                      command=lambda: self._descargar_y_reiniciar(url, nueva_version, win)).pack(pady=30)

    def _descargar_y_reiniciar(self, url, nueva_version, win):
        win.destroy()
        try:
            response = requests.get(url, stream=True)
            new_exe = os.path.join(BASE_DIR, f"{APP_NAME}_{nueva_version}.exe")

            with open(new_exe, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            with open(os.path.join(BASE_DIR, "version.txt"), "w") as f:
                f.write(nueva_version)

            messagebox.showinfo("Actualizado", f"Versión {nueva_version} descargada.\nEl programa se reiniciará.")
            subprocess.Popen([new_exe])
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo actualizar:\n{e}")

    # ===================== BANDEJA Y AUDIO (intacto) =====================
    def _crear_imagen_icono(self):
        size = 64
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse([0, 0, 63, 63], fill="#0D1117")
        cy = 32
        puntos = [
            (6, cy), (12, cy), (16, cy-9), (20, cy+13),
            (24, cy-17), (28, cy+17), (32, cy-13), (36, cy+9),
            (40, cy-9), (44, cy+13), (48, cy), (58, cy),
        ]
        d.line(puntos, fill="#00D2FF", width=3)
        return img

    def _iniciar_bandeja(self):
        imagen = self._crear_imagen_icono()

        def mostrar(icon, item):
            self.after(0, self._mostrar_desde_bandeja)

        def salir(icon, item):
            self.after(0, self._salir_completamente)

        menu = pystray.Menu(
            pystray.MenuItem(f"Mostrar {APP_NAME}", mostrar, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir", salir),
        )

        self._icono_bandeja = pystray.Icon(APP_NAME, imagen, APP_NAME, menu)
        hilo = threading.Thread(target=self._icono_bandeja.run, daemon=True)
        hilo.start()

    def _on_close(self):
        if self.minimizar_a_bandeja_activo:
            self.withdraw()
        else:
            self._salir_completamente()

    def _mostrar_desde_bandeja(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def _salir_completamente(self):
        self.encendido = False
        if self._icono_bandeja:
            self._icono_bandeja.stop()
        self.destroy()

    def set_entrada(self, valor):
        self.mic_seleccionado = valor

    def set_salida(self, valor):
        self.cable_seleccionado = valor

    def filtrar_dispositivos(self, es_entrada=True):
        info_dispositivos = {}
        nombres_vistos = set()
        for idx, dev in enumerate(self.dispositivos):
            nombre_limpio = dev["name"].strip()
            if "Asignador de sonido" in nombre_limpio or "Primary Sound" in nombre_limpio:
                continue
            if es_entrada and dev["max_input_channels"] > 0:
                if nombre_limpio not in nombres_vistos:
                    nombres_vistos.add(nombre_limpio)
                    info_dispositivos[nombre_limpio] = idx
            elif not es_entrada and dev["max_output_channels"] > 0:
                if nombre_limpio not in nombres_vistos:
                    nombres_vistos.add(nombre_limpio)
                    info_dispositivos[nombre_limpio] = idx
        return info_dispositivos

    def actualizar_sensibilidad(self, valor):
        self.fuerza_aislamiento = float(valor)
        if self.fuerza_aislamiento >= 0.98:
            texto = "Modo: Máximo Aislamiento  ·  Voz procesada al máximo"
        elif self.fuerza_aislamiento <= 0.75:
            texto = "Modo: Voz de Estudio  ·  Puede colarse ruido tenue"
        else:
            texto = f"Modo: Equilibrio Natural  ·  {int(self.fuerza_aislamiento * 100)}% IA"
        self.label_slider.configure(text=texto)

    def conmutar_sistema(self):
        if not self.encendido:
            self.encendido = True
            self.label_estado.configure(text="● FILTRADO ACTIVO",
                text_color=COLORS["accent_green"])
            self.boton_encender.configure(text="DETENER SANTAFILTER",
                fg_color=COLORS["accent_red"], hover_color="#D43060")
            self.hilo_audio = threading.Thread(target=self.procesar_audio, daemon=True)
            self.hilo_audio.start()
        else:
            self.encendido = False
            self.label_estado.configure(text="● FILTRO INACTIVO",
                text_color=COLORS["accent_red"])
            self.boton_encender.configure(text="INICIAR SANTAFILTER",
                fg_color=COLORS["accent_green"], hover_color="#00A85E")

    def procesar_audio(self):
        try:
            idx_in  = self.dispositivos_entrada[self.mic_seleccionado]
            idx_out = self.dispositivos_salida[self.cable_seleccionado]

            rate_ia  = 48000
            chunk_ia = 480

            denoiser = RNNoise(sample_rate=rate_ia)
            ganancia_suave = 0.0

            def callback(indata, outdata, frames, time, status):
                nonlocal ganancia_suave
                if not self.encendido:
                    outdata.fill(0)
                    return

                audio_original = indata[:, 0].copy()
                audio_int16 = (audio_original * 32767.0).astype(np.int16)
                audio_ia = np.expand_dims(audio_int16, axis=0)

                for prob_voz, frame_limpio in denoiser.denoise_chunk(audio_ia):
                    audio_filtrado = frame_limpio[0].astype(np.float32) / 32767.0

                    mix_ia       = self.fuerza_aislamiento
                    mix_original = 1.0 - mix_ia
                    audio_combinado = (audio_filtrado * mix_ia) + (audio_original * mix_original)

                    prob_real = (prob_voz[0] if isinstance(prob_voz, (list, tuple, np.ndarray)) else prob_voz)

                    ganancia_objetivo = 0.0 if prob_real < 0.15 else 1.0

                    if ganancia_objetivo > ganancia_suave:
                        ganancia_suave += 0.20
                    else:
                        ganancia_suave -= 0.04

                    ganancia_suave = max(0.0, min(1.0, ganancia_suave))
                    outdata[:, 0] = np.clip(audio_combinado * ganancia_suave * 1.2, -1.0, 1.0)

            with sd.Stream(device=(idx_in, idx_out), samplerate=rate_ia,
                           channels=1, callback=callback, blocksize=chunk_ia):
                while self.encendido:
                    sd.sleep(100)

        except Exception as e:
            print(f"Error crítico: {e}")
            self.encendido = False


if __name__ == "__main__":
    app = SantaFilterApp()
    app.mainloop()