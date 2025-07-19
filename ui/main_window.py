"""
Fenêtre principale de l'application YouTube Converter
"""

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QComboBox, 
                             QProgressBar, QTextEdit, QFileDialog, QListWidget,
                             QListWidgetItem, QGroupBox, QGridLayout, QSplitter,
                             QMessageBox, QSpacerItem, QSizePolicy)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap, QFont
from core.downloader import YouTubeDownloader
from core.converter import DownloadWorker
import os
import requests
from urllib.parse import urlparse, parse_qs
import glob
import re

def clean_output_folder(output_path):
    """Supprime les fichiers temporaires du dossier de sortie"""
    for ext in ('*.part', '*.webm', '*.f*', '*.temp'):
        for f in glob.glob(os.path.join(output_path, ext)):
            try:
                os.remove(f)
            except Exception:
                pass

def is_valid_youtube_url(url):
    """Vérifie si l'URL est une URL YouTube valide"""
    youtube_regex = re.compile(
        r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/'
        r'(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})'
    )
    return youtube_regex.match(url) is not None

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.downloader = YouTubeDownloader()
        self.conversion_workers = []
        self.url_timer = QTimer()
        self.url_timer.setSingleShot(True)
        self.url_timer.timeout.connect(self.fetch_video_info)
        self.init_ui()
        self.setup_connections()
        
    def init_ui(self):
        """Initialise l'interface utilisateur"""
        self.setWindowTitle("YouTube to MP3/MP4 Converter")
        self.setGeometry(100, 100, 900, 700)
        
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout principal
        main_layout = QVBoxLayout(central_widget)
        
        # Titre
        title_label = QLabel("YouTube Converter")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        
        # Groupe URL et paramètres
        input_group = QGroupBox("Téléchargement")
        input_layout = QGridLayout(input_group)
        
        # URL input
        input_layout.addWidget(QLabel("URL YouTube:"), 0, 0)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Collez l'URL de la vidéo YouTube ici...")
        input_layout.addWidget(self.url_input, 0, 1, 1, 2)  # Étend sur 2 colonnes
        
        # Format selection
        input_layout.addWidget(QLabel("Format:"), 1, 0)
        self.format_combo = QComboBox()
        self.format_combo.addItems(["MP4 (Vidéo)" ,"MP3 (Audio)"])
        input_layout.addWidget(self.format_combo, 1, 1)
        
        # Qualité
        input_layout.addWidget(QLabel("Qualité:"), 2, 0)
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["Meilleure", "720p", "480p", "360p", "144p"])
        input_layout.addWidget(self.quality_combo, 2, 1)
        
        # Dossier de destination
        input_layout.addWidget(QLabel("Destination:"), 3, 0)
        self.output_path = QLineEdit()
        self.output_path.setText(os.path.expanduser("~/Downloads"))
        input_layout.addWidget(self.output_path, 3, 1)
        
        self.browse_btn = QPushButton("Parcourir")
        input_layout.addWidget(self.browse_btn, 3, 2)
        
        main_layout.addWidget(input_group)
        
        # Splitter pour diviser l'interface
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Panel gauche - Informations vidéo
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        info_group = QGroupBox("Informations de la vidéo")
        info_layout = QVBoxLayout(info_group)
        
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(320, 180)
        self.thumbnail_label.setStyleSheet("border: 1px solid #666666; background-color: #1a1a1a;")
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setText("Miniature")
        info_layout.addWidget(self.thumbnail_label)
        
        self.title_label = QLabel("Titre: -")
        self.title_label.setWordWrap(True)
        info_layout.addWidget(self.title_label)
        
        self.duration_label = QLabel("Durée: -")
        info_layout.addWidget(self.duration_label)
        
        self.views_label = QLabel("Vues: -")
        info_layout.addWidget(self.views_label)
        
        self.author_label = QLabel("Auteur: -")
        info_layout.addWidget(self.author_label)
        
        # Indicateur de chargement
        self.loading_label = QLabel("Chargement des informations...")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setStyleSheet("color: #0066cc; font-style: italic;")
        self.loading_label.setVisible(False)
        info_layout.addWidget(self.loading_label)
        
        left_layout.addWidget(info_group)
        left_layout.addStretch()
        
        # Panel droit - Queue et progression
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Boutons d'action
        button_layout = QHBoxLayout()
        self.download_btn = QPushButton("Télécharger")
        self.download_btn.setEnabled(False)
        button_layout.addWidget(self.download_btn)
        
        self.clear_queue_btn = QPushButton("Vider la queue")
        button_layout.addWidget(self.clear_queue_btn)
        
        right_layout.addLayout(button_layout)
        
        # Queue de téléchargement
        queue_group = QGroupBox("Queue de téléchargement")
        queue_layout = QVBoxLayout(queue_group)
        
        self.download_queue = QListWidget()
        queue_layout.addWidget(self.download_queue)
        
        right_layout.addWidget(queue_group)
        
        # Progression globale
        progress_group = QGroupBox("Progression")
        progress_layout = QVBoxLayout(progress_group)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("Prêt")
        progress_layout.addWidget(self.status_label)
        
        right_layout.addWidget(progress_group)
        
        # Log
        log_group = QGroupBox("Journal")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(150)
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        
        right_layout.addWidget(log_group)
        
        # Ajout aux panels
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 500])
        
        main_layout.addWidget(splitter)
        
    def setup_connections(self):
        """Configure les connexions de signaux"""
        self.download_btn.clicked.connect(self.add_to_queue)
        self.browse_btn.clicked.connect(self.browse_output_folder)
        self.clear_queue_btn.clicked.connect(self.clear_queue)
        self.url_input.returnPressed.connect(self.fetch_video_info)
        self.url_input.textChanged.connect(self.on_url_changed)
        self.format_combo.currentTextChanged.connect(self.update_quality_choices)
        
    def on_url_changed(self, text):
        """Appelé quand l'URL change"""
        # Arrête le timer précédent
        self.url_timer.stop()
        
        # Nettoie l'affichage si l'URL est vide
        if not text.strip():
            self.reset_video_info()
            return
        
        # Vérifie si c'est une URL YouTube valide
        if is_valid_youtube_url(text.strip()):
            # Démarre un timer pour éviter les appels trop fréquents
            self.url_timer.start(1000)  # 1 seconde de délai
        else:
            self.reset_video_info()
            
    def reset_video_info(self):
        """Remet à zéro les informations vidéo"""
        self.title_label.setText("Titre: -")
        self.duration_label.setText("Durée: -")
        self.views_label.setText("Vues: -")
        self.author_label.setText("Auteur: -")
        self.thumbnail_label.clear()
        self.thumbnail_label.setText("Miniature")
        self.loading_label.setVisible(False)
        self.download_btn.setEnabled(False)
        if hasattr(self, 'video_info'):
            delattr(self, 'video_info')
        
    def fetch_video_info(self):
        """Récupère les informations de la vidéo"""
        url = self.url_input.text().strip()
        if not url:
            self.log("Veuillez entrer une URL YouTube")
            return
            
        if not is_valid_youtube_url(url):
            self.log("URL YouTube invalide")
            return
            
        # Affiche l'indicateur de chargement
        self.loading_label.setVisible(True)
        self.download_btn.setEnabled(False)
        self.log(f"Récupération des informations pour: {url}")
        
        # Thread pour récupérer les infos
        self.info_worker = VideoInfoWorker(url)
        self.info_worker.info_fetched.connect(self.on_info_fetched)
        self.info_worker.error_occurred.connect(self.on_info_error)
        self.info_worker.start()
        
    def on_info_fetched(self, info):
        """Traite les informations récupérées"""
        self.video_info = info

        # Debug : Affiche toutes les qualités disponibles
        formats = info.get('formats', [])
        print("---- Qualités disponibles ----")
        for fmt in formats:
            vcodec = fmt.get('vcodec', 'none')
            acodec = fmt.get('acodec', 'none')
            height = fmt.get('height', 'N/A')
            ext = fmt.get('ext', 'N/A')
            abr = fmt.get('abr', 'N/A')
            format_id = fmt.get('format_id', 'N/A')
            print(f"ID: {format_id} | {ext} | {height}p | vcodec: {vcodec} | acodec: {acodec} | abr: {abr}kbps")
        print("-----------------------------")

        # Mise à jour des labels
        self.title_label.setText(f"Titre: {info.get('title', 'N/A')}")
        self.duration_label.setText(f"Durée: {self.format_duration(info.get('duration', 0))}")
        self.views_label.setText(f"Vues: {info.get('view_count', 'N/A'):,}" if info.get('view_count') else "Vues: N/A")
        self.author_label.setText(f"Auteur: {info.get('uploader', 'N/A')}")
        
        # Chargement de la miniature
        self.load_thumbnail(info.get('thumbnail'))
        
        # Mise à jour des choix de qualité
        quality_choices = self.downloader.get_quality_choices(info['webpage_url'], media_type='mp4')
        self.quality_combo.clear()
        for choice in quality_choices:
            self.quality_combo.addItem(choice['label'], choice['format_id'])
        
        self.download_btn.setEnabled(True)
        self.loading_label.setVisible(False)
        self.log("Informations récupérées avec succès")
        
    def on_info_error(self, error):
        """Gère les erreurs de récupération d'infos"""
        self.log(f"Erreur: {error}")
        self.loading_label.setVisible(False)
        self.reset_video_info()
        
    def load_thumbnail(self, thumbnail_url):
        """Charge la miniature de la vidéo"""
        if not thumbnail_url:
            return
            
        try:
            response = requests.get(thumbnail_url, timeout=10)
            if response.status_code == 200:
                pixmap = QPixmap()
                pixmap.loadFromData(response.content)
                scaled_pixmap = pixmap.scaled(320, 180, Qt.AspectRatioMode.KeepAspectRatio, 
                                            Qt.TransformationMode.SmoothTransformation)
                self.thumbnail_label.setPixmap(scaled_pixmap)

        except Exception as e:
            self.log(f"Erreur chargement miniature: {e}")
            
    def format_duration(self, seconds):
        """Formate la durée en mm:ss"""
        if not seconds:
            return "N/A"
        mins = seconds // 60
        secs = seconds % 60
        return f"{mins:02d}:{secs:02d}"
        
    def add_to_queue(self):
        """Ajoute un téléchargement à la queue"""
        if not hasattr(self, 'video_info'):
            self.log("Aucune vidéo sélectionnée")
            return
            
        format_type = "audio" if "MP3" in self.format_combo.currentText() else "video"
        quality = self.quality_combo.currentText()
        
        item_text = f"{self.video_info['title']} - {self.format_combo.currentText()}"
        item = QListWidgetItem(item_text)
        item.setData(Qt.ItemDataRole.UserRole, {
            'info': self.video_info,
            'format': format_type,
            'quality': quality,
            'output_path': self.output_path.text(),
            'status': 'En attente'
        })
        
        self.download_queue.addItem(item)
        self.log(f"Ajouté à la queue: {item_text}")
        
        if not any(self.download_queue.item(i).data(Qt.ItemDataRole.UserRole)['status'] == 'Téléchargement'
                for i in range(self.download_queue.count())):
            self.start_next_download()
            
    def start_next_download(self):
        """Démarre le prochain téléchargement"""
        if any(w.isRunning() for w in self.conversion_workers):
            self.log("Un worker tourne déjà, attente…")
            return
        for i in range(self.download_queue.count()):
            item = self.download_queue.item(i)
            data = item.data(Qt.ItemDataRole.UserRole)
            if data['status'] == 'En attente':
                self.log(f"Lancement du téléchargement pour: {data['info']['title']}")
                self.start_download(item)
                break
                
    def start_download(self, item):
        """Démarre un téléchargement"""
        data = item.data(Qt.ItemDataRole.UserRole)
        data['status'] = 'Téléchargement'
        
        # Mise à jour de l'affichage
        item.setText(f"{data['info']['title']} - {data['status']}")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        clean_output_folder(data['output_path'])
        
        # Worker thread
        worker = DownloadWorker(
            data['info']['webpage_url'],
            data['format'],
            data['quality'],
            data['output_path']
        )
        
        # Connexion des signaux - teste les deux noms possibles
        if hasattr(worker, 'progress_updated'):
            worker.progress_updated.connect(self.on_progress_updated)
            self.log("Signal progress_updated connecté")
        elif hasattr(worker, 'progress'):
            worker.progress.connect(self.on_progress_updated)
            # self.log("Signal progress connecté") ## debug
        else:
            self.log("ERREUR: Aucun signal de progression trouvé!")
        
        worker.finished.connect(lambda: self.on_download_finished(item))
        worker.error_occurred.connect(lambda error: self.on_download_error(item, error))
        
        self.conversion_workers.append(worker)
        worker.start()
        
    def on_progress_updated(self, progress):
        """Met à jour la barre de progression"""
        # self.log(f"Progression reçue: {progress}%")  # Debug
        self.progress_bar.setValue(int(progress))
        self.status_label.setText(f"Téléchargement en cours... {progress:.1f}%")
        
    def on_download_finished(self, item):
        """Téléchargement terminé"""
        self.log("Téléchargement terminé, appel de on_download_finished")
        data = item.data(Qt.ItemDataRole.UserRole)
        data['status'] = 'Terminé'
        item.setData(Qt.ItemDataRole.UserRole, data)
        item.setText(f"{data['info']['title']} - ✓ Terminé")
        self.log(f"Téléchargement terminé: {data['info']['title']}")
        self.cleanup_finished_workers()
        self.start_next_download()
        
        # Cacher la barre si fini
        if not any(self.download_queue.item(i).data(Qt.ItemDataRole.UserRole)['status'] == 'Téléchargement' 
                  for i in range(self.download_queue.count())):
            self.progress_bar.setVisible(False)
            self.status_label.setText("Prêt")
            
    def on_download_error(self, item, error):
        """Erreur de téléchargement"""
        data = item.data(Qt.ItemDataRole.UserRole)
        data['status'] = 'Erreur'
        item.setData(Qt.ItemDataRole, data)
        item.setText(f"{data['info']['title']} - ✗ Erreur")
        self.log(f"Erreur téléchargement: {error}")
        self.cleanup_finished_workers()
        self.start_next_download()
        
    def cleanup_finished_workers(self):
        """Nettoie les workers terminés"""
        self.conversion_workers = [w for w in self.conversion_workers if w.isRunning()]
        
    def browse_output_folder(self):
        """Sélectionne le dossier de destination"""
        folder = QFileDialog.getExistingDirectory(self, "Sélectionner le dossier de destination")
        if folder:
            self.output_path.setText(folder)
            
    def clear_queue(self):
        """Vide la queue de téléchargement"""
        self.download_queue.clear()
        self.log("Queue vidée")
        
    def log(self, message):
        """Ajoute un message au journal"""
        self.log_text.append(f"[{self.get_timestamp()}] {message}")
        
    def get_timestamp(self):
        """Retourne l'horodatage actuel"""
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S")

    def update_quality_choices(self):
        """Met à jour la liste des qualités selon le format choisi"""
        if not hasattr(self, 'video_info'):
            return
        format_type = "audio" if "MP3" in self.format_combo.currentText() else "video"
        # Appelle la bonne méthode du downloader
        if format_type == "audio":
            choices = self.downloader.get_quality_choices(self.video_info['webpage_url'], media_type='mp3')
        else:
            choices = self.downloader.get_quality_choices(self.video_info['webpage_url'], media_type='mp4')
        self.quality_combo.clear()
        for choice in choices:
            self.quality_combo.addItem(choice['label'], choice['format_id'])

class VideoInfoWorker(QThread):
    """Worker thread pour récupérer les infos vidéo"""
    info_fetched = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, url):
        super().__init__()
        self.url = url
        
    def run(self):
        try:
            from core.downloader import YouTubeDownloader
            downloader = YouTubeDownloader()
            info = downloader.get_video_info(self.url)
            self.info_fetched.emit(info)
        except Exception as e:
            self.error_occurred.emit(str(e))