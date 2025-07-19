import subprocess
import sys
import os

def check_ffmpeg():
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("ffmpeg est installé !")
            print(result.stdout.splitlines()[0])
            return True
        else:
            print("ffmpeg n'est pas installé ou pas dans le PATH.")
            return False
    except FileNotFoundError:
        print("ffmpeg n'est pas installé ou pas dans le PATH.")
        return False

def get_fmpeg_path():
    """Retourne le chemin absolu vers ffmpeg.exe, même dans l'exécutable PyInstaller."""
    if getattr(sys, 'frozen', False):
        # Mode exécutable (PyInstaller)
        base_path = sys._MEIPASS
    else:
        # Mode développement
        base_path = os.path.dirname(__file__)
    return os.path.join(base_path, "ffmpeg", "ffmpeg.exe")