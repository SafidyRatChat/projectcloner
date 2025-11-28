import os
import json
import urllib.request
from datetime import datetime

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QCheckBox, QProgressBar, QFileDialog, QGroupBox, QMessageBox
)
from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsProject


# ================================
#  IP COUNTRY CHECK FUNCTION
# ================================
def get_user_country():
    try:
        with urllib.request.urlopen("https://ipapi.co/json/") as url:
            data = json.loads(url.read().decode())
            return data.get("country_name", "")
    except:
        return ""


# ================================
#  MAIN DIALOG CLASS
# ================================
class ProjectClonerDialog(QDialog):
    
    def __init__(self):
        super().__init__()
        self.init_ui()

        # Show Malagasy greeting if user is located in Madagascar
        country = get_user_country()
        if country.lower() == "madagascar":
            QMessageBox.information(
                self,
                "Tongasoa",
                "Tongasoa e! Mazotoa mampiasa — mirary tontolo finaritra!"
            )


    def init_ui(self):
        self.setWindowTitle("Project Cloner")
        self.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), "icon.png")))
        self.setMinimumWidth(500)
        
        layout = QVBoxLayout()
        
        # ================================
        # Output Folder
        # ================================
        path_group = QGroupBox("Output Location")
        path_layout = QVBoxLayout()
        path_edit_layout = QHBoxLayout()
        
        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("Select where to save the cloned project...")
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self.browse_output_path)
        
        path_edit_layout.addWidget(self.output_path_edit)
        path_edit_layout.addWidget(browse_button)
        path_layout.addLayout(path_edit_layout)
        path_group.setLayout(path_layout)
        layout.addWidget(path_group)
        
        # ================================
        # Clone options
        # ================================
        options_group = QGroupBox("Clone Options")
        options_layout = QVBoxLayout()
        
        self.include_data_check = QCheckBox("Include layer data files (shapefiles, geotiffs, etc.)")
        self.include_data_check.setChecked(True)
        options_layout.addWidget(self.include_data_check)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # ================================
        # Progress area
        # ================================
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("Ready to clone project")
        progress_layout.addWidget(self.status_label)
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)
        
        # ================================
        # Buttons
        # ================================
        button_layout = QHBoxLayout()
        self.clone_button = QPushButton("Clone Project")
        self.clone_button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; }")
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        
        button_layout.addWidget(self.clone_button)
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        self.set_default_output_path()


    # ================================
    # Set Auto Output Name
    # ================================
    def set_default_output_path(self):
        project = QgsProject.instance()
        project_file = project.fileName()
        
        if project_file:
            base = os.path.splitext(os.path.basename(project_file))[0]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            name = f"{base}_clone_{timestamp}.zip"
            
            desktop = os.path.expanduser("~/Desktop")
            default = os.path.join(desktop, name) if os.path.exists(desktop) else os.path.expanduser(f"~/{name}")
            self.output_path_edit.setText(default)


    # ================================
    # Browse output file
    # ================================
    def browse_output_path(self):
        default = self.output_path_edit.text() or os.path.expanduser("~")
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Project Clone As", default, "ZIP Files (*.zip)"
        )
        
        if file_path:
            if not file_path.lower().endswith('.zip'):
                file_path += '.zip'
            self.output_path_edit.setText(file_path)
