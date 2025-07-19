import re
import os
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import yt_dlp
from ffmpeg import get_fmpeg_path


def sanitize_filename(filename: str) -> str:
    """
    Nettoie un nom de fichier en supprimant les caractères interdits
    """
    # Caractères interdits sous Windows et autres OS
    forbidden_chars = r'[<>:"/\\|?*]'
    
    # Remplace les caractères interdits par des underscores
    sanitized = re.sub(forbidden_chars, '_', filename)
    
    # Supprime les espaces en début/fin
    sanitized = sanitized.strip()
    
    # Supprime les points en fin (problématique sous Windows)
    sanitized = sanitized.rstrip('.')
    
    # Limite la longueur (255 caractères max pour la plupart des systèmes)
    if len(sanitized) > 200:  # Garde de la marge pour l'extension
        sanitized = sanitized[:200]
    
    # Si le nom est vide après nettoyage, utilise un nom par défaut
    if not sanitized:
        sanitized = "fichier_sans_nom"
    
    return sanitized


def format_time(seconds: int) -> str:
    """
    Formate une durée en secondes vers le format HH:MM:SS ou MM:SS
    """
    if seconds < 0:
        return "00:00"
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes:02d}:{seconds:02d}"


def format_size(bytes_size: int) -> str:
    """
    Formate une taille en octets vers une chaîne lisible (KB, MB, GB)
    """
    if bytes_size < 0:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    size = float(bytes_size)
    
    for unit in units:
        if size < 1024.0:
            if unit == 'B':
                return f"{int(size)} {unit}"
            else:
                return f"{size:.1f} {unit}"
        size /= 1024.0
    
    return f"{size:.1f} PB"


def format_number(number: int) -> str:
    """
    Formate un nombre avec des séparateurs de milliers
    """
    if number < 0:
        return "0"
    
    return f"{number:,}".replace(',', ' ')


def is_valid_url(url: str) -> bool:
    """
    Vérifie si une URL est valide pour YouTube/autres plateformes supportées
    """
    if not url or not isinstance(url, str):
        return False
    
    # Patterns pour les URLs supportées
    patterns = [
        r'https?://(www\.)?(youtube\.com|youtu\.be)',
        r'https?://(www\.)?soundcloud\.com',
        r'https?://(www\.)?vimeo\.com',
        r'https?://(www\.)?dailymotion\.com',
        r'https?://(www\.)?twitch\.tv',
    ]
    
    for pattern in patterns:
        if re.match(pattern, url, re.IGNORECASE):
            return True
    
    return False


def extract_video_id(url: str) -> Optional[str]:
    """
    Extrait l'ID d'une vidéo YouTube depuis son URL
    """
    patterns = [
        r'youtube\.com/watch\?v=([^&]+)',
        r'youtu\.be/([^?]+)',
        r'youtube\.com/embed/([^?]+)',
        r'youtube\.com/v/([^?]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None


def get_available_formats(url: str) -> List[Dict]:
    """
    Récupère les formats disponibles pour une URL donnée
    """
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
        formats = []
        seen_formats = set()
        
        for fmt in info.get('formats', []):
            # Informations de base
            format_id = fmt.get('format_id', 'unknown')
            ext = fmt.get('ext', 'unknown')
            quality = fmt.get('quality', 0)
            filesize = fmt.get('filesize', 0)
            
            # Informations vidéo
            height = fmt.get('height')
            width = fmt.get('width')
            fps = fmt.get('fps')
            vcodec = fmt.get('vcodec', 'none')
            
            # Informations audio
            acodec = fmt.get('acodec', 'none')
            abr = fmt.get('abr')  # Audio bitrate
            
            # Création d'une clé unique pour éviter les doublons
            key = (ext, height, width, vcodec, acodec)
            if key in seen_formats:
                continue
            seen_formats.add(key)
            
            # Description du format
            description_parts = []
            
            if height and width:
                description_parts.append(f"{height}p")
            elif height:
                description_parts.append(f"{height}p")
            
            if fps and fps > 30:
                description_parts.append(f"{fps}fps")
            
            if vcodec != 'none' and acodec != 'none':
                description_parts.append("vidéo+audio")
            elif vcodec != 'none':
                description_parts.append("vidéo seule")
            elif acodec != 'none':
                description_parts.append("audio seul")
                if abr:
                    description_parts.append(f"{abr}kbps")
            
            description = " ".join(description_parts) if description_parts else "Format inconnu"
            
            formats.append({
                'format_id': format_id,
                'ext': ext,
                'description': description,
                'filesize': filesize,
                'height': height,
                'width': width,
                'fps': fps,
                'vcodec': vcodec,
                'acodec': acodec,
                'abr': abr,
                'quality': quality,
                'is_video': vcodec != 'none',
                'is_audio': acodec != 'none',
            })
        
        # Tri par qualité (vidéo d'abord, puis audio)
        formats.sort(key=lambda x: (
            not x['is_video'],  # Vidéos en premier
            -(x['height'] or 0),  # Hauteur décroissante
            -(x['abr'] or 0),  # Bitrate audio décroissant
        ))
        
        return formats
        
    except Exception as e:
        print(f"Erreur lors de l'extraction des formats: {e}")
        return []


def get_video_info(url: str) -> Optional[Dict]:
    """
    Récupère les informations détaillées d'une vidéo
    """
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        
        # Extraction des informations importantes
        video_info = {
            'title': info.get('title', 'Titre inconnu'),
            'description': info.get('description', ''),
            'uploader': info.get('uploader', 'Inconnu'),
            'upload_date': info.get('upload_date', ''),
            'duration': info.get('duration', 0),
            'view_count': info.get('view_count', 0),
            'like_count': info.get('like_count', 0),
            'thumbnail': info.get('thumbnail', ''),
            'webpage_url': info.get('webpage_url', url),
            'id': info.get('id', ''),
            'ext': info.get('ext', 'mp4'),
            'filesize': info.get('filesize', 0),
            'categories': info.get('categories', []),
            'tags': info.get('tags', []),
        }
        
        return video_info
        
    except Exception as e:
        print(f"Erreur lors de l'extraction des infos: {e}")
        return None


def is_playlist_url(url: str) -> bool:
    """
    Vérifie si l'URL correspond à une playlist
    """
    playlist_patterns = [
        r'youtube\.com/playlist\?list=',
        r'youtube\.com/watch\?.*list=',
        r'soundcloud\.com/.+/sets/',
    ]
    
    for pattern in playlist_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            return True
    
    return False


def get_playlist_info(url: str) -> Optional[Dict]:
    """
    Récupère les informations d'une playlist
    """
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,  # Ne télécharge pas, juste les infos
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        
        if 'entries' not in info:
            return None
        
        playlist_info = {
            'title': info.get('title', 'Playlist sans nom'),
            'description': info.get('description', ''),
            'uploader': info.get('uploader', 'Inconnu'),
            'video_count': len(info['entries']),
            'id': info.get('id', ''),
            'webpage_url': info.get('webpage_url', url),
            'entries': []
        }
        
        # Informations sur chaque vidéo
        for entry in info['entries'][:10]:  # Limite à 10 pour l'aperçu
            if entry:
                playlist_info['entries'].append({
                    'title': entry.get('title', 'Titre inconnu'),
                    'id': entry.get('id', ''),
                    'duration': entry.get('duration', 0),
                    'url': entry.get('url', ''),
                })
        
        return playlist_info
        
    except Exception as e:
        print(f"Erreur lors de l'extraction de la playlist: {e}")
        return None


def create_output_directory(path: str) -> bool:
    """
    Crée le répertoire de sortie s'il n'existe pas
    """
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        print(f"Erreur lors de la création du dossier: {e}")
        return False


def get_default_download_path() -> str:
    """
    Retourne le chemin de téléchargement par défaut
    """
    # Dossier Téléchargements de l'utilisateur
    downloads_path = Path.home() / "Downloads" / "YT-Downloader"
    
    # Crée le dossier s'il n'existe pas
    create_output_directory(str(downloads_path))
    
    return str(downloads_path)


def validate_output_path(path: str) -> Tuple[bool, str]:
    """
    Valide un chemin de sortie
    """
    if not path:
        return False, "Chemin vide"
    
    path_obj = Path(path)
    
    # Vérifie si le dossier parent existe ou peut être créé
    try:
        path_obj.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return False, f"Impossible de créer le dossier: {e}"
    
    # Vérifie les permissions d'écriture
    try:
        # Test de création d'un fichier temporaire
        test_file = path_obj.parent / "test_write_permission.tmp"
        test_file.touch()
        test_file.unlink()
    except Exception as e:
        return False, f"Pas de permission d'écriture: {e}"
    
    return True, "Chemin valide"


def load_settings(settings_file: str = "settings.json") -> Dict:
    """
    Charge les paramètres depuis un fichier JSON
    """
    default_settings = {
        'output_path': get_default_download_path(),
        'default_format': 'mp3',
        'default_quality': 'medium',
        'create_subfolders': True,
        'overwrite_files': False,
        'max_concurrent_downloads': 3,
        'theme': 'dark',
        'language': 'fr',
    }
    
    try:
        settings_path = Path(settings_file)
        if settings_path.exists():
            with open(settings_path, 'r', encoding='utf-8') as f:
                loaded_settings = json.load(f)
                # Fusionne avec les paramètres par défaut
                default_settings.update(loaded_settings)
    except Exception as e:
        print(f"Erreur lors du chargement des paramètres: {e}")
    
    return default_settings


def save_settings(settings: Dict, settings_file: str = "settings.json") -> bool:
    """
    Sauvegarde les paramètres dans un fichier JSON
    """
    try:
        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Erreur lors de la sauvegarde des paramètres: {e}")
        return False


def check_dependencies() -> Dict[str, bool]:
    """
    Vérifie que les dépendances nécessaires sont installées
    """
    dependencies = {
        'yt-dlp': False,
        get_fmpeg_path(): False,
        'ffprobe': False,
    }
    
    # Test yt-dlp
    try:
        import yt_dlp
        dependencies['yt-dlp'] = True
    except ImportError:
        pass
    
    # Test FFmpeg
    try:
        subprocess.run([get_fmpeg_path(), '-version'], 
                      capture_output=True, check=True)
        dependencies[get_fmpeg_path()] = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    # Test FFprobe
    try:
        subprocess.run(['ffprobe', '-version'], 
                      capture_output=True, check=True)
        dependencies['ffprobe'] = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    return dependencies