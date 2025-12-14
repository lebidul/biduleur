# leNiceGui/app.py
# Application NiceGUI pour Le Bidul v2.0.0
# Compatible Desktop (PyInstaller) et Web

import os
import sys
import asyncio
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

from nicegui import ui, app, events

# Import du backend existant
sys.path.insert(0, str(Path(__file__).parent.parent))

from . import __version__


@dataclass
class AppState:
    """État centralisé de l'application."""
    # Fichiers
    input_file: str = ""
    output_pdf: str = ""
    output_html: str = ""
    output_agenda_html: str = ""
    output_svg_dir: str = ""
    stories_output_dir: str = ""

    # Images et ressources
    cover_image: str = ""
    logos_dir: str = ""
    ours_png: str = ""
    ours_svg: str = "misenpageur/assets/ours/ours.svg"
    logos_svg: str = "misenpageur/assets/logos.svg"

    # Options
    poster_title: str = ""
    generate_cover: bool = True
    generate_svg: bool = True
    generate_stories: bool = True
    split_pdf: bool = False
    debug_mode: bool = False

    # Mise en page
    font_size_mode: str = "auto"
    font_size_forced: float = 10.0
    page_margin_mm: float = 1.0
    date_separator_type: str = "ligne"
    date_spacing: float = 4.0

    # Options icônes
    chapeau_icon_enabled: bool = False
    free_icon_enabled: bool = False

    # Poster
    poster_design: int = 0
    font_size_safety_factor: float = 0.98
    background_alpha: float = 0.85

    # Stories
    stories_font_name: str = "Arial"
    stories_font_size: int = 45
    stories_font_color: str = "#000000"
    stories_bg_type: str = "color"
    stories_bg_color: str = "#FFFFFF"
    stories_bg_image: str = ""
    stories_alpha: float = 0.5

    # Cucaracha
    cucaracha_type: str = "none"
    cucaracha_value: str = ""
    cucaracha_font: str = "Arial"
    cucaracha_font_size: int = 8

    # Auteur couverture
    auteur_couv: str = ""
    auteur_couv_url: str = ""

    # Layouts
    logos_layout: str = "svg"
    logos_padding_mm: float = 1.0
    ours_layout: str = "svg"

    # Date box
    date_box_back_color: str = "#FFFFFF"

    # Abréviations
    abbreviations_enabled: dict = field(default_factory=dict)

    # Progression
    progress: float = 0.0
    status: str = "Prêt"
    is_running: bool = False


# État global de l'application
state = AppState()


def get_resource_path(relative_path: str) -> str:
    """Retourne le chemin absolu vers une ressource."""
    if getattr(sys, 'frozen', False):
        base_path = getattr(sys, '_MEIPASS')
    else:
        base_path = str(Path(__file__).parent.parent)
    return os.path.join(base_path, relative_path)


def derive_output_paths(input_file: str) -> dict:
    """Calcule les chemins de sortie à partir du fichier d'entrée."""
    if not input_file:
        return {}
    input_path = Path(input_file)
    base = input_path.stem
    folder = input_path.parent
    return {
        "html": str(folder / f"{base}.html"),
        "agenda_html": str(folder / f"{base}.agenda.html"),
        "pdf": str(folder / f"{base}.pdf"),
        "svg_dir": str(folder / "svgs"),
        "stories_dir": str(folder / "stories"),
    }


async def handle_file_upload(e: events.UploadEventArguments):
    """Gère l'upload d'un fichier Excel/CSV."""
    import tempfile

    # NiceGUI: e.file est un objet FileUpload avec attributs name, content_type
    # et méthodes async read(), save(), text(), etc.
    upload_file = e.file
    filename = upload_file.name

    # Sauvegarder dans un dossier temporaire
    temp_dir = Path(tempfile.gettempdir()) / "bidul_uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    file_path = temp_dir / filename

    # save() est async
    await upload_file.save(str(file_path))

    state.input_file = str(file_path)

    # Calculer les chemins de sortie
    paths = derive_output_paths(str(file_path))
    state.output_html = paths.get("html", "")
    state.output_agenda_html = paths.get("agenda_html", "")
    state.output_pdf = paths.get("pdf", "")
    state.output_svg_dir = paths.get("svg_dir", "")
    state.stories_output_dir = paths.get("stories_dir", "")

    ui.notify(f"Fichier chargé : {filename}", type="positive")


def handle_local_file(path: str):
    """Gère un fichier local (mode desktop)."""
    if not path or not os.path.exists(path):
        ui.notify("Fichier introuvable", type="negative")
        return

    state.input_file = path
    paths = derive_output_paths(path)
    state.output_html = paths.get("html", "")
    state.output_agenda_html = paths.get("agenda_html", "")
    state.output_pdf = paths.get("pdf", "")
    state.output_svg_dir = paths.get("svg_dir", "")
    state.stories_output_dir = paths.get("stories_dir", "")

    ui.notify(f"Fichier sélectionné : {os.path.basename(path)}", type="positive")


async def run_generation():
    """Lance la génération du Bidul."""
    if not state.input_file:
        ui.notify("Veuillez sélectionner un fichier d'entrée", type="warning")
        return

    if state.is_running:
        ui.notify("Une génération est déjà en cours", type="warning")
        return

    state.is_running = True
    state.progress = 0.0
    state.status = "Démarrage..."

    try:
        # Import du pipeline
        from leTruc._helpers import run_pipeline
        import queue
        import threading

        status_queue = queue.Queue()
        stop_event = threading.Event()

        # Préparer les abréviations activées
        abbreviations_enabled = {k: v for k, v in state.abbreviations_enabled.items() if v}

        # Lancer le pipeline dans un thread séparé
        thread = threading.Thread(
            target=run_pipeline,
            kwargs={
                "status_queue": status_queue,
                "debug_mode": state.debug_mode,
                "input_file": state.input_file,
                "generate_cover": state.generate_cover,
                "cover_image": state.cover_image,
                "ours_background_png": state.ours_png,
                "ours_layout": state.ours_layout,
                "ours_svg_file": state.ours_svg,
                "logos_dir": state.logos_dir,
                "logos_layout": state.logos_layout,
                "logos_padding_mm": state.logos_padding_mm,
                "logos_svg_file": state.logos_svg,
                "date_box_back_color": state.date_box_back_color,
                "out_html": state.output_html,
                "out_agenda_html": state.output_agenda_html,
                "out_pdf": state.output_pdf,
                "auteur_couv": state.auteur_couv,
                "auteur_couv_url": state.auteur_couv_url,
                "page_margin_mm": state.page_margin_mm,
                "generate_svg": state.generate_svg,
                "out_svg_dir": state.output_svg_dir,
                "date_separator_type": state.date_separator_type,
                "date_spacing": state.date_spacing,
                "poster_design": state.poster_design,
                "font_size_safety_factor": state.font_size_safety_factor,
                "background_alpha": state.background_alpha,
                "poster_title": state.poster_title,
                "cucaracha_type": state.cucaracha_type,
                "cucaracha_value": state.cucaracha_value,
                "cucaracha_text_font": state.cucaracha_font,
                "cucaracha_font_size": state.cucaracha_font_size,
                "chapeau_icon_enabled": state.chapeau_icon_enabled,
                "free_icon_enabled": state.free_icon_enabled,
                "generate_stories": state.generate_stories,
                "stories_output_dir": state.stories_output_dir,
                "font_size_mode": state.font_size_mode,
                "font_size_forced": state.font_size_forced,
                "stories_font_name": state.stories_font_name,
                "stories_font_size": state.stories_font_size,
                "stories_font_color": state.stories_font_color,
                "stories_bg_type": state.stories_bg_type,
                "stories_bg_color": state.stories_bg_color,
                "stories_bg_image": state.stories_bg_image,
                "stories_alpha": state.stories_alpha,
                "abbreviations_enabled": abbreviations_enabled,
                "stop_event": stop_event,
                "split_pdf": state.split_pdf,
            }
        )
        thread.start()

        # Surveiller la progression
        total_steps = 1
        while thread.is_alive() or not status_queue.empty():
            try:
                msg = status_queue.get_nowait()
                msg_type = msg[0]

                if msg_type == 'start':
                    total_steps = msg[1]
                elif msg_type == 'status':
                    state.status = msg[1]
                    if msg[2] is not None:
                        state.progress = msg[2] / total_steps
                elif msg_type == 'final':
                    success = msg[1]
                    message = msg[2]
                    if success:
                        state.status = "Terminé !"
                        state.progress = 1.0
                        ui.notify("Génération terminée avec succès !", type="positive")
                        # Afficher le résumé
                        with ui.dialog() as dialog, ui.card():
                            ui.label("Résumé").classes("text-xl font-bold")
                            ui.label(message).classes("whitespace-pre-wrap")
                            ui.button("Fermer", on_click=dialog.close)
                        dialog.open()
                    else:
                        state.status = "Erreur"
                        ui.notify(f"Erreur : {message[:100]}...", type="negative")
            except queue.Empty:
                pass

            await asyncio.sleep(0.1)

        thread.join()

    except Exception as e:
        state.status = f"Erreur : {e}"
        ui.notify(f"Erreur : {e}", type="negative")
    finally:
        state.is_running = False


def create_header():
    """Crée l'en-tête de l'application."""
    with ui.header().classes("bg-primary"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label(f"Le Bidul v{__version__}").classes("text-xl font-bold text-white")

            with ui.row().classes("gap-2"):
                ui.button(icon="help", on_click=lambda: show_help_dialog()).props("flat round color=white")
                ui.button(icon="info", on_click=lambda: show_about_dialog()).props("flat round color=white")


def create_file_section():
    """Crée la section de sélection de fichier."""
    with ui.card().classes("w-full"):
        ui.label("Fichier d'entrée").classes("text-lg font-semibold")
        ui.separator()

        # Zone de drop / upload
        with ui.column().classes("w-full items-center p-4 border-2 border-dashed rounded-lg"):
            ui.icon("upload_file", size="xl").classes("text-gray-400")
            ui.label("Glissez-déposez votre fichier Excel/CSV").classes("text-gray-500")
            ui.label("ou").classes("text-gray-400 text-sm")

            ui.upload(
                label="Parcourir...",
                on_upload=handle_file_upload,
                auto_upload=True,
            ).props("accept=.xlsx,.xls,.csv").classes("w-64")

        # Affichage du fichier sélectionné
        with ui.row().classes("w-full items-center gap-2 mt-2"):
            ui.icon("description").classes("text-primary")
            ui.label().bind_text_from(state, 'input_file',
                backward=lambda x: os.path.basename(x) if x else "Aucun fichier sélectionné")


def create_parameters_section():
    """Crée la section des paramètres."""
    with ui.card().classes("w-full"):
        ui.label("Paramètres").classes("text-lg font-semibold")
        ui.separator()

        with ui.column().classes("w-full gap-4"):
            # Titre du poster
            ui.input("Titre du poster", placeholder="Ex: Janvier 2025").bind_value(state, 'poster_title').classes("w-full")

            # Taille de police
            with ui.row().classes("w-full items-center gap-4"):
                ui.label("Taille de police")
                ui.radio(["auto", "forcée"], value="auto").bind_value(state, 'font_size_mode',
                    forward=lambda x: "auto" if x == "auto" else "forced",
                    backward=lambda x: "auto" if x == "auto" else "forcée")
                ui.number("Taille (pt)", min=6, max=20, step=0.5, format="%.1f").bind_value(state, 'font_size_forced').bind_visibility_from(state, 'font_size_mode', lambda x: x != "auto")

            # Options checkboxes
            with ui.row().classes("w-full flex-wrap gap-4"):
                ui.checkbox("Abréviations").bind_value(state, 'abbreviations_enabled',
                    forward=lambda x: bool(x), backward=lambda x: x)
                ui.checkbox("Icône chapeau").bind_value(state, 'chapeau_icon_enabled')
                ui.checkbox("Icône gratuit").bind_value(state, 'free_icon_enabled')


def create_output_section():
    """Crée la section des sorties."""
    with ui.card().classes("w-full"):
        ui.label("Sorties").classes("text-lg font-semibold")
        ui.separator()

        with ui.column().classes("w-full gap-4"):
            # Chemin PDF
            with ui.row().classes("w-full items-center gap-2"):
                ui.icon("picture_as_pdf").classes("text-red-500")
                ui.input("PDF").bind_value(state, 'output_pdf').classes("flex-grow")

            # Options
            with ui.row().classes("w-full flex-wrap gap-4"):
                ui.checkbox("Générer SVG éditables").bind_value(state, 'generate_svg')
                ui.checkbox("Générer Stories Instagram").bind_value(state, 'generate_stories')
                ui.checkbox("PDF par page (en plus du complet)").bind_value(state, 'split_pdf')
                ui.checkbox("Mode Debug").bind_value(state, 'debug_mode')


def create_progress_section():
    """Crée la section de progression."""
    with ui.card().classes("w-full"):
        ui.label("Progression").classes("text-lg font-semibold")
        ui.separator()

        with ui.column().classes("w-full gap-2"):
            ui.linear_progress(show_value=False).bind_value_from(state, 'progress').classes("w-full")
            ui.label().bind_text_from(state, 'status')


def create_action_buttons():
    """Crée les boutons d'action."""
    with ui.row().classes("w-full justify-center gap-4"):
        ui.button(
            "Créer le Bidul",
            icon="rocket_launch",
            on_click=run_generation
        ).props("size=lg color=primary").bind_enabled_from(state, 'is_running', backward=lambda x: not x)

        ui.button(
            "Arrêter",
            icon="stop",
            on_click=lambda: None  # TODO: Implémenter l'arrêt
        ).props("size=lg color=negative").bind_visibility_from(state, 'is_running')


def show_about_dialog():
    """Affiche la boîte de dialogue À propos."""
    with ui.dialog() as dialog, ui.card().classes("w-96"):
        ui.label("À propos").classes("text-xl font-bold")
        ui.separator()
        ui.label(f"Le Bidul v{__version__}")
        ui.label("Transforme vos données événementielles en PDF professionnels")
        ui.separator()
        ui.label("Développé pour Le Bidul - Agenda culturel de la Sarthe")
        ui.link("Voir sur GitHub", "https://github.com/lebidul/bidul.biduleur", new_tab=True)
        ui.button("Fermer", on_click=dialog.close)
    dialog.open()


def show_help_dialog():
    """Affiche l'aide."""
    with ui.dialog() as dialog, ui.card().classes("w-[600px] max-h-[80vh]"):
        ui.label("Guide d'utilisation").classes("text-xl font-bold")
        ui.separator()

        with ui.scroll_area().classes("h-96"):
            ui.markdown("""
## Comment utiliser Le Bidul

### 1. Sélectionner un fichier
- Glissez-déposez votre fichier Excel (.xlsx) ou CSV
- Ou cliquez sur "Parcourir" pour le sélectionner

### 2. Configurer les paramètres
- **Titre du poster** : Apparaît en haut de la page 3
- **Taille de police** : Auto ajuste automatiquement, ou forcez une taille
- **Abréviations** : Raccourcit les mots courants (Théâtre → Th.)

### 3. Choisir les sorties
- **PDF** : Document principal (3 pages)
- **SVG** : Versions éditables dans Illustrator/Inkscape
- **Stories** : Images pour Instagram Stories

### 4. Lancer la génération
Cliquez sur "Créer le Bidul" et attendez la fin du traitement.
            """)

        ui.button("Fermer", on_click=dialog.close)
    dialog.open()


def create_interface():
    """Crée l'interface principale de l'application."""
    create_header()

    with ui.column().classes("w-full max-w-4xl mx-auto p-4 gap-4"):
        create_file_section()

        with ui.expansion("Paramètres avancés", icon="settings").classes("w-full"):
            create_parameters_section()

        create_output_section()
        create_progress_section()
        create_action_buttons()


def main(native: bool = False):
    """Point d'entrée principal."""
    # Configuration du thème
    ui.colors(primary='#1976D2', secondary='#26A69A', accent='#9C27B0')

    create_interface()

    if native:
        # Mode Desktop
        ui.run(
            native=True,
            window_size=(1000, 800),
            title=f"Le Bidul v{__version__}",
            reload=False,
        )
    else:
        # Mode Web
        ui.run(
            title=f"Le Bidul v{__version__}",
            reload=False,
        )


if __name__ in {"__main__", "__mp_main__"}:
    # Détection automatique du mode
    native_mode = "--native" in sys.argv or app.native.main_window is not None
    main(native=native_mode)
