import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import tkinter.font as tkfont
import queue
import os
import itertools
import ast

# Tenta usar visual moderno
try:
    import ttkbootstrap as tb
    from ttkbootstrap.constants import *
    from ttkbootstrap.widgets import Meter, ToastNotification, ToolTip
    HAS_BOOTSTRAP = True
except ImportError:
    HAS_BOOTSTRAP = False
    print("ERRO CRÍTICO: Instale 'pip install ttkbootstrap' para ver o novo visual.")

# --- Importações dos Módulos Locais e Core ---
# Certifique-se que estes arquivos existem ou são mocks, conforme seu ambiente
from utils import build_yaml_text
from managers import RunnerManager
from core.state import AppState, get_sharc_root
from core.yaml_builder import build_yaml_structure

# Importa as abas existentes
from ui.tabs import (
    GeneralTab, IMTTab, VictimTab,
    PreviewTab, RunnerTab, ResultsTab, SingleEarthStationTab
)
PROJECT_ROOT = get_sharc_root()


class App(tb.Window if HAS_BOOTSTRAP else tk.Tk):
    def __init__(self):
        # 1. Configuração do Tema (Claro e Profissional)
        if HAS_BOOTSTRAP:
            super().__init__(themename="cosmo")
        else:
            super().__init__()

        self.title("SHARC – SHARing and Compatibility")
        self.geometry("1400x950")
        self.minsize(1280, 800)

        # 2. Inicializar Variáveis de Estado
        self.state_model = AppState()
        self.__dict__.update(self.state_model.__dict__)

        self.main_cli_path = tk.StringVar(
            value=os.path.join(PROJECT_ROOT / "main_cli.py"))

        # 3. Backend e Filas
        self.line_q = queue.Queue()
        self.runner_manager = RunnerManager(
            log_callback=self._safe_log,
            update_row_callback=self._safe_update_row
        )

        # Controle de Páginas
        self.current_frame = None  # Armazena o container visual atual
        self.frames = {}           # Armazena os containers visuais
        self.nav_buttons = {}      # Armazena os botões do menu

        # 4. Construção da Interface
        self._setup_custom_styles()
        self._build_layout()
        self._init_pages()

        # 5. Iniciar Loop
        self.after(100, self._drain_log_queue)

        # Seleciona página inicial
        self._switch_page("general")

        # Exibe Toast de boas-vindas
        self.after(800, self._show_welcome_toast)

    def _setup_custom_styles(self):
        """Define estilos para o tema CLARO."""
        style = tb.Style()

        # Fontes limpas
        base_font = ("Segoe UI", 10)

        # Verifica se tem fonte estilizada, senão usa padrão
        available_fonts = set(tkfont.families())
        header_font = ("Segoe UI", 22, "bold")  # Fonte profissional padrão

        style.configure(".", font=base_font)

        # Estilo do Título na Sidebar
        style.configure("Brand.TLabel", font=header_font,
                        foreground="#2C3E50")  # Azul escuro profissional

        # Botões de Navegação
        style.configure("Nav.TButton", font=("Segoe UI", 11),
                        anchor="w", padding=(20, 12))

        # Estilo dos Cards (Fundo branco com sombra leve seria ideal, aqui usamos flat)
        style.configure("Card.TFrame", background="#ffffff", relief="flat")

    def _build_layout(self):
        """Layout: Sidebar Cinza (Esq) + Conteúdo Branco (Dir)."""

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- A. Sidebar (Esquerda) ---
        self.sidebar = tb.Frame(self, bootstyle="light")
        self.sidebar.grid(row=0, column=0, rowspan=3, sticky="nsew")

        # Logo e Menu
        self._build_sidebar_header()

        self.menu_frame = tb.Frame(self.sidebar, bootstyle="light")
        self.menu_frame.pack(fill="both", expand=True, pady=10)

        # Monitor de Sistema (Meter)
        self._build_system_monitor()

        # --- B. Header Bar (Topo Direita) ---
        self.header = tb.Frame(self, bootstyle="bg-white", height=70)
        self.header.grid(row=0, column=1, sticky="ew")
        self._build_header_content()

        # Linha separadora sutil abaixo do header
        sep = tb.Separator(self.header, orient="horizontal",
                           bootstyle="secondary")
        sep.pack(side="bottom", fill="x")

        # --- C. Área de Conteúdo (Centro Direita) ---
        self.content_area = tb.Frame(self, padding=25)
        self.content_area.grid(row=1, column=1, sticky="nsew")

        # --- D. Status Bar (Rodapé Direita) ---
        self.status_bar = tb.Frame(self, bootstyle="primary")
        self.status_bar.grid(row=2, column=1, sticky="ew")
        self._build_footer_content()

    def _build_sidebar_header(self):
        frame = tb.Frame(self.sidebar, bootstyle="light")
        frame.pack(fill="x", pady=(30, 10), padx=20)

        # Título
        lbl = tb.Label(frame, text="SHARC", style="Brand.TLabel",
                       bootstyle="inverse-light")
        lbl.pack(anchor="w")

        sub = tb.Label(frame, text="SIMULATION MANAGER", font=("Segoe UI", 9, "bold"),
                       foreground="#7F8C8D", bootstyle="inverse-light")
        sub.pack(anchor="w")

        # Separador na sidebar
        tb.Separator(self.sidebar, bootstyle="secondary").pack(
            fill="x", padx=20, pady=15)

    def _build_system_monitor(self):
        monitor_frame = tb.Frame(self.sidebar, bootstyle="light", padding=15)
        monitor_frame.pack(side="bottom", fill="x", pady=10)

        tb.Label(monitor_frame, text="Global Progress", foreground="#7F8C8D",
                 font=("Segoe UI", 9, "bold"), bootstyle="inverse-light").pack(anchor="center", pady=5)

        self.sys_meter = Meter(
            monitor_frame,
            metersize=140,
            padding=5,
            amountused=0,
            metertype="full",
            subtext="Idle",
            interactive=False,
            bootstyle="primary",  # Azul cosmo
            stripethickness=10
        )
        self.sys_meter.pack(anchor="center")

    def _build_header_content(self):
        # Título da Página
        self.lbl_page_title = tb.Label(self.header, text="Dashboard",
                                       font=("Segoe UI", 18), foreground="#2C3E50")
        self.lbl_page_title.pack(side="left", padx=30, pady=20)

        # Botão Salvar
        btn_save = tb.Button(self.header, text="Save Configuration", bootstyle="success",  # Verde
                             command=self.save_yaml_dialog_multicombos)
        btn_save.pack(side="right", padx=30)
        ToolTip(
            btn_save, text="Gera e salva os arquivos YAML com a configuração atual.")

    def _build_footer_content(self):
        # SSH Status
        f_ssh = tb.Frame(self.status_bar, bootstyle="primary", padding=(15, 5))
        f_ssh.pack(side="right", fill="y")
        tb.Label(f_ssh, textvariable=self.ssh_status, font=("Consolas", 9, "bold"),
                 bootstyle="inverse-primary").pack()

        # Separador vertical
        tb.Label(self.status_bar, text="|",
                 bootstyle="inverse-primary").pack(side="right")

        # Tunnel Status
        f_tun = tb.Frame(self.status_bar, bootstyle="primary", padding=(15, 5))
        f_tun.pack(side="right", fill="y")
        tb.Label(f_tun, textvariable=self.tunnel_status, font=("Consolas", 9),
                 bootstyle="inverse-primary").pack()

        # Mensagem de Log (Esquerda)
        self.lbl_status_msg = tb.Label(self.status_bar, text="Ready.", font=("Segoe UI", 9),
                                       bootstyle="inverse-primary")
        self.lbl_status_msg.pack(side="left", padx=20)

    def _init_pages(self):
        """Inicializa as páginas e cria a estrutura de navegação."""
        
        # --- [ALTERAÇÃO AQUI] ---
        # Substituímos VictimTab por SingleEarthStationTab na lista
        pages = [
            ("general", "General Settings", GeneralTab, "⚙"),
            ("imt", "IMT Configuration", IMTTab, "📡"),
            ("victim", "Victim", VictimTab, ""),
            ("station", "Single Earth Station", SingleEarthStationTab, "🛰"),
            ("preview", "Visual Preview", PreviewTab, "👁"),
            ("runner", "Execution Runner", RunnerTab, "🚀"),
            ("results", "Data Analysis", ResultsTab, "📊"),
        ]

        for key, label, Cls, icon in pages:
            # 1. Cria Botão de Menu (Sidebar)
            btn = tb.Button(
                self.menu_frame,
                text=f"  {icon}   {label}",
                style="Nav.TButton",
                bootstyle="secondary-link",
                command=lambda k=key, l=label: self._switch_page(k, l)
            )
            btn.pack(fill="x", pady=2, padx=10)
            self.nav_buttons[key] = btn

            # 2. Container Visual (Onde os widgets da aba serão desenhados)
            container = tb.Frame(self.content_area)

            # 3. Instância da Lógica (Controlador da Aba)
            # Passamos 'container' como parent. A classe da aba desenha dentro dele.
            # E passamos 'self' (App) para que a aba acesse as variáveis de estado.
            instance = Cls(self, container)

            # 4. Registra referências
            self.frames[key] = container       # Para dar .pack() depois
            # Para lógica (self.tab_general...)
            setattr(self, f"tab_{key}", instance)

    def _switch_page(self, key, label_text=None):
        """Troca a página visível e SINCRONIZA dados."""

        # Sincroniza IMT Countries (necessário para a visualização 3D funcionar)
        if hasattr(self, 'tab_imt') and hasattr(self.tab_imt, 'txt_countries'):
            try:
                raw_txt = self.tab_imt.txt_countries.get("1.0", "end").strip()
                if raw_txt:
                    self.topo_countries.set(raw_txt)
            except Exception:
                pass

        # --- Troca Visual ---
        if label_text:
            self.lbl_page_title.config(text=label_text)
        elif key == "general":
            self.lbl_page_title.config(text="General Settings")

        # Esconde container atual
        if self.current_frame:
            self.current_frame.pack_forget()

        # Atualiza estilo dos botões (Highlight no ativo)
        for k, btn in self.nav_buttons.items():
            if k == key:
                btn.configure(bootstyle="primary")
            else:
                btn.configure(bootstyle="secondary-link")

        # Mostra container novo
        self.current_frame = self.frames[key]
        self.current_frame.pack(fill="both", expand=True)

        # --- Trigger de Refresh ---
        # Se for a aba Preview, força o redesenho do mapa
        if key == "preview":
            logic_instance = getattr(self, f"tab_{key}", None)
            if logic_instance:
                if hasattr(logic_instance, "refresh"):
                    logic_instance.refresh()
                elif hasattr(logic_instance, "update_plot"):
                    logic_instance.update_plot()

    def _show_welcome_toast(self):
        toast = ToastNotification(
            title="SHARC",
            message="System Ready.\nTheme: Cosmo Light",
            duration=3000,
            bootstyle="light",
            position=(40, 60, "ne")
        )
        toast.show_toast()

    def _show_success_toast(self, msg):
        toast = ToastNotification(
            title="Success",
            message=msg,
            duration=3000,
            bootstyle="success",
            position=(40, 60, "ne")
        )
        toast.show_toast()

    # --- Lógica de Negócio e Logs (Backend) ---

    def _safe_log(self, msg):
        self.line_q.put(("log", msg))

    def _safe_update_row(self, data):
        self.line_q.put(("row", data))

    def _drain_log_queue(self):
        try:
            for _ in range(50):
                item = self.line_q.get_nowait()
                msg_type, payload = item

                if msg_type == "log":
                    clean_msg = payload.strip()
                    if clean_msg:
                        self.lbl_status_msg.config(text=clean_msg[:120])

                    if hasattr(self.tab_runner, 'txt_log'):
                        w = self.tab_runner.txt_log
                        w.configure(state="normal")
                        w.insert("end", payload +
                                 ("\n" if not payload.endswith("\n") else ""))
                        w.see("end")
                        w.configure(state="disabled")

                elif msg_type == "row":
                    if hasattr(self.tab_runner, 'tree'):
                        tree = self.tab_runner.tree
                        iid = payload.get("iid")
                        if iid and tree.exists(iid):
                            cur = list(tree.item(iid, "values"))
                            if payload["status"] is not None:
                                cur[1] = payload["status"]
                            if payload["pct"] is not None:
                                cur[3] = payload["pct"]
                                try:
                                    pct_float = float(
                                        payload["pct"].strip('%'))
                                    self.sys_meter.configure(
                                        amountused=int(pct_float), subtext="Running")
                                except:
                                    pass

                            tree.item(iid, values=cur)
        except queue.Empty:
            pass
        except Exception:
            pass

        self.after(100, self._drain_log_queue)

    # --- YAML Generation ---

    def current_yaml_dict(self) -> dict:
        if hasattr(self, 'tab_imt') and hasattr(self.tab_imt, 'txt_countries'):
            try:
                txt = self.tab_imt.txt_countries.get("1.0", "end")
                self.topo_countries.set(txt)
            except:
                pass
        return build_yaml_structure(self)

    def _deep_format(self, obj, combo):
        if isinstance(obj, dict):
            return {k: self._deep_format(v, combo) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._deep_format(v, combo) for v in obj]
        if isinstance(obj, str):
            try:
                return obj.format(**combo)
            except:
                return obj
        return obj

    def save_yaml_to_yamldir(self):
        self._generate_and_save_yaml(self.var_yaml_dir.get())

    def save_yaml_dialog_multicombos(self):
        initdir = self.var_yaml_dir.get() or os.getcwd()
        path = filedialog.asksaveasfilename(
            title="Escolha um nome base",
            defaultextension=".yaml",
            initialdir=initdir,
            initialfile=(self.var_prefix.get() or "scenario") + ".yaml"
        )
        if path:
            outdir = os.path.dirname(path)
            count = self._generate_and_save_yaml(outdir)
            self.var_yaml_dir.set(outdir)

    def _generate_and_save_yaml(self, outdir):
        if not outdir:
            return 0
        os.makedirs(outdir, exist_ok=True)

        tree = self.tab_general.var_table
        names, lists = [], []
        for iid in tree.get_children():
            name, vals = tree.item(iid, "values")
            try:
                vlist = ast.literal_eval(vals)
                names.append(str(name))
                lists.append(list(vlist))
            except:
                messagebox.showwarning(
                    "Erro", f"Valores inválidos para variável {name}")
                return 0

        combos = [dict(zip(names, p))
                  for p in itertools.product(*lists)] if names else [{}]
        root = self.current_yaml_dict()
        base_prefix = root["general"]["output_dir_prefix"] or "scenario"

        count = 0
        for combo in combos:
            prefix = base_prefix
            try:
                prefix = prefix.format(**combo)
            except:
                pass

            root_fmt = self._deep_format(root, combo)
            text = build_yaml_text(root_fmt)
            fname = os.path.join(outdir, f"{prefix}.yaml")
            with open(fname, "w", encoding="utf-8") as f:
                f.write(text)
            count += 1

        self._show_success_toast(f"{count} scenarios generated in:\n{outdir}")
        return count


if __name__ == "__main__":
    app = App()
    app.mainloop()