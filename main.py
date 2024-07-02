import sys
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, QFileDialog, QComboBox, QCheckBox, QMessageBox, QTabWidget, QColorDialog
from PyQt6.QtCore import QObject, pyqtSignal, QThread
import pathlib
import time

# import from snapshotter.py
from snapshotter import (
    get_world_names, get_map_names, create_snapshot, save_snapshot,
    post_to_discord_webhook, is_discord_available
)

class SnapshotWorker(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, tiles_dir, world_name, map_name, scale, fixed_tile_size, color_hex, webhook_url, message):
        super().__init__()
        self.tiles_dir = tiles_dir
        self.world_name = world_name
        self.map_name = map_name
        self.scale = scale
        self.fixed_tile_size = fixed_tile_size
        self.color_hex = color_hex
        self.webhook_url = webhook_url
        self.message = message

    def run(self):
        try:
            snapshot = create_snapshot(self.tiles_dir, self.world_name, self.map_name, self.scale, self.fixed_tile_size, self.color_hex)
            snapshot_path = save_snapshot(snapshot, self.world_name, self.map_name)
            
            snapshot_path_str = str(snapshot_path)

            if self.webhook_url:
                if is_discord_available:
                    post_to_discord_webhook(snapshot_path_str, self.webhook_url, self.message)
                else:
                    self.error.emit("Unable to post to Discord. Ensure the 'discord' package is installed.")

            self.finished.emit(snapshot_path_str)
        except Exception as e:
            self.error.emit(str(e))

class AutoSnapshotWorker(QObject):
    finished = pyqtSignal()
    create_snapshot = pyqtSignal()

    def __init__(self, interval):
        super().__init__()
        self.interval = interval
        self.is_running = True

    def run(self):
        while self.is_running:
            self.create_snapshot.emit()
            time.sleep(self.interval)
        self.finished.emit()

class SnapshotGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.worker = None
        self.thread = None

    def initUI(self):
        self.setWindowTitle('Dynmap Snapshotter')
        main_layout = QVBoxLayout()
        self.tab_widget = QTabWidget()
        
        # create tabs
        self.snapshot_tab = QWidget()
        self.settings_tab = QWidget()
        
        self.tab_widget.addTab(self.snapshot_tab, "Snapshot")
        self.tab_widget.addTab(self.settings_tab, "Settings")

        # set up each tab
        self.setup_snapshot_tab()
        self.setup_settings_tab()

        main_layout.addWidget(self.tab_widget)
        self.setLayout(main_layout)
        self.resize(400, 300)

        # initialize ui
        self.toggle_resize_options()
        self.update_worlds()
        self.toggle_snaps_options()

    def setup_snapshot_tab(self):
        layout = QVBoxLayout()

        # folder selection
        folder_layout = QHBoxLayout()
        self.folder_input = QLineEdit()
        folder_button = QPushButton('Browse')
        folder_button.clicked.connect(self.browse_folder)
        folder_layout.addWidget(QLabel('Tiles Directory:'))
        folder_layout.addWidget(self.folder_input)
        folder_layout.addWidget(folder_button)
        layout.addLayout(folder_layout)

        # world selection
        self.world_combo = QComboBox()
        self.world_combo.currentTextChanged.connect(self.update_maps)
        layout.addWidget(QLabel('World:'))
        layout.addWidget(self.world_combo)

        # map selection
        self.map_combo = QComboBox()
        layout.addWidget(QLabel('Map:'))
        layout.addWidget(self.map_combo)

        # snapshot buttons
        self.create_button = QPushButton('Create Snapshot')
        self.create_button.clicked.connect(self.create_snapshot)
        self.start_auto_button = QPushButton('Start Auto Snapshots')
        self.start_auto_button.clicked.connect(self.start_auto_snapshots)
        self.start_auto_button.hide()
        
        # Add both buttons to the layout
        layout.addWidget(self.create_button)
        layout.addWidget(self.start_auto_button)

        self.snapshot_tab.setLayout(layout)

    def setup_settings_tab(self):
        layout = QVBoxLayout()

        # resize options
        self.resize_check = QCheckBox('Resize output')
        self.resize_check.stateChanged.connect(self.toggle_resize_options)
        layout.addWidget(self.resize_check)

        resize_layout = QHBoxLayout()
        self.scale_input = QLineEdit()
        self.scale_input.setPlaceholderText('Scale (e.g., 0.5)')
        self.tile_size_input = QLineEdit()
        self.tile_size_input.setPlaceholderText('Tile size (e.g., 64)')
        resize_layout.addWidget(self.scale_input)
        resize_layout.addWidget(self.tile_size_input)
        layout.addLayout(resize_layout)

        # auto snapshots
        self.auto_snaps_input = QLineEdit()
        self.auto_snaps_input.setPlaceholderText('Interval (Minutes)')
        auto_snapshot_layout = QHBoxLayout()
        self.toggle_auto_snaps = QCheckBox('Enable automatic snapshots')

        self.toggle_auto_snaps.stateChanged.connect(self.toggle_snaps_options)

        auto_snapshot_layout.addWidget(self.toggle_auto_snaps)
        auto_snapshot_layout.addWidget(self.auto_snaps_input)
        layout.addLayout(auto_snapshot_layout)

        # background color
        color_layout = QHBoxLayout()
        self.color_check = QCheckBox('Apply background color')
        self.color_button = QPushButton('Choose Color')
        self.color_button.clicked.connect(self.open_color_dialog)
        self.selected_color = None
        color_layout.addWidget(self.color_check)
        color_layout.addWidget(self.color_button)
        layout.addLayout(color_layout)

        # discord options
        self.toggle_discord = QCheckBox('Post to Discord')
        layout.addWidget(self.toggle_discord)
        discord_layout = QVBoxLayout()
        self.webhook_input = QLineEdit()
        self.webhook_input.setPlaceholderText('Discord Webhook URL')
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText('Discord message')
        discord_layout.addWidget(self.webhook_input)
        discord_layout.addWidget(self.message_input)
        self.toggle_discord.stateChanged.connect(self.toggle_discord_options)
        layout.addLayout(discord_layout)

        self.settings_tab.setLayout(layout)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Dynmap Tiles Directory")
        if folder:
            self.folder_input.setText(folder)
            self.update_worlds()

    def update_worlds(self):
        tiles_dir = self.folder_input.text()
        if tiles_dir:
            world_names = get_world_names(pathlib.Path(tiles_dir))
            self.world_combo.clear()
            self.world_combo.addItems(world_names)

    def update_maps(self):
        tiles_dir = self.folder_input.text()
        world_name = self.world_combo.currentText()
        if tiles_dir and world_name:
            map_names = get_map_names(pathlib.Path(tiles_dir), world_name)
            self.map_combo.clear()
            self.map_combo.addItems(map_names)

    def toggle_resize_options(self):
        enabled = self.resize_check.isChecked()
        self.scale_input.setEnabled(enabled)
        self.tile_size_input.setEnabled(enabled)

    def open_color_dialog(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.selected_color = color
            self.color_button.setStyleSheet(f'background-color: {color.name()};')

    def toggle_discord_options(self):
        enabled = self.toggle_discord.isChecked()
        self.webhook_input.setEnabled(enabled)
        self.message_input.setEnabled(enabled)

    def toggle_snaps_options(self):
        enabled = self.toggle_auto_snaps.isChecked()
        self.auto_snaps_input.setEnabled(enabled)
        
        if enabled:
            self.create_button.hide()
            self.start_auto_button.show()
        else:
            self.create_button.show()
            self.start_auto_button.hide()

    def start_auto_snapshots(self):
        interval = float(self.auto_snaps_input.text()) * 60
        self.worker = AutoSnapshotWorker(interval)
        self.thread = QThread()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.worker.create_snapshot.connect(self.create_snapshot)

        self.thread.start()

        self.start_auto_button.setText("Stop Auto Snapshots")
        self.start_auto_button.clicked.disconnect()
        self.start_auto_button.clicked.connect(self.stop_auto_snapshots)

    def stop_auto_snapshots(self):
        if self.worker:
            self.worker.is_running = False
            self.thread.quit()
            self.thread.wait()
            self.worker = None
            self.thread = None

        self.start_auto_button.setText("Start Auto Snapshots")
        self.start_auto_button.clicked.disconnect()
        self.start_auto_button.clicked.connect(self.start_auto_snapshots)

    def create_snapshot(self):
        tiles_dir = self.folder_input.text()
        world_name = self.world_combo.currentText()
        map_name = self.map_combo.currentText()

        if not (tiles_dir and world_name and map_name):
            QMessageBox.warning(self, "Missing Information", "Please fill in all required fields.")
            return

        scale = float(self.scale_input.text()) if self.scale_input.text() and self.resize_check.isChecked() else None
        fixed_tile_size = int(self.tile_size_input.text()) if self.tile_size_input.text() and self.resize_check.isChecked() else None

        color_hex = self.selected_color.name() if self.color_check.isChecked() and self.selected_color else None

        webhook_url = self.webhook_input.text() if self.toggle_discord.isChecked() else None
        message = self.message_input.text() if self.toggle_discord.isChecked() else None

        self.snapshot_thread = QThread()
        self.snapshot_worker = SnapshotWorker(tiles_dir, world_name, map_name, scale, fixed_tile_size, color_hex, webhook_url, message)
        self.snapshot_worker.moveToThread(self.snapshot_thread)
        self.snapshot_thread.started.connect(self.snapshot_worker.run)
        self.snapshot_worker.finished.connect(self.snapshot_thread.quit)
        self.snapshot_worker.finished.connect(self.snapshot_worker.deleteLater)
        self.snapshot_thread.finished.connect(self.snapshot_thread.deleteLater)
        self.snapshot_worker.finished.connect(self.snapshot_success)
        self.snapshot_worker.error.connect(self.snapshot_error)

        self.snapshot_thread.start()

    def snapshot_success(self, snapshot_path):
        QMessageBox.information(self, "Success", f"Snapshot created and saved to:\n{snapshot_path}")

    def snapshot_error(self, error_message):
        QMessageBox.critical(self, "Error", f"An error has occurred: {error_message}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = SnapshotGUI()
    ex.show()
    sys.exit(app.exec())
