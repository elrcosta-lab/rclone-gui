from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QWidget


def apply_theme(widget: QWidget):
    palette = widget.palette()
    palette.setColor(QPalette.Window, QColor("#1e1e2e"))
    palette.setColor(QPalette.WindowText, QColor("#cdd6f4"))
    palette.setColor(QPalette.Base, QColor("#181825"))
    palette.setColor(QPalette.AlternateBase, QColor("#313244"))
    palette.setColor(QPalette.ToolTipBase, QColor("#45475a"))
    palette.setColor(QPalette.ToolTipText, QColor("#cdd6f4"))
    palette.setColor(QPalette.Text, QColor("#cdd6f4"))
    palette.setColor(QPalette.Button, QColor("#313244"))
    palette.setColor(QPalette.ButtonText, QColor("#cdd6f4"))
    palette.setColor(QPalette.BrightText, QColor("#f38ba8"))
    palette.setColor(QPalette.Highlight, QColor("#89b4fa"))
    palette.setColor(QPalette.HighlightedText, QColor("#1e1e2e"))
    widget.setPalette(palette)

    widget.setStyleSheet("""
        QToolTip { background-color: #45475a; color: #cdd6f4; border: 1px solid #585b70; }
        QMenu { background-color: #1e1e2e; color: #cdd6f4; border: 1px solid #313244; }
        QMenu::item:selected { background-color: #313244; }
        QLineEdit { background-color: #313244; color: #cdd6f4; border: 1px solid #45475a;
                     border-radius: 4px; padding: 4px; }
        QTextEdit { background-color: #181825; color: #cdd6f4; border: 1px solid #313244;
                     border-radius: 4px; }
        QPushButton { background-color: #89b4fa; color: #1e1e2e; border-radius: 4px;
                       padding: 6px 16px; font-weight: bold; }
        QPushButton:hover { background-color: #74c7ec; }
        QPushButton:pressed { background-color: #89dceb; }
        QPushButton:disabled { background-color: #45475a; color: #6c7086; }
        QTreeView { background-color: #1e1e2e; color: #cdd6f4; border: 1px solid #313244;
                     border-radius: 4px; }
        QTreeView::item:selected { background-color: #313244; color: #89b4fa; }
        QTreeView::item:hover { background-color: #313244; }
        QHeaderView::section { background-color: #181825; color: #a6adc8; padding: 4px;
                                border: none; border-bottom: 1px solid #313244; }
        QTabWidget::pane { border: 1px solid #313244; background-color: #1e1e2e; }
        QTabBar::tab { background-color: #181825; color: #6c7086; padding: 8px 16px;
                        border: none; }
        QTabBar::tab:selected { background-color: #1e1e2e; color: #89b4fa; border-bottom: 2px solid #89b4fa; }
        QGroupBox { border: 1px solid #313244; border-radius: 4px; margin-top: 8px;
                     padding-top: 16px; }
        QGroupBox::title { subcontrol-origin: margin; left: 8px; }
        QStatusBar { background-color: #181825; color: #a6adc8; }
        QSplitter::handle { background-color: #313244; }
    """)
