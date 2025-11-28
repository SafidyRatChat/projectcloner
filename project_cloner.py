import os
import zipfile
import shutil
import tempfile
import json
from datetime import datetime
from qgis.PyQt.QtCore import QThread, pyqtSignal
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsRasterLayer,
    QgsLayerDefinition,
    Qgis,
    QgsMessageLog
)
from .project_cloner_dialog import ProjectClonerDialog


def sanitize_filename(name):
    """Sanitize layer name to be a valid filename."""
    return "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in name)


class CloneThread(QThread):
    progress_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, output_path, include_data=True):
        super().__init__()
        self.output_path = output_path
        self.include_data = include_data
        self.temp_dir = None

    def run(self):
        try:
            self.status_updated.emit("Starting project clone...")
            self.temp_dir = tempfile.mkdtemp()
            project = QgsProject.instance()
            project_file = project.fileName()

            if not project_file:
                self.finished_signal.emit(False, "No project file is currently open.")
                return

            # Backup project file
            self.status_updated.emit("Backing up project file...")
            project_backup = os.path.join(self.temp_dir, "project.qgz")
            project.write(project_backup)
            self.progress_updated.emit(10)

            # Collect layers
            layers = project.mapLayers()
            total_layers = len(layers)
            layer_files = []

            for i, layer in enumerate(layers.values(), start=1):
                progress = 10 + (i / total_layers) * 80
                self.progress_updated.emit(int(progress))

                if isinstance(layer, (QgsVectorLayer, QgsRasterLayer)):
                    layer_name = sanitize_filename(layer.name())
                    self.status_updated.emit(f"Processing layer: {layer_name}")

                    source = layer.source()

                    # Copy data files if exists
                    if self.include_data and os.path.isfile(source):
                        dest_file = os.path.join(self.temp_dir, f"{layer_name}{os.path.splitext(source)[1]}")
                        shutil.copy2(source, dest_file)
                        layer_files.append(dest_file)
                        self._copy_associated_files(source, self.temp_dir)

                    # Save layer style (.qml) for all layers
                    style_file = os.path.join(self.temp_dir, f"{layer_name}.qml")
                    layer.saveNamedStyle(style_file)
                    layer_files.append(style_file)

                    # Save layer definition (.qlr) for vector layers if possible
                    if isinstance(layer, QgsVectorLayer):
                        try:
                            layer_def_file = os.path.join(self.temp_dir, f"{layer_name}.qlr")
                            if hasattr(QgsLayerDefinition, "writeLayer"):
                                QgsLayerDefinition.writeLayer(layer, layer_def_file)
                                layer_files.append(layer_def_file)
                        except Exception:
                            # Some versions do not support writeLayer; skip .qlr
                            pass

            # Create ZIP package
            self.status_updated.emit("Creating ZIP package...")
            with zipfile.ZipFile(self.output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(project_backup, "project.qgz")
                for file_path in layer_files:
                    zipf.write(file_path, os.path.basename(file_path))

                # Add metadata
                metadata = {
                    'created': datetime.now().isoformat(),
                    'qgis_version': Qgis.QGIS_VERSION,
                    'layer_count': total_layers,
                    'include_data': self.include_data
                }
                metadata_file = os.path.join(self.temp_dir, "metadata.json")
                with open(metadata_file, 'w') as f:
                    json.dump(metadata, f, indent=2)
                zipf.write(metadata_file, "metadata.json")

            self.progress_updated.emit(100)
            self.status_updated.emit("Clone completed successfully!")
            self.finished_signal.emit(True, f"Project cloned successfully to: {self.output_path}")

        except Exception as e:
            QgsMessageLog.logMessage(str(e), "Project Cloner", Qgis.Critical)
            self.finished_signal.emit(False, f"Error during cloning: {str(e)}")
        finally:
            if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)

    def _copy_associated_files(self, source_file, dest_dir):
        """Copy files associated with main data file (like shapefile components)."""
        base_name = os.path.splitext(os.path.basename(source_file))[0]
        base_dir = os.path.dirname(source_file)

        for f in os.listdir(base_dir):
            if f.startswith(base_name):
                full_path = os.path.join(base_dir, f)
                if os.path.isfile(full_path):
                    shutil.copy2(full_path, dest_dir)


class ProjectCloner:
    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.clone_thread = None

    def initGui(self):
        self.action = QAction("Project Cloner", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu("Project Tools", self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        self.iface.removePluginMenu("Project Tools", self.action)
        self.iface.removeToolBarIcon(self.action)
        if self.dialog:
            self.dialog.close()

    def run(self):
        if not self.dialog:
            self.dialog = ProjectClonerDialog()
            self.dialog.clone_button.clicked.connect(self.start_clone)

        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

    def start_clone(self):
        output_path = self.dialog.output_path_edit.text()
        include_data = self.dialog.include_data_check.isChecked()

        if not output_path:
            QMessageBox.warning(self.dialog, "Warning", "Please select output path.")
            return

        self.dialog.clone_button.setEnabled(False)
        self.dialog.progress_bar.setValue(0)
        self.dialog.status_label.setText("Starting...")

        self.clone_thread = CloneThread(output_path, include_data)
        self.clone_thread.progress_updated.connect(self.dialog.progress_bar.setValue)
        self.clone_thread.status_updated.connect(self.dialog.status_label.setText)
        self.clone_thread.finished_signal.connect(self.clone_finished)
        self.clone_thread.start()

    def clone_finished(self, success, message):
        self.dialog.clone_button.setEnabled(True)
        if success:
            QMessageBox.information(self.dialog, "Success", message)
            self.dialog.progress_bar.setValue(100)
        else:
            QMessageBox.critical(self.dialog, "Error", message)
            self.dialog.progress_bar.setValue(0)
        self.clone_thread = None
