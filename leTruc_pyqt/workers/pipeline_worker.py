#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Worker Qt pour exécuter le pipeline dans un thread séparé
"""
import os
import logging
from datetime import datetime
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal

from misenpageur import logger
from utils.helpers import ensure_parent_dir, project_defaults


class PipelineWorker(QThread):
    """Worker Qt pour exécuter le pipeline de génération"""

    # Signaux
    progress = pyqtSignal(int, int)  # (current_step, total_steps)
    status = pyqtSignal(str)  # message de statut
    finished = pyqtSignal(str)  # résumé final en cas de succès
    error = pyqtSignal(str)  # message d'erreur

    def __init__(self, params: dict):
        super().__init__()
        self.params = params
        self.log = None

    def run(self):
        """Exécute le pipeline dans le thread"""
        debug_mode = self.params.get('debug_mode', False)
        debug_dir = None

        # Configuration du logging en mode debug
        if debug_mode:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            pdf_path = Path(self.params['out_pdf'])
            debug_dir = pdf_path.parent / f"debug_run_{timestamp}"
            logger.setup_logger(str(debug_dir))

        self.log = logging.getLogger(__name__)
        final_layout_path = None

        try:
            # Import des modules nécessaires
            from misenpageur.misenpageur.config import Config
            from misenpageur.misenpageur.layout import Layout
            from misenpageur.misenpageur.pdfbuild import build_pdf
            from misenpageur.misenpageur.svgbuild import build_svg
            from misenpageur.misenpageur.layout_builder import build_layout_with_margins
            from misenpageur.misenpageur.html_utils import extract_paragraphs_from_html
            from misenpageur.misenpageur.image_builder import generate_story_images
            from misenpageur.misenpageur.draw_logic import read_text
            from biduleur.csv_utils import parse_bidul
            from biduleur.format_utils import output_html_file

            # Calculer le nombre total d'étapes
            total_steps = 3  # analyse, HTML, PDF
            if self.params.get('generate_svg') and self.params.get('out_svg_dir'):
                total_steps += 1
            if self.params.get('generate_stories'):
                total_steps += 1

            self.progress.emit(0, total_steps)
            current_step = 0

            # Créer les dossiers parents si nécessaire
            for path in [self.params['out_html'], self.params['out_agenda_html'],
                         self.params['out_pdf'], self.params['out_svg_dir']]:
                if path:
                    ensure_parent_dir(path)

            # Étape 1: Analyse du fichier
            current_step += 1
            self.status.emit(f"Étape {current_step}/{total_steps} : Analyse du fichier...")
            self.progress.emit(current_step, total_steps)

            html_body_bidul, html_body_agenda, number_of_lines = parse_bidul(
                self.params['input_file']
            )

            # Étape 2: Génération des HTML
            current_step += 1
            self.status.emit(f"Étape {current_step}/{total_steps} : Génération des HTML...")
            self.progress.emit(current_step, total_steps)

            output_html_file(html_body_bidul,
                             original_file_name=self.params['input_file'],
                             output_filename=self.params['out_html'])
            output_html_file(html_body_agenda,
                             original_file_name=self.params['input_file'],
                             output_filename=self.params['out_agenda_html'])

            html_text = read_text(self.params['out_html'])
            paras = extract_paragraphs_from_html(html_text)

            # Configuration
            defaults = project_defaults()
            project_root, cfg_path, lay_path = defaults["root"], defaults["config"], defaults["layout"]
            cfg = Config.from_yaml(cfg_path)
            cfg.project_root = project_root

            # Appliquer tous les paramètres
            cfg.input_html = self.params['out_html']
            cfg.skip_cover = not self.params['generate_cover']
            if self.params['out_pdf']:
                cfg.output_pdf = self.params['out_pdf']
            if self.params.get('cover_image'):
                cfg.cover_image = self.params['cover_image']
            if self.params.get('ours_background_png'):
                cfg.section_1['ours_background_png'] = self.params['ours_background_png']
            if self.params.get('logos_dir'):
                cfg.logos_dir = self.params['logos_dir']
            if self.params.get('auteur_couv'):
                cfg.auteur_couv = self.params['auteur_couv']
            if self.params.get('auteur_couv_url'):
                cfg.auteur_couv_url = self.params['auteur_couv_url']

            cfg.pdf_layout['page_margin_mm'] = self.params['page_margin_mm']
            cfg.font_size_mode = self.params['font_size_mode']
            cfg.font_size_forced = self.params['font_size_forced']
            cfg.logos_layout = self.params['logos_layout']
            cfg.logos_padding_mm = self.params['logos_padding_mm']

            # Séparateur de dates
            cfg.date_line['enabled'] = (self.params['date_separator_type'] == "ligne")
            cfg.date_box['enabled'] = (self.params['date_separator_type'] == "box")
            if cfg.date_box['enabled']:
                cfg.date_box['back_color'] = self.params['date_box_back_color']
            cfg.date_spaceBefore = self.params['date_spacing']
            cfg.date_spaceAfter = self.params['date_spacing']

            # Poster
            cfg.poster['design'] = self.params['poster_design']
            cfg.poster['font_size_safety_factor'] = self.params['font_size_safety_factor']
            cfg.poster['background_image_alpha'] = self.params['background_alpha']
            cfg.poster['title'] = self.params['poster_title']

            # Cucaracha
            cfg.cucaracha_box['content_type'] = self.params['cucaracha_type']
            cfg.cucaracha_box['content_value'] = self.params['cucaracha_value']
            cfg.cucaracha_box['text_font_name'] = self.params['cucaracha_text_font']
            cfg.cucaracha_box['text_font_size'] = self.params['cucaracha_font_size']

            # Stories
            cfg.stories['enabled'] = self.params['generate_stories']
            if self.params.get('stories_output_dir'):
                cfg.stories['output_dir'] = self.params['stories_output_dir']
            cfg.stories['agenda_font_name'] = self.params['stories_font_name']
            cfg.stories['agenda_font_size'] = self.params['stories_font_size']
            cfg.stories['text_color'] = self.params['stories_font_color']
            cfg.stories['background_color'] = self.params['stories_bg_color']
            cfg.stories['background_image_alpha'] = self.params['stories_alpha']
            cfg.stories['background_type'] = self.params['stories_bg_type']
            cfg.stories['background_image'] = self.params['stories_bg_image']

            # Construire le layout avec marges
            final_layout_path = build_layout_with_margins(lay_path, cfg)
            lay = Layout.from_yaml(final_layout_path)

            # Étape 3: Création du PDF
            report = {}
            if self.params['out_pdf']:
                current_step += 1
                self.status.emit(f"Étape {current_step}/{total_steps} : Création du PDF...")
                self.progress.emit(current_step, total_steps)
                report = build_pdf(project_root, cfg, lay, self.params['out_pdf'], cfg_path, paras)

            # Étape 4: Conversion SVG (optionnel)
            if self.params.get('generate_svg') and self.params.get('out_svg_dir'):
                if not report:
                    report = build_pdf(project_root, cfg, lay, os.devnull, cfg_path, paras)
                current_step += 1
                self.status.emit(f"Étape {current_step}/{total_steps} : Conversion en SVG...")
                self.progress.emit(current_step, total_steps)
                build_svg(project_root, cfg, lay, self.params['out_svg_dir'], cfg_path, paras)

            # Étape 5: Stories (optionnel)
            num_stories = 0
            if self.params.get('generate_stories'):
                current_step += 1
                self.status.emit(f"Étape {current_step}/{total_steps} : Création des Stories...")
                self.progress.emit(current_step, total_steps)
                num_stories = generate_story_images(project_root, cfg, paras)

            # Construire le résumé
            summary_lines = [
                f"Fichier d'entrée : {os.path.basename(self.params['input_file'])}",
                "-" * 40,
                "Fichiers de sortie créés :"
            ]

            if self.params['out_html']:
                summary_lines.append(f"  - HTML: {self.params['out_html']}")
            if self.params['out_agenda_html']:
                summary_lines.append(f"  - HTML (Agenda): {self.params['out_agenda_html']}")
            if self.params['out_pdf']:
                summary_lines.append(f"  - PDF: {self.params['out_pdf']}")
            if self.params.get('generate_svg') and self.params.get('out_svg_dir'):
                summary_lines.append(f"  - SVG: {self.params['out_svg_dir']}")
            if self.params.get('generate_stories') and self.params.get('stories_output_dir'):
                summary_lines.append(f"  - Stories: {self.params['stories_output_dir']}")

            summary_lines.append("\n" + "-" * 40)
            summary_lines.append(f"Nombre d'événements traités : {number_of_lines}")

            fs_main = report.get("font_size_main")
            if fs_main:
                summary_lines.append(f"Taille de police (pages 1-2): {fs_main:.2f} pt")

            fs_poster = report.get("font_size_poster_final")
            if fs_poster:
                fs_poster_opt = report.get("font_size_poster_optimal", 0)
                summary_lines.append(
                    f"Taille de police (poster): {fs_poster:.2f} pt (optimale: {fs_poster_opt:.2f} pt)"
                )

            if self.params.get('generate_stories') and num_stories > 0:
                summary_lines.append(f"Nombre de fichiers images créés pour la Story: {num_stories}")

            self.finished.emit("\n".join(summary_lines))

        except PermissionError as e:
            locked_file = e.filename or "un fichier de sortie"
            user_message = (
                f"Impossible d'écrire le fichier suivant :\n\n"
                f"{os.path.basename(locked_file)}\n\n"
                f"Veuillez vous assurer que le fichier n'est pas ouvert dans un autre programme."
            )
            self.log.error(f"Erreur de permission: {e.filename}", exc_info=True)
            self.error.emit(user_message)

        except Exception as e:
            self.log.error("Erreur inattendue", exc_info=True)
            import traceback
            self.error.emit(f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}")

        finally:
            if debug_mode:
                logger.shutdown_logger()
            if final_layout_path and os.path.exists(final_layout_path):
                try:
                    os.remove(final_layout_path)
                except OSError:
                    pass