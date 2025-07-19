import os
import sys
import subprocess
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal, QObject
import yt_dlp
#from utils import format_time, sanitize_filename, get_available_formats
from core.utils import format_time, sanitize_filename, get_available_formats
from ffmpeg import get_fmpeg_path


class DownloadWorker(QThread):
    """Worker thread pour le téléchargement et la conversion"""
    
    # Signaux pour communiquer avec l'interface
    progress = pyqtSignal(int)  # Progression en pourcentage
    status = pyqtSignal(str)    # Statut actuel
    finished = pyqtSignal(bool, str)  # Succès/échec et message
    info_extracted = pyqtSignal(dict)  # Informations de la vidéo
    error_occurred = pyqtSignal(str) #signal d'erreur
    
    def __init__(self, url, format_type, quality, output_path, cookies_file=None):
        super().__init__()
        self.url = url
        self.output_path = Path(output_path)
        self.format_type = format_type
        self.quality = quality
        self.cookies_file = cookies_file
        print(f" path : {self.output_path}")
        self.is_cancelled = False
        self.temp_file = None  # Nouveau : pour stocker le fichier temporaire
        
    def run(self):
        """Méthode principale du thread"""
        try:
            self.status.emit("Extraction des informations...")
            
            # Configuration yt-dlp
            ydl_opts = self._get_ydl_options()
            print("Options yt-dlp :", ydl_opts)
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extraction des informations
                info = ydl.extract_info(self.url, download=False)
                self.info_extracted.emit({
                    'title': info.get('title', 'Inconnu'),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', 'Inconnu'),
                    'view_count': info.get('view_count', 0)
                })
                
                if self.is_cancelled:
                    return
                
                # Téléchargement
                self.status.emit("Téléchargement en cours...")
                ydl.download([self.url])
                
                # NOUVEAU : Conversion audio pour les vidéos
                if self.format_type in ['mp4', 'video'] and self.temp_file:
                    self.status.emit("Vérification et conversion audio...")
                    self._ensure_aac_audio()
                
            self.finished.emit(True, "Téléchargement terminé avec succès!")
            
        except Exception as e:
            error_msg = f"Erreur: {str(e)}"
            self.error_occurred.emit(error_msg)
            self.finished.emit(False, error_msg)
    
    def _get_ydl_options(self):
        """Configure les options pour yt-dlp"""
        
        def progress_hook(d):
            if self.is_cancelled:
                raise yt_dlp.DownloadError("Téléchargement annulé")
                
            if d['status'] == 'downloading':
                if 'total_bytes' in d:
                    percent = int(d['downloaded_bytes'] / d['total_bytes'] * 100)
                    self.progress.emit(percent)
                elif '_percent_str' in d:
                    # Extraction du pourcentage depuis la chaîne
                    percent_str = d['_percent_str'].strip().replace('%', '')
                    try:
                        percent = int(float(percent_str))
                        self.progress.emit(percent)
                    except ValueError:
                        pass
            elif d['status'] == 'finished':
                self.progress.emit(100)
                # NOUVEAU : Stocker le fichier temporaire pour les vidéos
                if self.format_type in ['mp4', 'video']:
                    self.temp_file = d['filename']
                self.status.emit("Téléchargement terminé, finalisation...")
        
        # Template de nom de fichier - MODIFIÉ
        if self.format_type in ['mp4', 'video']:
            filename_template = '%(title)s_temp.%(ext)s'
        else:
            filename_template = '%(title)s.%(ext)s'
        
        # Options de base
        ydl_opts = {
            'outtmpl': str(self.output_path / filename_template),
            'progress_hooks': [progress_hook],
        }
        
        print(f"format type : {self.format_type}")
        
        # Configuration selon le format souhaité
        if self.format_type == 'mp3' or self.format_type == 'audio':
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        elif self.format_type == 'mp4' or self.format_type == 'video':
            # NOUVEAU : Format optimisé pour éviter l'Opus
            ydl_opts.update({
                'format': (
                    'bestvideo[vcodec^=avc1][ext=mp4]+bestaudio[acodec=aac]/'
                    'bestvideo[ext=mp4]+bestaudio[acodec=aac]/'
                    'bestvideo[ext=mp4]+140/'  # Format 140 = AAC
                    'best[ext=mp4]'
                ),
                'merge_output_format': 'mp4',
                # Pas de post-processeur ici, on le fera manuellement
            })
        
        if self.cookies_file:
            ydl_opts['cookiefile'] = self.cookies_file
        
        return ydl_opts
    
    def _ensure_aac_audio(self):
        """NOUVELLE MÉTHODE : S'assure que l'audio est en AAC"""
        if not self.temp_file or not Path(self.temp_file).exists():
            return
        
        try:
            # Vérifier le codec audio
            audio_codec = self._get_audio_codec(self.temp_file)
            print(f"Codec audio détecté: {audio_codec}")
            
            # Nom du fichier final
            final_file = self.temp_file.replace('_temp.mp4', '.mp4')
            
            if audio_codec != 'aac':
                self.status.emit("Conversion audio vers AAC...")
                print("Conversion audio nécessaire...")
                self._convert_to_aac(self.temp_file, final_file)
            else:
                print("Audio déjà en AAC, simple renommage...")
                Path(self.temp_file).rename(final_file)
                
        except Exception as e:
            print(f"Erreur lors de la conversion audio: {e}")
            # En cas d'erreur, renommer le fichier temporaire
            final_file = self.temp_file.replace('_temp.mp4', '_original.mp4')
            if Path(self.temp_file).exists():
                Path(self.temp_file).rename(final_file)
    
    def _get_audio_codec(self, file_path):
        """NOUVELLE MÉTHODE : Détecte le codec audio d'un fichier"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-select_streams', 'a:0',
                '-show_entries', 'stream=codec_name', '-of', 'csv=p=0',
                file_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except:
            return 'unknown'
    
    def _convert_to_aac(self, input_file, output_file):
        """NOUVELLE MÉTHODE : Convertit l'audio en AAC"""
        cmd = [
            get_fmpeg_path(), '-y', '-i', input_file,
            '-c:v', 'copy',           # Copie la vidéo sans réencodage
            '-c:a', 'aac',            # Force l'audio en AAC
            '-b:a', '192k',           # Bitrate audio
            '-ac', '2',               # Stéréo
            '-ar', '44100',           # Fréquence d'échantillonnage
            '-movflags', '+faststart', # Optimisation pour la lecture
            output_file
        ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print("Conversion audio réussie !")
            
            # Supprimer le fichier temporaire
            if Path(input_file).exists():
                Path(input_file).unlink()
                
        except subprocess.CalledProcessError as e:
            print(f"Erreur lors de la conversion: {e}")
            # En cas d'erreur, renommer le fichier original
            if Path(input_file).exists():
                Path(input_file).rename(output_file)
    
    def _get_audio_quality(self):
        """Convertit la qualité en paramètre pour FFmpeg"""
        quality_map = {
            'best': '0',      # VBR haute qualité
            'high': '2',      # ~190 kbps
            'medium': '4',    # ~165 kbps
            'low': '7',       # ~100 kbps
        }
        return quality_map.get(self.quality, '0')
    
    def cancel(self):
        """Annule le téléchargement"""
        self.is_cancelled = True


class MediaConverter:
    """Classe pour les conversions de médias avec FFmpeg"""
    
    @staticmethod
    def is_ffmpeg_available():
        """Vérifie si FFmpeg est disponible"""
        try:
            subprocess.run([get_fmpeg_path(), '-version'], 
                         capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    @staticmethod
    def convert_audio(input_path, output_path, target_format, quality='medium'):
        """Convertit un fichier audio"""
        input_path = Path(input_path)
        output_path = Path(output_path)
        
        if not input_path.exists():
            raise FileNotFoundError(f"Fichier source introuvable: {input_path}")
        
        # Commande FFmpeg de base
        cmd = [get_fmpeg_path(), '-i', str(input_path), '-y']  # -y pour écraser
        
        # Configuration selon le format cible
        if target_format.lower() == 'mp3':
            quality_map = {
                'low': '128k',
                'medium': '192k',
                'high': '320k'
            }
            bitrate = quality_map.get(quality, '192k')
            cmd.extend(['-codec:a', 'libmp3lame', '-b:a', bitrate])
        
        elif target_format.lower() == 'wav':
            cmd.extend(['-codec:a', 'pcm_s16le'])
        
        elif target_format.lower() == 'aac':
            quality_map = {
                'low': '96k',
                'medium': '128k',
                'high': '256k'
            }
            bitrate = quality_map.get(quality, '128k')
            cmd.extend(['-codec:a', 'aac', '-b:a', bitrate])
        
        cmd.append(str(output_path))
        
        # Exécution de la conversion
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True, "Conversion réussie"
        except subprocess.CalledProcessError as e:
            return False, f"Erreur FFmpeg: {e.stderr}"
    
    @staticmethod
    def ensure_aac_audio(input_path, output_path=None):
        """NOUVELLE MÉTHODE : S'assure que le fichier a un audio AAC compatible"""
        input_path = Path(input_path)
        if output_path is None:
            output_path = input_path.parent / f"{input_path.stem}_aac{input_path.suffix}"
        
        if not input_path.exists():
            raise FileNotFoundError(f"Fichier source introuvable: {input_path}")
        
        cmd = [
            get_fmpeg_path(), '-y', '-i', str(input_path),
            '-c:v', 'copy',           # Copie la vidéo
            '-c:a', 'aac',            # Force AAC
            '-b:a', '192k',           # Bitrate
            '-ac', '2',               # Stéréo
            '-ar', '44100',           # Fréquence
            '-movflags', '+faststart', # Optimisation
            str(output_path)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True, f"Conversion réussie: {output_path}"
        except subprocess.CalledProcessError as e:
            return False, f"Erreur FFmpeg: {e.stderr}"
    
    @staticmethod
    def check_audio_codec(file_path):
        """NOUVELLE MÉTHODE : Vérifie le codec audio d'un fichier"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-select_streams', 'a:0',
                '-show_entries', 'stream=codec_name', '-of', 'csv=p=0',
                str(file_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            codec = result.stdout.strip()
            return codec
        except:
            return 'unknown'
    
    @staticmethod
    def get_media_info(file_path):
        """Récupère les informations d'un fichier média"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', '-show_streams', str(file_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            import json
            data = json.loads(result.stdout)
            
            # Extraction des informations principales
            format_info = data.get('format', {})
            streams = data.get('streams', [])
            
            info = {
                'duration': float(format_info.get('duration', 0)),
                'size': int(format_info.get('size', 0)),
                'bitrate': int(format_info.get('bit_rate', 0)),
                'format': format_info.get('format_name', 'Unknown'),
            }
            
            # Informations audio/vidéo
            for stream in streams:
                if stream.get('codec_type') == 'audio':
                    info.update({
                        'audio_codec': stream.get('codec_name', 'Unknown'),
                        'sample_rate': int(stream.get('sample_rate', 0)),
                        'channels': int(stream.get('channels', 0)),
                    })
                elif stream.get('codec_type') == 'video':
                    info.update({
                        'video_codec': stream.get('codec_name', 'Unknown'),
                        'width': int(stream.get('width', 0)),
                        'height': int(stream.get('height', 0)),
                        'fps': eval(stream.get('r_frame_rate', '0/1')),
                    })
            
            return info
            
        except Exception as e:
            return {'error': str(e)}


class PlaylistDownloader(QThread):
    """Worker pour télécharger des playlists"""
    
    progress = pyqtSignal(int, int)  # current, total
    video_finished = pyqtSignal(str, bool)  # title, success
    all_finished = pyqtSignal(bool, str)
    
    def __init__(self, url, output_path, format_type="mp3", quality="best"):
        super().__init__()
        self.url = url
        self.output_path = Path(output_path)
        self.format_type = format_type
        self.quality = quality
        self.is_cancelled = False
    
    def run(self):
        """Télécharge une playlist complète"""
        try:
            # Configuration pour extraire les informations de la playlist
            ydl_opts = {
                'extract_flat': True,
                'quiet': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                playlist_info = ydl.extract_info(self.url, download=False)
                
            if 'entries' not in playlist_info:
                self.all_finished.emit(False, "Ce n'est pas une playlist valide")
                return
            
            entries = playlist_info['entries']
            total_videos = len(entries)
            
            # Téléchargement de chaque vidéo
            for i, entry in enumerate(entries):
                if self.is_cancelled:
                    break
                
                video_url = entry.get('url') or f"https://youtube.com/watch?v={entry['id']}"
                video_title = entry.get('title', f'Vidéo {i+1}')
                
                # Créer un worker pour cette vidéo
                worker = DownloadWorker(video_url, self.format_type, self.quality, self.output_path)
                
                success = self._download_single_video(worker)
                self.video_finished.emit(video_title, success)
                self.progress.emit(i + 1, total_videos)
            
            if not self.is_cancelled:
                self.all_finished.emit(True, f"Playlist téléchargée: {total_videos} vidéos")
            
        except Exception as e:
            self.all_finished.emit(False, f"Erreur playlist: {str(e)}")
    
    def _download_single_video(self, worker):
        """Télécharge une seule vidéo de façon synchrone"""
        try:
            # Configuration yt-dlp
            ydl_opts = worker._get_ydl_options()
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([worker.url])
            
            return True
        except Exception:
            return False
    
    def cancel(self):
        """Annule le téléchargement de la playlist"""
        self.is_cancelled = True


# NOUVELLE FONCTION UTILITAIRE pour corriger les fichiers existants
def fix_existing_mp4_audio(file_path):
    """
    Corrige l'audio d'un fichier MP4 existant
    """
    file_path = Path(file_path)
    if not file_path.exists():
        print(f"Fichier introuvable: {file_path}")
        return False
    
    # Vérifier le codec audio
    codec = MediaConverter.check_audio_codec(file_path)
    print(f"Codec audio détecté: {codec}")
    
    if codec == 'aac':
        print("Le fichier a déjà un audio AAC compatible")
        return True
    
    # Créer le fichier corrigé
    output_path = file_path.parent / f"{file_path.stem}_fixed.mp4"
    success, message = MediaConverter.ensure_aac_audio(file_path, output_path)
    
    if success:
        print(f"Fichier corrigé créé: {output_path}")
        return True
    else:
        print(f"Échec de la correction: {message}")
        return False