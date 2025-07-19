#!/usr/bin/env python3
"""
YouTube to MP3/MP4 Converter
"""

import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from ui.main_window import MainWindow


def main():
    """Fonction principale"""
    # Configuration de l'application
    app = QApplication(sys.argv)
    app.setApplicationName("YouTube Converter")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("YTConverter")

        # Style clair moderne
    app.setStyleSheet("""
        QMainWindow {
            background-color: #f5f5f5;
            color: #000000;
        }
        QPushButton {
            background-color: #e0e0e0;
            border: 1px solid #b0b0b0;
            border-radius: 5px;
            padding: 8px 16px;
            color: #000000;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #d5d5d5;
        }
        QPushButton:pressed {
            background-color: #c0c0c0;
        }
        QPushButton:disabled {
            background-color: #f0f0f0;
            color: #a0a0a0;
        }
        QLineEdit {
            background-color: #ffffff;
            border: 1px solid #cccccc;
            border-radius: 3px;
            padding: 5px;
            color: #000000;
        }
        QLineEdit:focus {
            border: 2px solid #0078d4;
        }
        QComboBox {
            background-color: #ffffff;
            border: 1px solid #cccccc;
            border-radius: 3px;
            padding: 5px;
            color: #000000;
        }
        QComboBox::drop-down {
            border: none;
        }
        QComboBox::down-arrow {
            image: none;
            border-width: 5px;
            border-style: solid;
            border-color: #666666 transparent transparent transparent;
        }
        QProgressBar {
            border: 1px solid #cccccc;
            border-radius: 3px;
            text-align: center;
            background-color: #eeeeee;
        }
        QProgressBar::chunk {
            background-color: #0078d4;
            border-radius: 2px;
        }
        QLabel, QLabel * {
            color: #000000;
        }
        QTextEdit {
            background-color: #ffffff;
            border: 1px solid #cccccc;
            border-radius: 3px;
            color: #000000;
        }
        QListWidget {
            background-color: #ffffff;
            border: 1px solid #cccccc;
            border-radius: 3px;
            color: #000000;
        }
        QListWidget::item {
            padding: 5px;
            border-bottom: 1px solid #dddddd;
        }
        QListWidget::item:selected {
            background-color: #cde6f7;
        }
    """)
    
    # Création et affichage de la fenêtre principale
    window = MainWindow()
    window.show()
    
    # Boucle d'événements
    sys.exit(app.exec())

if __name__ == "__main__":
    main()