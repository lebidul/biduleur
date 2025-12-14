# leTruc/_helpers.py
# v1.4.2 : Ajout système d'abréviations
import os
import sys
from pathlib import Path
from tkinter import messagebox, filedialog
import subprocess
import importlib.resources as res
import queue
from datetime import datetime
import json
from dataclasses import asdict
import logging

from biduleur.csv_utils import parse_bidul
from biduleur.format_utils import output_html_file
from misenpageur.misenpageur.html_utils import extract_paragraphs_from_html
from misenpageur.misenpageur.image_builder import generate_story_images
from misenpageur.misenpageur.draw_logic import read_text
from misenpageur import logger


# Pour garder app.py propre, nous avons déplacé les fonctions "utilitaires" qui ne sont pas des méthodes de la classe dans un fichier séparé.

# Cette fonction est utilisée par `run_pipeline` et `_load_cfg_defaults`
def get_resource_path(relative_path):
    """
    Retourne le chemin absolu vers une ressource, fonctionne en mode dev et packagé.
    """
    if getattr(sys, 'frozen', False):
        # En mode packagé, la base est le dossier où tout est décompressé.
        base_path = getattr(sys, '_MEIPASS')
    else:
        # En mode développement, on remonte d'un niveau depuis le dossier `leTruc`
        # pour trouver la vraie racine du projet.
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    return os.path.join(base_path, relative_path)


def _ensure_parent_dir(path: str):
    if path: Path(path).parent.mkdir(parents=True, exist_ok=True)


# Cette fonction est utilisée par `_load_cfg_defaults`
def _project_defaults() -> dict:
    """
    Définit les chemins par défaut pour les fichiers de config et layout.
    """
    # get_resource_path nous donne maintenant la bonne racine dans les deux modes.
    repo_root = get_resource_path('.')

    cfg = os.path.join(repo_root, "misenpageur", "config.yml")
    lay = os.path.join(repo_root, "misenpageur", "layout.yml")

    return {"root": repo_root, "config": cfg, "layout": lay}


# Cette fonction est utilisée par le constructeur de l'Application
def _load_cfg_defaults() -> dict:
    """
    Charge les valeurs par défaut depuis le fichier config.yml.
    En cas d'échec, retourne un dictionnaire de valeurs sûres codées en dur.
    """
    # On définit d'abord les valeurs de secours au cas où tout échouerait.
    out = {
        "cover": "",
        "ours_background_png": "",
        "logos_dir": "",
        "auteur_couv": "",
        "auteur_couv_url": "",
        "skip_cover": False,
        "page_margin_mm": 1.0,
        "date_separator_type": "ligne",
        "date_spacing": "4",
        "poster_design": 0,
        "font_size_safety_factor": 0.98,
        "background_alpha": 0.85,
        "poster_title": "",
        "cucaracha_type": "none",
        "cucaracha_value": "",
        "cucaracha_text_font": "Arial",
        "abbreviations": {},  # v1.4.2 : Abréviations
        "debug_mode": False
    }

    # On essaie de lire les vraies valeurs par défaut depuis le config.yml
    try:
        # On tente l'import de Config uniquement ici.
        from misenpageur.misenpageur.config import Config

        # On récupère les chemins par défaut (qui sont compatibles PyInstaller)
        defaults = _project_defaults()
        cfg_path = defaults.get("config")

        if not cfg_path or not os.path.exists(cfg_path):
            print(f"[WARN] Fichier de configuration par défaut introuvable : {cfg_path}")
            return out  # Retourne les valeurs de secours

        cfg = Config.from_yaml(cfg_path)

        # ==================== CORRECTION POUR LES CHEMINS RELATIFS ====================
        # On récupère le chemin racine des ressources (le dossier _MEIPASS dans le build)
        resource_root = get_resource_path('.')

        def make_abs_path(rel_path):
            """Helper pour transformer un chemin relatif en chemin absolu."""
            if not rel_path or os.path.isabs(rel_path):
                return rel_path
            # On joint le chemin relatif à la racine des ressources
            return os.path.join(resource_root, rel_path)

        # Si la lecture réussit, on met à jour notre dictionnaire 'out'
        out.update({
            # On applique la conversion sur tous les chemins
            "cover": make_abs_path(cfg.cover_image or ""),
            "logos_dir": make_abs_path(cfg.logos_dir or ""),

            "auteur_couv": getattr(cfg, "auteur_couv", "") or "",
            "auteur_couv_url": getattr(cfg, "auteur_couv_url", "") or "",
            "skip_cover": getattr(cfg, "skip_cover", False),
            "date_spacing": str(cfg.date_spaceBefore),
        })
        if isinstance(cfg.section_1, dict):
            out["ours_background_png"] = make_abs_path(cfg.section_1.get("ours_background_png", ""))
        if isinstance(cfg.pdf_layout, dict):
            out["page_margin_mm"] = cfg.pdf_layout.get("page_margin_mm", 1.0)
        if cfg.date_line.get("enabled", True):
            out["date_separator_type"] = "ligne"
        elif cfg.date_box.get("enabled", False):
            out["date_separator_type"] = "box"
        else:
            out["date_separator_type"] = "aucun"
        if isinstance(cfg.poster, dict):
            out.update({
                "poster_design": cfg.poster.get("design", 0),
                "font_size_safety_factor": cfg.poster.get("font_size_safety_factor", 0.98),
                "background_alpha": cfg.poster.get("background_image_alpha", 0.85),
                "poster_title": cfg.poster.get("title", "")
            })
        if isinstance(cfg.cucaracha_box, dict):
            out.update({
                "cucaracha_type": cfg.cucaracha_box.get("content_type", "none"),
                "cucaracha_value": cfg.cucaracha_box.get("content_value", ""),
                "cucaracha_text_font": cfg.cucaracha_box.get("text_font_name", "Arial")
            })
        out["font_size_mode"] = getattr(cfg, "font_size_mode", "auto")
        out["font_size_forced"] = getattr(cfg, "font_size_forced", 10.0)
        out["debug_mode"] = getattr(cfg, "debug_mode", False)

        if isinstance(cfg.stories, dict):
            out["stories_enabled"] = cfg.stories.get("enabled", True)
            out["stories_font_name"] = cfg.stories.get("agenda_font_name", "Arial")
            out["stories_font_size"] = cfg.stories.get("agenda_font_size", 45)
            out["stories_font_color"] = cfg.stories.get("text_color", "#000000")
            out["stories_bg_color"] = cfg.stories.get("background_color", "#FFFFFF")

        # v1.4.2 : Les abréviations viennent uniquement de abbreviations.yml
        # On n'utilise plus cfg.abbreviations

    except Exception as e:
        # Si l'import ou la lecture du fichier échoue, on affiche un avertissement
        # mais l'application peut continuer avec les valeurs par défaut.
        print(f"[WARN] Erreur lors de la lecture des défauts depuis config.yml : {e}")
        # On ne fait rien d'autre, la fonction retournera le 'out' initial.

    return out


def save_embedded_template(filename, title):
    ext = os.path.splitext(filename)[1].lower()
    ftypes = [("Excel", "*.xlsx")] if ext == '.xlsx' else [("CSV", "*.csv")]
    target = filedialog.asksaveasfilename(title=title, defaultextension=ext, filetypes=ftypes, initialfile=filename)
    if not target: return
    try:
        data = res.files('biduleur.templates').joinpath(filename).read_bytes()
        with open(target, "wb") as f:
            f.write(data)
        messagebox.showinfo("Modèle enregistré", f"Fichier enregistré ici :\n{target}")
    except Exception as e:
        messagebox.showerror("Erreur", f"Impossible d'enregistrer le modèle : {e}")


# Cette fonction est utilisée par le thread
def run_pipeline(
        status_queue: queue.Queue,
        debug_mode: bool,
        input_file: str, generate_cover: bool, cover_image: str, ours_background_png: str,
        ours_layout: str, ours_svg_file: str, logos_dir: str,
        logos_layout: str, logos_padding_mm: float, logos_svg_file: str, date_box_back_color: str,
        out_html: str, out_agenda_html: str, out_pdf: str, auteur_couv: str, auteur_couv_url: str,
        page_margin_mm: float, generate_svg: bool, out_svg_dir: str, date_separator_type: str,
        date_spacing: float, poster_design: int, font_size_safety_factor: float,
        background_alpha: float, poster_title: str, cucaracha_type: str,
        cucaracha_value: str, cucaracha_text_font: str, cucaracha_font_size: int,
        chapeau_icon_enabled: bool,
        free_icon_enabled: bool,
        generate_stories: bool, stories_output_dir: str,
        font_size_mode: str, font_size_forced: float,
        stories_font_name: str, stories_font_size: int, stories_font_color: str,
        stories_bg_type: str, stories_bg_color: str, stories_bg_image: str,
        stories_alpha: float,
        abbreviations_enabled: dict = None  # v1.4.2 : Abréviations activées
) -> tuple[bool, str]:
    debug_dir = None
    if debug_mode:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        pdf_path = Path(out_pdf)
        debug_dir = pdf_path.parent / f"debug_run_{timestamp}"
        logger.setup_logger(str(debug_dir))

    # On importe le logger configuré
    log = logging.getLogger(__name__)

    try:
        from misenpageur.misenpageur.config import Config
        from misenpageur.misenpageur.layout import Layout
        from misenpageur.misenpageur.pdfbuild import build_pdf
        from misenpageur.misenpageur.svgbuild import build_svg
        from misenpageur.misenpageur.layout_builder import build_layout_with_margins
    except Exception as e:
        log.error(f"Erreur critique d'import: {e}", exc_info=True)
        import traceback
        status_queue.put(('final', False, f"Erreur critique: ...\n{e}\n\n{traceback.format_exc()}"))
        return

    final_layout_path = None
    report = {}
    abbreviation_stats = {}  # v1.4.2 : Stats des remplacements

    try:
        status_queue.put(('status', "Préparation...", 0, None))

        # 1. Calculer le nombre total d'étapes à l'avance
        total_steps = 3  # 3 étapes de base : analyse, HTML, PDF/fin
        if generate_svg and out_svg_dir:
            total_steps += 1
        if generate_stories:
            total_steps += 1

        # 2. Envoyer un message d'initialisation avec le total
        status_queue.put(('start', total_steps, None))
        current_step = 0

        for p in (out_html, out_agenda_html, out_pdf, out_svg_dir):
            if p: _ensure_parent_dir(p)

        current_step += 1
        status_queue.put(('status', f"Étape {current_step}/{total_steps} : Analyse du fichier...", current_step, None))

        try:
            html_body_bidul, html_body_agenda, number_of_lines = parse_bidul(input_file)
        except ValueError as e:
            # Erreur de validation (colonnes manquantes ou fichier corrompu)
            status_queue.put(('final', False, str(e)))
            return

        current_step += 1
        status_queue.put(('status', f"Étape {current_step}/{total_steps} : Génération des HTML...", current_step, None))
        output_html_file(html_body_bidul, original_file_name=input_file, output_filename=out_html)
        output_html_file(html_body_agenda, original_file_name=input_file, output_filename=out_agenda_html)

        html_text = read_text(out_html)
        paras = extract_paragraphs_from_html(html_text)

        # ==================== v1.4.2 : APPLICATION DES ABRÉVIATIONS ====================
        if abbreviations_enabled:
            try:
                from misenpageur.misenpageur.abbreviations import (
                    Abbreviation, apply_abbreviations_to_paragraphs, get_default_abbreviations
                )
                import html

                # Charger les abréviations depuis abbreviations.yml
                all_abbreviations = get_default_abbreviations()

                # Construire la liste des abréviations activées
                enabled_abbrevs = []
                for key, is_enabled in abbreviations_enabled.items():
                    if is_enabled and key in all_abbreviations:
                        data = all_abbreviations[key]
                        enabled_abbrevs.append(Abbreviation(
                            key=key,
                            original=data["original"],
                            replacement=data["replacement"],
                            description=data["description"],
                            enabled=True
                        ))

                if enabled_abbrevs:
                    log.info(f"Application de {len(enabled_abbrevs)} abréviation(s)...")

                    # IMPORTANT : Décoder les entités HTML AVANT le remplacement
                    # "Th&eacute;&acirc;tre" → "Théâtre"
                    paras_decoded = [html.unescape(p) for p in paras]
                    log.debug(f"Exemple avant décodage: {paras[0][:100] if paras else 'N/A'}")
                    log.debug(f"Exemple après décodage: {paras_decoded[0][:100] if paras_decoded else 'N/A'}")

                    # Charger les expressions nobr à protéger
                    nobr_expressions = []
                    defaults = _project_defaults()
                    nobr_file = os.path.join(defaults["root"], "misenpageur", "assets", "textes", "nobr.txt")
                    if os.path.exists(nobr_file):
                        try:
                            with open(nobr_file, 'r', encoding='utf-8') as f:
                                nobr_expressions = [line.strip() for line in f if line.strip()]
                            log.info(f"Chargé {len(nobr_expressions)} expression(s) nobr à protéger")
                        except Exception as e:
                            log.warning(f"Erreur lors du chargement de nobr.txt: {e}")

                    # Appliquer les abréviations sur les paragraphes décodés (en protégeant les nobr)
                    paras, abbreviation_stats = apply_abbreviations_to_paragraphs(
                        paras_decoded,
                        enabled_abbrevs,
                        nobr_expressions
                    )
                    total_replacements = sum(abbreviation_stats.values())
                    if total_replacements > 0:
                        log.info(f"Total: {total_replacements} remplacement(s) effectué(s)")
                    else:
                        log.warning("Aucun remplacement effectué ! Vérifiez les logs de debug.")

            except ImportError as e:
                log.warning(f"Module d'abréviations non disponible: {e}")
            except Exception as e:
                log.warning(f"Erreur lors de l'application des abréviations: {e}", exc_info=True)
        # ==================== FIN ABRÉVIATIONS ====================

        defaults = _project_defaults()
        project_root, cfg_path, lay_path = defaults["root"], defaults["config"], defaults["layout"]
        cfg = Config.from_yaml(cfg_path)

        cfg.project_root = project_root
        cfg.input_file = input_file  # Fichier d'entrée Excel/CSV
        cfg.input_html = out_html
        cfg.skip_cover = not generate_cover
        if out_pdf: cfg.output_pdf = out_pdf
        cfg.generate_svg = generate_svg  # Générer des SVG éditables
        cfg.output_svg_dir = out_svg_dir  # Dossier de sortie SVG
        cfg.stories_output_dir = stories_output_dir  # Dossier de sortie stories
        if (cover_image or "").strip(): cfg.cover_image = cover_image.strip()
        if (ours_background_png or "").strip(): cfg.section_1['ours_background_png'] = ours_background_png.strip()
        if (logos_dir or "").strip(): cfg.logos_dir = logos_dir.strip()
        if (auteur_couv or "").strip(): cfg.auteur_couv = auteur_couv.strip()
        if (auteur_couv_url or "").strip(): cfg.auteur_couv_url = auteur_couv_url.strip()
        cfg.pdf_layout['page_margin_mm'] = page_margin_mm
        cfg.font_size_mode = font_size_mode
        cfg.font_size_forced = font_size_forced
        cfg.logos_layout = logos_layout
        cfg.logos_padding_mm = logos_padding_mm
        cfg.logos_svg_file = logos_svg_file
        cfg.ours_layout = ours_layout
        cfg.ours_svg_file = ours_svg_file
        cfg.date_line['enabled'] = (date_separator_type == "ligne")
        cfg.date_box['enabled'] = (date_separator_type == "box")
        if cfg.date_box['enabled']:
            cfg.date_box['back_color'] = date_box_back_color
        cfg.date_spaceBefore = date_spacing
        cfg.date_spaceAfter = date_spacing
        cfg.poster['design'] = poster_design
        cfg.poster['font_size_safety_factor'] = font_size_safety_factor
        cfg.poster['background_image_alpha'] = background_alpha
        cfg.poster['title'] = poster_title
        cfg.cucaracha_box['content_type'] = cucaracha_type
        cfg.cucaracha_box['content_value'] = cucaracha_value
        cfg.cucaracha_box['text_font_name'] = cucaracha_text_font
        cfg.cucaracha_box['text_font_size'] = cucaracha_font_size
        cfg.chapeau_icon_enabled = chapeau_icon_enabled
        cfg.free_icon_enabled = free_icon_enabled
        cfg.stories['enabled'] = generate_stories
        if stories_output_dir:
            cfg.stories['output_dir'] = stories_output_dir
        cfg.stories['agenda_font_name'] = stories_font_name
        cfg.stories['agenda_font_size'] = stories_font_size
        cfg.stories['text_color'] = stories_font_color
        cfg.stories['background_color'] = stories_bg_color
        cfg.stories['background_image_alpha'] = stories_alpha
        cfg.stories['background_type'] = stories_bg_type
        cfg.stories['background_image'] = stories_bg_image

        final_layout_path = build_layout_with_margins(lay_path, cfg)
        lay = Layout.from_yaml(final_layout_path)

        if out_pdf:
            current_step += 1
            status_queue.put(('status', f"Étape {current_step}/{total_steps} : Création du PDF...", current_step, None))
            report = build_pdf(project_root, cfg, lay, out_pdf, cfg_path, paras)
        if generate_svg and out_svg_dir:
            if not report:
                report = build_pdf(project_root, cfg, lay, os.devnull, cfg_path, paras)
            current_step += 1
            status_queue.put(
                ('status', f"Étape {current_step}/{total_steps} : Conversion en SVG...", current_step, None))
            build_svg(project_root, cfg, lay, out_svg_dir, cfg_path, paras)
        if generate_stories:
            current_step += 1
            # Message "en cours"
            status_queue.put(
                ('status', f"Étape {current_step}/{total_steps} : Création des Stories...", current_step, None))
            num_stories_created = generate_story_images(project_root, cfg, paras)

        status_queue.put(('status', "Finalisation...", None))

        summary_lines = [
            f"Fichier d'entrée : {os.path.basename(input_file)}", "-" * 40, "Fichiers de sortie créés :"
        ]
        if out_html: summary_lines.append(f"  - HTML: {out_html}")
        if out_agenda_html: summary_lines.append(f"  - HTML (Agenda): {out_agenda_html}")
        if out_pdf: summary_lines.append(f"  - PDF: {out_pdf}")
        if generate_svg and out_svg_dir: summary_lines.append(f"  - SVG: {out_svg_dir}")
        if generate_stories and stories_output_dir: summary_lines.append(f"  - Stories: {stories_output_dir}")

        summary_lines.append("\n" + "-" * 40)
        summary_lines.append(f"Nombre d'événements traités : {number_of_lines}")

        # v1.4.2 : Afficher les stats d'abréviations
        if abbreviation_stats:
            total_abbrev = sum(abbreviation_stats.values())
            if total_abbrev > 0:
                summary_lines.append(f"Abréviations appliquées : {total_abbrev}")

        fs_main = report.get("font_size_main")
        if fs_main: summary_lines.append(f"Taille de police (pages 1-2): {fs_main:.2f} pt")
        fs_poster = report.get("font_size_poster_final")
        if fs_poster:
            fs_poster_opt = report.get("font_size_poster_optimal", 0)
            summary_lines.append(
                f"Taille de police (poster)    : {fs_poster:.2f} pt (optimale: {fs_poster_opt:.2f} pt)")
        if generate_stories and stories_output_dir:
            summary_lines.append(f"Nombre de fichiers images créés pour la Story: {num_stories_created}")

        if debug_mode and debug_dir:
            # 1. Sauvegarder la configuration utilisée
            log.info("Sauvegarde de la configuration utilisée dans config.json...")

            # Helper pour convertir les objets non sérialisables comme Path
            def json_converter(o):
                if isinstance(o, Path):
                    return str(o)
                # Lève une erreur pour les autres types non gérés
                raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")

            # On utilise un bloc try/except au cas où la sérialisation échouerait
            try:
                config_path = debug_dir / "config.json"
                config_data = asdict(cfg)  # Convertit le dataclass en dictionnaire
                # Ajouter le fichier input et les abréviations pour permettre l'import complet
                config_data["_input_file"] = input_file
                config_data["_abbreviations_enabled"] = abbreviations_enabled or {}
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, indent=2, default=json_converter, ensure_ascii=False)
            except Exception as e:
                log.error(f"Impossible de sauvegarder le fichier config.json : {e}")

            # v1.4.2 : Sauvegarder les stats d'abréviations
            if abbreviations_enabled or abbreviation_stats:
                try:
                    abbrev_path = debug_dir / "abbreviations.json"
                    abbrev_data = {
                        "enabled": abbreviations_enabled or {},
                        "stats": abbreviation_stats
                    }
                    with open(abbrev_path, 'w', encoding='utf-8') as f:
                        json.dump(abbrev_data, f, indent=2, ensure_ascii=False)
                    log.info("Sauvegarde des abréviations dans abbreviations.json...")
                except Exception as e:
                    log.error(f"Impossible de sauvegarder abbreviations.json : {e}")

            # 2. Sauvegarder le résumé de l'exécution
            log.info("Sauvegarde du résumé dans summary.info...")
            try:
                summary_path = debug_dir / "summary.info"
                with open(summary_path, 'w', encoding='utf-8') as f:
                    f.write("\n".join(summary_lines))
            except Exception as e:
                log.error(f"Impossible de sauvegarder le fichier summary.info : {e}")

        status_queue.put(('final', True, "\n".join(summary_lines)))



    except PermissionError as e:
        # On intercepte SPÉCIFIQUEMENT l'erreur de permission
        # On extrait le nom du fichier qui cause le problème
        log.error(f"Erreur de permission: {e.filename}", exc_info=True)
        locked_file = e.filename or "un fichier de sortie"
        user_message = (
            f"Impossible d'écrire le fichier suivant :\n\n"
            f"{os.path.basename(locked_file)}\n\n"
            f"Veuillez vous assurer que le fichier n'est pas ouvert dans un autre programme (comme Adobe Reader) et réessayez."
        )
        status_queue.put(('final', False, user_message))

    except Exception as e:
        log.error("Une erreur inattendue est survenue.", exc_info=True)
        import traceback
        status_queue.put(('final', False, f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}"))

    finally:
        if debug_mode:
            logger.shutdown_logger()
        if final_layout_path and os.path.exists(final_layout_path) and Path(final_layout_path).name.endswith(".yml"):
            try:
                os.remove(final_layout_path)
            except OSError:
                pass


# Cette fonction est utilisée à la fin du run
def open_file(filepath):
    """Ouvre un fichier avec l'application par défaut du système."""
    if not filepath or not os.path.exists(filepath):
        print(f"[WARN] Impossible d'ouvrir le fichier, il n'existe pas : {filepath}")
        return
    try:
        if sys.platform == "win32":
            os.startfile(filepath)
        elif sys.platform == "darwin":  # macOS
            subprocess.run(["open", filepath])
        else:  # Linux
            subprocess.run(["xdg-open", filepath])
    except Exception as e:
        messagebox.showwarning("Ouverture impossible", f"Impossible d'ouvrir le fichier automatiquement:\n{e}")


def _default_paths_from_input(input_file: str) -> dict:
    input_path = Path(input_file)
    base = input_path.stem
    folder = input_path.parent
    return {
        "html": str(folder / f"{base}.html"),
        "agenda_html": str(folder / f"{base}.agenda.html"),
        "pdf": str(folder / f"{base}.pdf"),
        "svg_output_dir": str(folder / "svgs"),
        "stories_output": str(folder / "stories")
    }


def load_and_apply_config(app_instance, config_path: str):
    """
    Charge un fichier de config (YAML ou JSON) et met à jour les variables du GUI.
    Les valeurs absentes dans le config sont préservées (garde valeur actuelle du GUI).
    """

    from misenpageur.misenpageur.config import Config

    # Utiliser from_file pour détecter automatiquement le format
    cfg = Config.from_file(config_path)

    # Charger aussi les données brutes pour récupérer les champs supplémentaires (_input_file, _abbreviations_enabled)
    raw_data = {}
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            if config_path.lower().endswith('.json'):
                raw_data = json.load(f)
            else:
                import yaml
                raw_data = yaml.safe_load(f) or {}
    except Exception as e:
        print(f"[WARN] Erreur lors de la lecture des données brutes : {e}")

    # Helper pour chemins absolus
    resource_root = get_resource_path('.')
    config_dir = os.path.dirname(os.path.abspath(config_path))

    def make_abs(p, base_dir=resource_root):
        if not p:
            return ""
        return os.path.join(base_dir, p) if not os.path.isabs(p) else p

    # --- Fichiers d'entrée/sortie ---
    # Priorité au champ _input_file (sauvegardé par le mode debug), sinon input_file
    input_file = raw_data.get('_input_file') or getattr(cfg, 'input_file', None)
    if input_file:
        abs_path = make_abs(input_file, config_dir)
        app_instance.input_var.set(abs_path)
        # Mettre à jour la zone de dépôt visuelle
        from .callbacks import _update_drop_zone_text
        _update_drop_zone_text(app_instance, abs_path)
        # Calculer les chemins dérivés (html, agenda_html, pdf, etc.)
        derived_paths = _default_paths_from_input(abs_path)
        app_instance.html_var.set(derived_paths["html"])
        app_instance.agenda_var.set(derived_paths["agenda_html"])
        # Les chemins pdf, svg, stories peuvent être écrasés ci-dessous si présents dans la config
        if not (hasattr(cfg, 'output_pdf') and cfg.output_pdf):
            app_instance.pdf_var.set(derived_paths["pdf"])
        if not (hasattr(cfg, 'output_svg_dir') and cfg.output_svg_dir):
            app_instance.svg_output_var.set(derived_paths["svg_output_dir"])
        if not (hasattr(cfg, 'stories_output_dir') and cfg.stories_output_dir):
            app_instance.stories_output_var.set(derived_paths["stories_output"])
    if hasattr(cfg, 'output_pdf') and cfg.output_pdf:
        app_instance.pdf_var.set(make_abs(cfg.output_pdf, config_dir))
    if hasattr(cfg, 'output_svg_dir') and cfg.output_svg_dir:
        app_instance.svg_output_var.set(make_abs(cfg.output_svg_dir, config_dir))
    if hasattr(cfg, 'stories_output_dir') and cfg.stories_output_dir:
        app_instance.stories_output_var.set(make_abs(cfg.stories_output_dir, config_dir))

    # --- Options d'icônes ---
    if hasattr(cfg, 'chapeau_icon_enabled'):
        app_instance.chapeau_icon_var.set(cfg.chapeau_icon_enabled)
    if hasattr(cfg, 'free_icon_enabled'):
        app_instance.free_icon_var.set(cfg.free_icon_enabled)

    # --- SVG éditable ---
    if hasattr(cfg, 'generate_svg'):
        app_instance.generate_svg_var.set(cfg.generate_svg)

    # --- Debug mode ---
    if hasattr(cfg, 'debug_mode'):
        app_instance.debug_mode_var.set(cfg.debug_mode)

    # --- Images et ressources ---
    if cfg.cover_image:
        app_instance.cover_var.set(make_abs(cfg.cover_image, config_dir))
    if cfg.logos_dir:
        app_instance.logos_var.set(make_abs(cfg.logos_dir, config_dir))
    if hasattr(cfg, 'auteur_couv') and cfg.auteur_couv:
        app_instance.auteur_var.set(cfg.auteur_couv)
    if hasattr(cfg, 'auteur_couv_url') and cfg.auteur_couv_url:
        app_instance.auteur_url_var.set(cfg.auteur_couv_url)

    # --- Paramètres des logos ---
    if hasattr(cfg, 'logos_layout') and cfg.logos_layout:
        app_instance.logos_layout_var.set(cfg.logos_layout)
    if hasattr(cfg, 'logos_svg_file') and cfg.logos_svg_file:
        app_instance.logos_svg_var.set(make_abs(cfg.logos_svg_file, config_dir))
    if hasattr(cfg, 'logos_padding_mm') and cfg.logos_padding_mm is not None:
        app_instance.logos_padding_var.set(str(cfg.logos_padding_mm))

    # --- Paramètres de l'ours ---
    if hasattr(cfg, 'ours_layout') and cfg.ours_layout:
        app_instance.ours_layout_var.set(cfg.ours_layout)
    if hasattr(cfg, 'ours_svg_file') and cfg.ours_svg_file:
        app_instance.ours_svg_var.set(make_abs(cfg.ours_svg_file, config_dir))

    # Section 1 (ours background PNG)
    if isinstance(cfg.section_1, dict) and cfg.section_1.get("ours_background_png"):
        app_instance.ours_png_var.set(make_abs(cfg.section_1["ours_background_png"], config_dir))

    # Layout
    if isinstance(cfg.pdf_layout, dict):
        margin = cfg.pdf_layout.get("page_margin_mm")
        if margin is not None:
            app_instance.margin_var.set(str(margin))

    # Font
    if hasattr(cfg, 'font_size_mode'):
        app_instance.font_size_mode_var.set(cfg.font_size_mode)
    if hasattr(cfg, 'font_size_forced'):
        app_instance.font_size_forced_var.set(str(cfg.font_size_forced))

    # Date separator
    if hasattr(cfg, 'date_line') and isinstance(cfg.date_line, dict):
        if cfg.date_line.get("enabled", False):
            app_instance.date_separator_var.set("ligne")
    if hasattr(cfg, 'date_box') and isinstance(cfg.date_box, dict):
        if cfg.date_box.get("enabled", False):
            app_instance.date_separator_var.set("box")
            if cfg.date_box.get("back_color"):
                app_instance.date_box_back_color_var.set(cfg.date_box["back_color"])

    # Date spacing
    if hasattr(cfg, 'date_spaceBefore'):
        app_instance.date_spacing_var.set(str(cfg.date_spaceBefore))

    # Poster
    if isinstance(cfg.poster, dict):
        title = cfg.poster.get("title")
        if title is not None:
            app_instance.poster_title_var.set(title)

        design = cfg.poster.get("design")
        if design is not None:
            app_instance.poster_design_var.set(design)

        safety = cfg.poster.get("font_size_safety_factor")
        if safety is not None:
            app_instance.safety_factor_var.set(str(safety))

        alpha = cfg.poster.get("background_image_alpha")
        if alpha is not None:
            app_instance.alpha_var.set(alpha)

    # Cucaracha
    if isinstance(cfg.cucaracha_box, dict):
        ctype = cfg.cucaracha_box.get("content_type")
        if ctype:
            app_instance.cucaracha_type_var.set(ctype)

        cvalue = cfg.cucaracha_box.get("content_value")
        if cvalue:
            app_instance.cucaracha_value_var.set(cvalue)

        cfont = cfg.cucaracha_box.get("text_font_name")
        if cfont:
            app_instance.cucaracha_font_var.set(cfont)

        cfsize = cfg.cucaracha_box.get("text_font_size")
        if cfsize is not None:
            app_instance.cucaracha_font_size_var.set(str(cfsize))

    # Stories
    if isinstance(cfg.stories, dict):
        enabled = cfg.stories.get("enabled")
        if enabled is not None:
            app_instance.generate_stories_var.set(enabled)

        # Support pour output_dir dans le dict stories (compatibilité)
        output_dir = cfg.stories.get("output_dir")
        if output_dir:
            app_instance.stories_output_var.set(make_abs(output_dir, config_dir))

        font_name = cfg.stories.get("agenda_font_name")
        if font_name:
            app_instance.stories_font_name_var.set(font_name)

        font_size = cfg.stories.get("agenda_font_size")
        if font_size is not None:
            app_instance.stories_font_size_var.set(str(font_size))

        text_color = cfg.stories.get("text_color")
        if text_color:
            app_instance.stories_font_color_var.set(text_color)

        bg_color = cfg.stories.get("background_color")
        if bg_color:
            app_instance.stories_bg_color_var.set(bg_color)

        bg_alpha = cfg.stories.get("background_image_alpha")
        if bg_alpha is not None:
            app_instance.stories_alpha_var.set(bg_alpha)

        bg_type = cfg.stories.get("background_type")
        if bg_type:
            app_instance.stories_bg_type_var.set(bg_type)

        bg_image = cfg.stories.get("background_image")
        if bg_image:
            app_instance.stories_bg_image_var.set(make_abs(bg_image, config_dir))

    # v1.4.2+ : Importer les abréviations depuis _abbreviations_enabled (config.json debug)
    abbreviations_enabled = raw_data.get('_abbreviations_enabled', {})
    if abbreviations_enabled and hasattr(app_instance, 'abbreviation_vars'):
        for key, enabled in abbreviations_enabled.items():
            if key in app_instance.abbreviation_vars:
                app_instance.abbreviation_vars[key].set(enabled)

    # Forcer le rafraîchissement du GUI
    app_instance.update_idletasks()