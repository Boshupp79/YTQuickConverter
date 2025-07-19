"""
Module de téléchargement YouTube utilisant yt-dlp - Version avec qualité vidéo optimisée
"""

import yt_dlp
import os
import re
from pathlib import Path
import subprocess
import sys
from ffmpeg import get_fmpeg_path

def convert_to_aac(input_file, output_file):
    """
    Convertit un fichier vidéo ou audio en mp4/aac
    Gère correctement l'audio Opus et autres formats
    """
    cmd = [
        get_fmpeg_path(), '-y',
        '-i', input_file,
        '-c:v', 'copy',  # Copie la vidéo sans réencodage
        '-c:a', 'aac',   # Force l'encodage audio en AAC
        '-b:a', '192k',  # Bitrate audio
        '-ac', '2',      # Stéréo
        '-ar', '44100',  # Fréquence d'échantillonnage
        '-movflags', '+faststart',  # Optimisation pour la lecture
        output_file
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"Conversion réussie: {output_file}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Erreur lors de la conversion: {e}")
        print(f"Sortie d'erreur: {e.stderr}")
        return False

class YouTubeDownloader:
    def __init__(self):
        self.ydl_opts_base = {
            'quiet': True,
            'no_warnings': True,
            'extractaudio': False,
            'audioformat': 'mp3',
            'outtmpl': '%(title)s.%(ext)s',
            'ignoreerrors': True,
        }

    def _get_ffprobe_path(self):
        """Retourne le chemin vers ffprobe"""
        return get_fmpeg_path().replace('ffmpeg', 'ffprobe')
        
    def get_video_info(self, url):
        """
        Récupère les informations d'une vidéo YouTube
        """
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'cookiesfrombrowser': ('firefox', ),
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                return {
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'view_count': info.get('view_count', 0),
                    'uploader': info.get('uploader', 'Unknown'),
                    'thumbnail': info.get('thumbnail', ''),
                    'webpage_url': info.get('webpage_url', url),
                    'id': info.get('id', ''),
                    'formats': info.get('formats', [])
                }
            except Exception as e:
                raise Exception(f"Erreur lors de la récupération des informations: {str(e)}")
    
    def download_audio(self, url, output_path, quality='best', progress_hook=None):
        """
        Télécharge l'audio d'une vidéo YouTube en MP3
        """
        Path(output_path).mkdir(parents=True, exist_ok=True)
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192' if quality == 'best' else '128',
            }],
            'quiet': False,
            'no_warnings': False,
        }
        
        if progress_hook:
            ydl_opts['progress_hooks'] = [progress_hook]
            
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                ydl.download([url])
                return True
            except Exception as e:
                raise Exception(f"Erreur lors du téléchargement audio: {str(e)}")
    
    def download_video(self, url, output_path, quality='best'):
        """
        Télécharge une vidéo YouTube avec qualité et audio AAC optimisés
        """
        return self.download_video_with_quality_optimized(url, output_path, quality)
    
    def download_video_with_quality_optimized(self, url, output_path, quality='best'):
        """
        NOUVELLE MÉTHODE PRINCIPALE : Télécharge avec qualité vidéo optimisée + audio AAC
        """
        Path(output_path).mkdir(parents=True, exist_ok=True)
        
        # D'abord, analyser les formats disponibles pour cette vidéo spécifique
        print("🔍 Analyse des formats disponibles...")
        available_formats = self._analyze_available_formats(url)
        
        if not available_formats:
            print("⚠️  Aucun format analysé, utilisation des stratégies standard")
            return self._download_with_fallback_strategies(url, output_path, quality)
        
        # Choisir la meilleure stratégie selon les formats disponibles
        best_strategy = self._choose_best_strategy(available_formats, quality)
        print(f"🎯 Stratégie choisie: {best_strategy['name']}")
        print(f"📊 Format cible: {best_strategy['description']}")
        
        # Essayer la stratégie optimale d'abord
        try:
            result = best_strategy['function'](url, output_path, available_formats)
            if result and os.path.exists(result):
                video_info = self._get_video_quality_info(result)
                print(f"✅ Succès! Qualité obtenue: {video_info}")
                return result
        except Exception as e:
            print(f"❌ Stratégie optimale échouée: {e}")
        
        # Fallback sur les stratégies standard
        print("🔄 Fallback sur les stratégies standard...")
        return self._download_with_fallback_strategies(url, output_path, quality)

    def _analyze_available_formats(self, url):
        """
        Analyse détaillée des formats disponibles pour une vidéo spécifique
        """
        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                formats = info.get('formats', [])
                
                analysis = {
                    'video_formats': [],
                    'audio_formats': [],
                    'best_video': None,
                    'best_audio_aac': None,
                    'max_height': 0,
                    'has_h264': False,
                    'has_aac': False
                }
                
                for fmt in formats:
                    # Analyser les formats vidéo
                    if fmt.get('vcodec') and fmt.get('vcodec') != 'none':
                        height = fmt.get('height', 0)
                        fps = fmt.get('fps', 0)
                        vcodec = fmt.get('vcodec', '')
                        
                        video_fmt = {
                            'format_id': fmt.get('format_id'),
                            'height': height,
                            'width': fmt.get('width', 0),
                            'fps': fps,
                            'vcodec': vcodec,
                            'tbr': fmt.get('tbr', 0),
                            'filesize': fmt.get('filesize', 0),
                            'ext': fmt.get('ext', ''),
                            'quality_score': self._calculate_video_quality_score(height, fps, vcodec)
                        }
                        
                        analysis['video_formats'].append(video_fmt)
                        analysis['max_height'] = max(analysis['max_height'], height)
                        
                        if 'avc1' in vcodec or 'h264' in vcodec.lower():
                            analysis['has_h264'] = True
                            
                        # Meilleur format vidéo
                        if not analysis['best_video'] or video_fmt['quality_score'] > analysis['best_video']['quality_score']:
                            analysis['best_video'] = video_fmt
                    
                    # Analyser les formats audio
                    if fmt.get('acodec') and fmt.get('acodec') != 'none':
                        acodec = fmt.get('acodec', '')
                        
                        audio_fmt = {
                            'format_id': fmt.get('format_id'),
                            'acodec': acodec,
                            'abr': fmt.get('abr', 0),
                            'asr': fmt.get('asr', 0),
                            'quality_score': self._calculate_audio_quality_score(acodec, fmt.get('abr', 0))
                        }
                        
                        analysis['audio_formats'].append(audio_fmt)
                        
                        if 'aac' in acodec.lower():
                            analysis['has_aac'] = True
                            if not analysis['best_audio_aac'] or audio_fmt['quality_score'] > analysis['best_audio_aac']['quality_score']:
                                analysis['best_audio_aac'] = audio_fmt
                
                # Trier par qualité
                analysis['video_formats'].sort(key=lambda x: x['quality_score'], reverse=True)
                analysis['audio_formats'].sort(key=lambda x: x['quality_score'], reverse=True)
                
                return analysis
                
        except Exception as e:
            print(f"❌ Erreur analyse formats: {e}")
            return None

    def _calculate_video_quality_score(self, height, fps, vcodec):
        """
        Calcule un score de qualité vidéo
        """
        score = 0
        
        # Score basé sur la résolution
        if height >= 1080:
            score += 100
        elif height >= 720:
            score += 75
        elif height >= 480:
            score += 50
        else:
            score += 25
            
        # Bonus pour les FPS élevés
        if fps >= 60:
            score += 20
        elif fps >= 30:
            score += 10
            
        # Bonus pour H.264
        if 'avc1' in vcodec or 'h264' in vcodec.lower():
            score += 15
            
        return score

    def _calculate_audio_quality_score(self, acodec, abr):
        """
        Calcule un score de qualité audio
        """
        score = 0
        
        # Bonus pour AAC
        if 'aac' in acodec.lower():
            score += 50
        elif 'mp4a' in acodec.lower():
            score += 45
        elif 'opus' in acodec.lower():
            score += 30  # Opus est bon mais on préfère AAC
            
        # Score basé sur le bitrate
        if abr >= 192:
            score += 30
        elif abr >= 128:
            score += 20
        elif abr >= 96:
            score += 10
            
        return score

    # def _choose_best_strategy(self, available_formats, quality):
    #     """
    #     Choisit la meilleure stratégie selon les formats disponibles
    #     """
    #     max_height = available_formats['max_height']
    #     has_h264 = available_formats['has_h264']
    #     has_aac = available_formats['has_aac']
    #     best_video = available_formats['best_video']
    #     best_audio_aac = available_formats['best_audio_aac']
        
    #     # Stratégie selon la qualité disponible et demandée
    #     if quality == 'best' or quality == '1080p':
    #         if max_height >= 1080 and has_h264 and has_aac:
    #             return {
    #                 'name': 'Format Premium 1080p H.264+AAC',
    #                 'description': f"1080p H.264 + AAC {best_audio_aac['abr'] if best_audio_aac else 'N/A'}kbps",
    #                 'function': self._download_premium_quality
    #             }
    #         elif max_height >= 720 and has_h264:
    #             return {
    #                 'name': 'Format Haute Qualité 720p+',
    #                 'description': f"{max_height}p H.264 + audio optimal",
    #                 'function': self._download_high_quality_adaptive
    #             }
        
    #     if quality == '720p' or max_height >= 720:
    #         if has_h264 and has_aac:
    #             return {
    #                 'name': 'Format Standard 720p H.264+AAC',
    #                 'description': f"720p H.264 + AAC",
    #                 'function': self._download_standard_quality
    #             }
        
    #     # Fallback intelligent
    #     if has_aac:
    #         return {
    #             'name': 'Format Adaptatif avec AAC',
    #             'description': f"Meilleure qualité disponible ({max_height}p) + AAC",
    #             'function': self._download_adaptive_with_aac
    #         }
    #     else:
    #         return {
    #             'name': 'Format Conversion AAC',
    #             'description': f"Meilleure qualité disponible ({max_height}p) + conversion AAC",
    #             'function': self._download_with_conversion
    #         }
        
    def _choose_best_strategy(self, available_formats, quality):
    # TOUJOURS forcer la conversion pour garantir la qualité
        return {
            'name': 'Conversion Haute Qualité Forcée',
            'description': f"Conversion AAC optimisée garantie",
            'function': self._download_and_convert_hq
        }

    def _download_premium_quality(self, url, output_path, available_formats):
        """
        Téléchargement qualité premium (1080p H.264 + AAC)
        """
        best_video = available_formats['best_video']
        best_audio = available_formats['best_audio_aac']
        
        format_selector = (
            f"bestvideo[height<=1080][vcodec^=avc1][fps>=30]+bestaudio[acodec=aac]/"
            f"bestvideo[height<=1080][vcodec^=avc1]+{best_audio['format_id']}/"
            f"{best_video['format_id']}+{best_audio['format_id']}/"
            f"bestvideo[height<=1080]+bestaudio[acodec=aac]"
        )
        
        return self._download_with_format(url, output_path, format_selector)

    def _download_high_quality_adaptive(self, url, output_path, available_formats):
        """
        Téléchargement haute qualité adaptatif
        """
        max_height = available_formats['max_height']
        target_height = min(max_height, 1080)
        
        format_selector = (
            f"bestvideo[height<={target_height}][vcodec^=avc1][fps>=30]+bestaudio[acodec=aac]/"
            f"bestvideo[height<={target_height}][vcodec^=avc1]+bestaudio[acodec=aac]/"
            f"bestvideo[height<={target_height}]+bestaudio[acodec=aac]/"
            f"best[height<={target_height}][vcodec^=avc1]"
        )
        
        return self._download_with_format(url, output_path, format_selector)

    def _download_standard_quality(self, url, output_path, available_formats):
        """
        Téléchargement qualité standard (720p)
        """
        format_selector = (
            "bestvideo[height<=720][vcodec^=avc1][fps>=30]+bestaudio[acodec=aac]/"
            "bestvideo[height<=720][vcodec^=avc1]+bestaudio[acodec=aac]/"
            "bestvideo[height<=720]+bestaudio[acodec=aac]/"
            "best[height<=720]"
        )
        
        return self._download_with_format(url, output_path, format_selector)

    def _download_adaptive_with_aac(self, url, output_path, available_formats):
        """
        Téléchargement adaptatif avec AAC garanti
        """
        best_audio = available_formats['best_audio_aac']
        
        format_selector = (
            f"bestvideo+{best_audio['format_id']}/"
            f"bestvideo+bestaudio[acodec=aac]/"
            f"best[acodec=aac]"
        )
        
        return self._download_with_format(url, output_path, format_selector)

    def _download_with_conversion(self, url, output_path, available_formats):
        """
        Téléchargement avec conversion AAC forcée
        """
        best_video = available_formats['best_video']
        
        # Télécharger la meilleure qualité disponible
        format_selector = (
            f"{best_video['format_id']}+bestaudio/"
            f"bestvideo[height<={best_video['height']}]+bestaudio/"
            f"best[height<={best_video['height']}]"
        )
        
        temp_file = self._download_with_format(url, output_path, format_selector, temp=True)
        
        if temp_file:
            # Conversion vers AAC
            final_file = temp_file.replace('_temp.mp4', '.mp4')
            if self._convert_audio_to_aac_hq(temp_file, final_file):
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                return final_file
            else:
                os.rename(temp_file, final_file)
                return final_file
        
        return None

    def _download_with_format(self, url, output_path, format_selector, temp=False):
        """
        Télécharge avec un sélecteur de format spécifique
        """
        filename_template = '%(title)s_temp.%(ext)s' if temp else '%(title)s.%(ext)s'
        
        ydl_opts = {
            'outtmpl': os.path.join(output_path, filename_template),
            'format': format_selector,
            'merge_output_format': 'mp4',
            'prefer_ffmpeg': True,
            'quiet': False,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_file = ydl.prepare_filename(info)
            
            if not downloaded_file.endswith('.mp4'):
                downloaded_file = os.path.splitext(downloaded_file)[0] + '.mp4'
            
            return downloaded_file

    def _download_with_fallback_strategies(self, url, output_path, quality):
        """
        Stratégies de fallback si l'analyse échoue
        """
        strategies = [
            ('Qualité maximale avec AAC', self._download_max_quality_with_aac),
            ('H.264 haute qualité', self._download_h264_high_quality),
            ('Qualité adaptative', self._download_adaptive_quality),
            ('Fallback avec conversion', self._download_and_convert_hq)
        ]
        
        for i, (name, strategy) in enumerate(strategies, 1):
            try:
                print(f"🔄 Essai stratégie fallback {i}/4: {name}...")
                result = strategy(url, output_path, quality)
                if result and os.path.exists(result):
                    print(f"✅ Succès avec stratégie fallback {i}: {name}")
                    return result
            except Exception as e:
                print(f"❌ Stratégie fallback {i} échouée: {e}")
                continue
        
        raise Exception("Toutes les stratégies ont échoué")
        """
        Stratégie 1: Qualité maximale avec audio AAC garantie
        """
        # Sélecteur de format optimisé pour la qualité
        format_selector = self._get_quality_optimized_format_selector(quality)
        
        ydl_opts = {
            'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
            'format': format_selector,
            'merge_output_format': 'mp4',
            'prefer_ffmpeg': True,
            'writesubtitles': False,
            'writeautomaticsub': False,
            'quiet': False,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_file = ydl.prepare_filename(info)
            
            if not downloaded_file.endswith('.mp4'):
                downloaded_file = os.path.splitext(downloaded_file)[0] + '.mp4'
            
            return downloaded_file

    def _download_h264_high_quality(self, url, output_path, quality):
        """
        Stratégie 2: Prioriser H.264 haute qualité
        """
        ydl_opts = {
            'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
            'format': (
                # Prioriser H.264 haute qualité avec AAC
                'bestvideo[vcodec^=avc1][height>=720][fps>=30]+bestaudio[acodec=aac]/'
                'bestvideo[vcodec^=avc1][height>=720]+bestaudio[acodec=aac]/'
                'bestvideo[vcodec^=avc1][height>=480]+bestaudio[acodec=aac]/'
                'bestvideo[vcodec^=avc1]+140/'  # Format AAC 128k
                'bestvideo[ext=mp4][height>=720]+bestaudio[acodec=aac]/'
                'best[vcodec^=avc1][height>=720]'
            ),
            'merge_output_format': 'mp4',
            'prefer_ffmpeg': True,
            'format_sort': ['res:720', 'fps:30', 'vcodec:h264', 'acodec:aac'],
            'quiet': False,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_file = ydl.prepare_filename(info)
            
            if not downloaded_file.endswith('.mp4'):
                downloaded_file = os.path.splitext(downloaded_file)[0] + '.mp4'
            
            return downloaded_file

    def _download_adaptive_quality(self, url, output_path, quality):
        """
        Stratégie 3: Qualité adaptative selon la résolution disponible
        """
        # D'abord, analyser les formats disponibles
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])
            
            # Trouver la meilleure qualité disponible
            best_height = 0
            for fmt in formats:
                if fmt.get('height') and fmt.get('vcodec') != 'none':
                    best_height = max(best_height, fmt.get('height', 0))
            
            print(f"Meilleure résolution disponible: {best_height}p")
        
        # Adapter le format selon la qualité disponible
        if best_height >= 1080:
            target_format = 'bestvideo[height<=1080][vcodec^=avc1]+bestaudio[acodec=aac]'
        elif best_height >= 720:
            target_format = 'bestvideo[height<=720][vcodec^=avc1]+bestaudio[acodec=aac]'
        else:
            target_format = 'bestvideo[vcodec^=avc1]+bestaudio[acodec=aac]'
        
        ydl_opts = {
            'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
            'format': f'{target_format}/bestvideo+bestaudio[acodec=aac]/best[ext=mp4]',
            'merge_output_format': 'mp4',
            'prefer_ffmpeg': True,
            'quiet': False,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_file = ydl.prepare_filename(info)
            
            if not downloaded_file.endswith('.mp4'):
                downloaded_file = os.path.splitext(downloaded_file)[0] + '.mp4'
            
            return downloaded_file

    def _download_and_convert_hq(self, url, output_path):
        """
        Stratégie 4: Téléchargement haute qualité puis conversion audio
        """
        ydl_opts = {
            'outtmpl': os.path.join(output_path, '%(title)s_temp.%(ext)s'),
            'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
            'merge_output_format': 'mp4',
            'prefer_ffmpeg': True,
            'quiet': False,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            temp_file = ydl.prepare_filename(info)
            
            if not temp_file.endswith('.mp4'):
                temp_file = os.path.splitext(temp_file)[0] + '.mp4'
            
            # Conversion avec optimisation qualité
            final_file = temp_file.replace('_temp.mp4', '.mp4')
            success = self._convert_audio_to_aac_hq(temp_file, final_file)
            
            if success and os.path.exists(final_file):
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                return final_file
            else:
                # Fallback: renommer le fichier temporaire
                if os.path.exists(temp_file):
                    os.rename(temp_file, final_file)
                return final_file

    def _get_quality_optimized_format_selector(self, quality):
        """
        Sélecteur de format optimisé selon la qualité demandée
        """
        quality_selectors = {
            'best': (
                # Meilleure qualité disponible
                'bestvideo[vcodec^=avc1][height<=1080][fps>=30]+bestaudio[acodec=aac]/'
                'bestvideo[vcodec^=avc1][height<=1080]+bestaudio[acodec=aac]/'
                'bestvideo[height<=1080]+bestaudio[acodec=aac]/'
                'bestvideo[vcodec^=avc1]+140/'
                'best[vcodec^=avc1][height<=1080]/'
                'best[height<=1080]'
            ),
            '1080p': (
                'bestvideo[height<=1080][vcodec^=avc1][fps>=30]+bestaudio[acodec=aac]/'
                'bestvideo[height<=1080][vcodec^=avc1]+bestaudio[acodec=aac]/'
                'bestvideo[height<=1080]+bestaudio[acodec=aac]/'
                'best[height<=1080]'
            ),
            '720p': (
                'bestvideo[height<=720][vcodec^=avc1][fps>=30]+bestaudio[acodec=aac]/'
                'bestvideo[height<=720][vcodec^=avc1]+bestaudio[acodec=aac]/'
                'bestvideo[height<=720]+bestaudio[acodec=aac]/'
                'best[height<=720]'
            ),
            '480p': (
                'bestvideo[height<=480][vcodec^=avc1]+bestaudio[acodec=aac]/'
                'bestvideo[height<=480]+bestaudio[acodec=aac]/'
                'best[height<=480]'
            )
        }
        
        return quality_selectors.get(quality, quality_selectors['best'])

    def _get_video_quality_info(self, file_path):
        """
        Récupère les informations de qualité vidéo d'un fichier
        """
        if not os.path.exists(file_path):
            return "Fichier introuvable"
        
        try:
            cmd = [
                self._get_ffprobe_path(), '-v', 'quiet', '-print_format', 'json',
                '-show_streams', file_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            import json
            data = json.loads(result.stdout)
            
            video_info = {}
            audio_info = {}
            
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    video_info = {
                        'codec': stream.get('codec_name', 'Unknown'),
                        'width': stream.get('width', 'Unknown'),
                        'height': stream.get('height', 'Unknown'),
                        'fps': stream.get('r_frame_rate', 'Unknown'),
                        'bitrate': stream.get('bit_rate', 'Unknown')
                    }
                elif stream.get('codec_type') == 'audio':
                    audio_info = {
                        'codec': stream.get('codec_name', 'Unknown'),
                        'sample_rate': stream.get('sample_rate', 'Unknown'),
                        'channels': stream.get('channels', 'Unknown')
                    }
            
            return f"Vidéo: {video_info.get('width')}x{video_info.get('height')} {video_info.get('codec')}, Audio: {audio_info.get('codec')}"
            
        except Exception as e:
            return f"Erreur analyse: {e}"

    def _convert_audio_to_aac_hq(self, input_file, output_file):
        """
        Conversion audio vers AAC haute qualité
        """
        cmd = [
            get_fmpeg_path(), '-y', '-i', input_file,
            '-c:v', 'copy',           # Copie la vidéo sans réencodage
            '-c:a', 'aac',            # Force l'audio en AAC
            '-b:a', '256k',           # Bitrate audio plus élevé
            '-ac', '2',               # Stéréo
            '-ar', '48000',           # Fréquence d'échantillonnage plus élevée
            '-movflags', '+faststart', # Optimisation
            '-metadata', 'title=',    # Nettoyer les métadonnées
            output_file
        ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print("✓ Conversion audio HQ vers AAC réussie")
            return True
        except subprocess.CalledProcessError as e:
            print(f"✗ Erreur lors de la conversion: {e}")
            return False

    def download_video_with_specific_quality(self, url, output_path, target_quality='1080p'):
        """
        Télécharge avec une qualité spécifique optimisée
        """
        print(f"Téléchargement en qualité {target_quality}...")
        return self.download_video_with_quality_optimized(url, output_path, target_quality)

    def get_video_analysis(self, url):
        """
        Analyse complète d'une vidéo avant téléchargement
        """
        print("🔍 Analyse complète de la vidéo...")
        
        # Informations générales
        try:
            info = self.get_video_info(url)
            print(f"📹 Titre: {info['title']}")
            print(f"⏱️  Durée: {info['duration']} secondes")
            print(f"👤 Auteur: {info['uploader']}")
        except:
            print("❌ Impossible de récupérer les infos générales")
            
        # Analyse des formats
        formats = self._analyze_available_formats(url)
        if formats:
            print(f"📊 Résolution maximale: {formats['max_height']}p")
            print(f"🎬 H.264 disponible: {'✅' if formats['has_h264'] else '❌'}")
            print(f"🎵 AAC disponible: {'✅' if formats['has_aac'] else '❌'}")
            
            if formats['best_video']:
                bv = formats['best_video']
                print(f"🏆 Meilleur format vidéo: {bv['height']}p {bv['fps']}fps ({bv['vcodec']})")
                
            if formats['best_audio_aac']:
                ba = formats['best_audio_aac']
                print(f"🎧 Meilleur format audio AAC: {ba['abr']}kbps")
            
            # Recommandation
            strategy = self._choose_best_strategy(formats, 'best')
            print(f"💡 Stratégie recommandée: {strategy['name']}")
            print(f"📋 Description: {strategy['description']}")
            
            return {
                'info': info if 'info' in locals() else None,
                'formats': formats,
                'strategy': strategy
            }
        else:
            print("❌ Impossible d'analyser les formats")
            return None

    def get_quality_choices(self, url, media_type='mp3'):
        """
        Retourne une liste des qualités disponibles simplifiée :
        - mp4 : seulement les résolutions (720p, 480p, etc.)
        - mp3 : seulement "Audio MP3"
        """
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])
            choices = []
            
            if media_type == 'mp4':
                # Résolutions standards à proposer
                standard_res = [2160, 1440, 1080, 720, 480, 360, 240]
                seen_resolutions = set()
                
                for res in standard_res:
                    # Cherche le format mp4 correspondant à la résolution
                    best_fmt = None
                    for fmt in formats:
                        if (fmt.get('vcodec') and fmt.get('vcodec') != 'none'
                            and fmt.get('height') == res):
                            if not best_fmt or fmt.get('tbr', 0) > best_fmt.get('tbr', 0):
                                best_fmt = fmt
                    
                    if best_fmt and res not in seen_resolutions:
                        choices.append({
                            'format_id': best_fmt.get('format_id'),
                            'label': f"{res}p",
                            'height': res,
                            'type': 'video'
                        })
                        seen_resolutions.add(res)
                        
            elif media_type == 'mp3':
                # Une seule option pour l'audio MP3
                choices.append({
                    'format_id': 'bestaudio',
                    'label': "Audio MP3",
                    'type': 'audio'
                })
                
            return choices

    # Méthodes existantes conservées pour compatibilité
    def _check_audio_codec(self, file_path):
        """
        Vérifie le codec audio d'un fichier
        """
        if not os.path.exists(file_path):
            return 'unknown'
            
        try:
            cmd = [
                self._get_ffprobe_path(), '-v', 'quiet', '-select_streams', 'a:0',
                '-show_entries', 'stream=codec_name', '-of', 'csv=p=0',
                file_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            codec = result.stdout.strip()
            return codec
        except Exception as e:
            return 'unknown'

    def _verify_aac_audio(self, file_path):
        """
        Vérification que l'audio est bien en AAC
        """
        if not os.path.exists(file_path):
            return False
        
        codec = self._check_audio_codec(file_path)
        aac_variants = ['aac', 'aac_low', 'aac_he', 'aac_he_v2']
        return codec.lower() in aac_variants

    def sanitize_filename(self, filename):
        """
        Nettoie le nom de fichier des caractères invalides
        """
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        if len(filename) > 200:
            filename = filename[:200]
            
        return filename.strip()

    def is_valid_youtube_url(self, url):
        """
        Vérifie si l'URL est une URL YouTube valide
        """
        youtube_patterns = [
            r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=[\w-]+',
            r'(?:https?://)?(?:www\.)?youtu\.be/[\w-]+',
            r'(?:https?://)?(?:www\.)?youtube\.com/embed/[\w-]+',
            r'(?:https?://)?(?:www\.)?youtube\.com/v/[\w-]+',
        ]
        
        for pattern in youtube_patterns:
            if re.match(pattern, url):
                return True
        return False

    def download_with_selected_quality(self, url, output_path, selected_format_id):
        # Cherche le meilleur audio AAC disponible
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])
            best_audio_aac = None
            for fmt in formats:
                if fmt.get('acodec', '').lower() in ['aac', 'mp4a.40.2']:
                    if not best_audio_aac or fmt.get('abr', 0) > best_audio_aac.get('abr', 0):
                        best_audio_aac = fmt
            # Fallback sur m4a si pas d'AAC
            if not best_audio_aac:
                for fmt in formats:
                    if fmt.get('ext', '') == 'm4a':
                        best_audio_aac = fmt
                        break

        # Compose le format_selector
        if best_audio_aac:
            format_selector = f"{selected_format_id}+{best_audio_aac['format_id']}"
        else:
            format_selector = f"{selected_format_id}+bestaudio"

        ydl_opts = {
            'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
            'format': format_selector,
            'merge_output_format': 'mp4',
            'quiet': False,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_file = ydl.prepare_filename(info)
            if not downloaded_file.endswith('.mp4'):
                downloaded_file = os.path.splitext(downloaded_file)[0] + '.mp4'
        # Conversion en AAC si besoin
        output_file = downloaded_file.rsplit('.', 1)[0] + '_aac.mp4'
        convert_to_aac(downloaded_file, output_file)
        return output_file

    def download_with_format_id(self, url, output_path, format_id):
        """
        Télécharge la vidéo avec le format_id choisi + meilleur audio AAC
        """
        ydl_opts = {
            'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
            'format': f"{format_id}+bestaudio[ext=m4a]/bestaudio/best",
            'merge_output_format': 'mp4',
            'quiet': False,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_file = ydl.prepare_filename(info)
            if not downloaded_file.endswith('.mp4'):
                downloaded_file = os.path.splitext(downloaded_file)[0] + '.mp4'
        # Conversion en AAC si besoin
        output_file = downloaded_file.rsplit('.', 1)[0] + '_aac.mp4'
        convert_to_aac(downloaded_file, output_file)
        return output_file