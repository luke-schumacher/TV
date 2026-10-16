"""Native setup/settings UI; mpv retains its own proven playback window."""
from __future__ import annotations
import copy
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog,
    QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton,
    QSpinBox, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from .app import TVApp
from .channel import build_lineup
from .config import ConfigError, config_from_dict
from .library import LibraryService, stable_config
from .profiles import DESKTOP
from .settings import SettingsDraft, validate_document
from .playback_state import default_state_path
from .storage import write_json

STYLE = '''
QWidget { background:#111720; color:#edf1f7; font-size:14px; }
QDialog { background:#111720; }
QLabel#heading { font-size:28px; font-weight:600; }
QLabel#subheading { color:#aab9cc; }
QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox,QTableWidget { background:#1c2633; border:1px solid #52657c; border-radius:5px; padding:7px; }
QPushButton { background:#26374b; border:1px solid #617995; border-radius:6px; padding:9px 16px; }
QPushButton:focus,QLineEdit:focus,QComboBox:focus { border:2px solid #8ac8ff; }
QPushButton#primary { background:#a7d5ff; color:#102030; font-weight:600; }
QPushButton:disabled { color:#7b8798; background:#25303f; }
QTabBar::tab { padding:12px 18px; } QTabBar::tab:selected { border-bottom:3px solid #a7d5ff; }
QHeaderView::section { background:#26374b; padding:8px; }
QTableWidget::item:selected { background:#35567a; }
QCheckBox { padding:6px; } QCheckBox::indicator { width:20px; height:20px; border:1px solid #8da6c4; border-radius:3px; background:#1c2633; }
QCheckBox::indicator:checked { background:#a7d5ff; border:2px solid #edf1f7; }
'''


def application():
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName('TV')
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(STYLE)
    return app


class SettingsDialog(QDialog):
    """A draft is isolated until a successful scan and atomic Save/Watch."""
    def __init__(self, path, *, first_run=False, on_saved=None, on_preview=None, cache=None):
        super().__init__()
        self.setWindowTitle('TV · Choose your channels' if first_run else 'TV · Settings')
        self.resize(1000, 690)
        self.first_run = first_run
        self.draft = SettingsDraft(Path(path))
        self.on_saved = on_saved
        self.on_preview = on_preview
        self.cache = cache
        self.prepared = None
        self.future = None
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='tv-settings')
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self._poll)
        raw = self.draft.data
        if raw:
            validate_document(raw, self.draft.path, require_media=False)
        if not raw:
            self.draft.update({'media_root': str(Path.home() / 'Movies' / 'TV'), 'prefer_usb': False,
                'start_offset': 0, 'tune_in': 'resume', 'volume_control': 'pi',
                'power_off_on_min_volume': False, 'ui': {'theme': 'modern'}})
            raw = self.draft.data
        layout = QVBoxLayout(self)
        heading = QLabel('Make yourself at home' if first_run else 'Your TV, your way')
        heading.setObjectName('heading')
        layout.addWidget(heading)
        sub = QLabel('Choose a library, review your channels, then watch.' if first_run else 'Your show keeps playing while you adjust settings.')
        sub.setObjectName('subheading')
        layout.addWidget(sub)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        library = QWidget()
        form = QFormLayout(library)
        loaded = config_from_dict(raw, base_dir=self.draft.path.parent)
        self.root = QLineEdit(str(loaded.media_root or ""))
        self.root.setAccessibleName('Library folder')
        browse = QPushButton('Choose folder…')
        browse.clicked.connect(self.choose_folder)
        row = QHBoxLayout()
        row.addWidget(self.root, 1)
        row.addWidget(browse)
        form.addRow('Library folder', row)
        explanation = QLabel('One folder per show. The folder name becomes its channel name.\nExample: TV / Arthur / S01E01.mp4')
        explanation.setWordWrap(True)
        form.addRow(explanation)
        self.review = QPushButton('Review channels')
        self.review.clicked.connect(lambda: self.prepare(save=False))
        form.addRow(self.review)
        self.summary = QLabel('Choose a library to see its channels.' if first_run else 'Save validates the library before applying changes.')
        self.summary.setWordWrap(True)
        form.addRow(self.summary)
        self.tabs.addTab(library, 'Library')

        channels = QWidget()
        cl = QVBoxLayout(channels)
        self.custom = QCheckBox('Customize channel names, numbers and playback order')
        self.custom.setChecked(bool(raw.get('channels')))
        self.custom.toggled.connect(lambda checked: self.table.setEnabled(checked))
        cl.addWidget(self.custom)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(['Number', 'Name', 'Show folder', 'Order', 'Exclude patterns', 'Exclude seasons'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setAccessibleName('Channels')
        cl.addWidget(self.table, 1)
        actions = QHBoxLayout()
        add = QPushButton('Add show folder…')
        add.clicked.connect(self.add_channel)
        remove = QPushButton('Remove selected channel')
        remove.clicked.connect(self.remove_channel)
        actions.addWidget(add)
        actions.addWidget(remove)
        cl.addLayout(actions)
        cl.addWidget(QLabel('Order: shuffle or in_order. Separate exclusions with semicolons; seasons: 1; 3-5.'))
        entries = copy.deepcopy(raw.get("channels", []))
        for entry, channel in zip(entries, loaded.channels):
            entry["path"] = str(channel.path.resolve())
            entry["order"] = channel.order
        self.fill_channels(entries)
        self.table.setEnabled(self.custom.isChecked())
        self.tabs.addTab(channels, 'Channels')

        watching = QWidget()
        wf = QFormLayout(watching)
        self.tune = QComboBox()
        self.tune.addItems(['resume', 'random', 'broadcast'])
        self.tune.setCurrentText(raw.get('tune_in', 'resume'))
        wf.addRow('When tuning in', self.tune)
        self.order = QComboBox()
        self.order.addItems(['shuffle', 'in_order'])
        self.order.setCurrentText(raw.get('order', 'shuffle'))
        wf.addRow('Default episode order', self.order)
        self.volume = QSpinBox()
        self.volume.setRange(0, 100)
        self.volume.setValue(raw.get('initial_volume', 70))
        wf.addRow('Startup volume', self.volume)
        self.audio = QComboBox()
        self.audio.setEditable(True)
        self.audio.addItem('auto')
        self.audio.setCurrentText(raw.get('audio_device') or 'auto')
        wf.addRow('Audio output', self.audio)
        self.theme = QComboBox()
        self.theme.addItems(['modern', 'crt'])
        self.theme.setCurrentText(raw.get('ui', {}).get('theme', 'crt'))
        wf.addRow('Appearance', self.theme)
        self.scale = QDoubleSpinBox()
        self.scale.setRange(.75, 1.5)
        self.scale.setSingleStep(.1)
        self.scale.setValue(raw.get('ui', {}).get('scale', 1))
        wf.addRow('Text size', self.scale)
        self.contrast = QCheckBox('High contrast text')
        self.contrast.setChecked(raw.get('ui', {}).get('high_contrast', False))
        wf.addRow(self.contrast)
        self.motion = QCheckBox('Reduce motion and turn off CRT distortion')
        self.motion.setChecked(raw.get('ui', {}).get('reduced_motion', False))
        wf.addRow(self.motion)
        preview = QPushButton('Preview appearance')
        preview.setEnabled(on_preview is not None)
        preview.clicked.connect(self.preview)
        wf.addRow(preview)
        self.tabs.addTab(watching, 'Watching')

        advanced = QWidget()
        af = QFormLayout(advanced)
        self.recursive = QCheckBox('Include season subfolders')
        self.recursive.setChecked(raw.get('scan_recursive', True))
        af.addRow(self.recursive)
        self.force43 = QCheckBox('Fit every show inside a 4:3 frame')
        self.force43.setChecked(raw.get('force_4_3', False))
        af.addRow(self.force43)
        self.diagnostics = QLabel('Desktop playback · Software volume · Host shutdown disabled')
        self.diagnostics.setWordWrap(True)
        af.addRow(self.diagnostics)
        af.addRow(QLabel('G: guide   S: settings   F: fullscreen   Q: quit'))
        self.tabs.addTab(advanced, 'Advanced')
        self.status = QLabel('')
        self.status.setWordWrap(True)
        self.status.setAccessibleName('Settings status')
        layout.addWidget(self.status)
        buttons = QHBoxLayout()
        cancel = QPushButton('Cancel')
        cancel.clicked.connect(self.reject)
        self.cancel_button = cancel
        self.save_button = QPushButton('Watch' if first_run else 'Save changes')
        self.save_button.setObjectName('primary')
        self.save_button.clicked.connect(lambda: self.prepare(save=True))
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(self.save_button)
        layout.addLayout(buttons)

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, 'Choose your TV library', self.root.text())
        if folder:
            self.root.setText(folder)

    def fill_channels(self, entries):
        self.table.setRowCount(0)
        for entry in entries:
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = [str(entry.get('number', row + 2)), entry.get('name') or Path(entry['path']).name,
                str(entry['path']), entry.get('order', 'shuffle'),
                '; '.join(entry.get('exclude', [])) if isinstance(entry.get('exclude', []), list) else entry.get('exclude', ''),
                '; '.join(map(str, entry.get('exclude_seasons', []))) if isinstance(entry.get('exclude_seasons', []), list) else str(entry.get('exclude_seasons', ''))]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, copy.deepcopy(entry))

    def add_channel(self):
        folder = QFileDialog.getExistingDirectory(self, 'Choose one show folder', self.root.text())
        if folder:
            entries = self.channel_entries()
            used = {int(x['number']) for x in entries}
            number = 2
            while number in used:
                number += 1
            entries.append({'number': number, 'name': Path(folder).name, 'path': folder})
            self.fill_channels(entries)
            self.custom.setChecked(True)

    def remove_channel(self):
        row = self.table.currentRow()
        if row >= 0:
            self.custom.setChecked(True)
            self.table.removeRow(row)

    def channel_entries(self):
        result = []
        for row in range(self.table.rowCount()):
            values = [self.table.item(row, c).text().strip() for c in range(6)]
            entry = copy.deepcopy(self.table.item(row, 0).data(Qt.ItemDataRole.UserRole) or {})
            entry.update(number=int(values[0]), name=values[1], path=str(Path(values[2]).expanduser().resolve()),
                order=values[3], exclude=[x.strip() for x in values[4].split(';') if x.strip()],
                exclude_seasons=[x.strip() for x in values[5].split(';') if x.strip()])
            result.append(entry)
        return result

    def collect(self):
        if self.custom.isChecked() and self.table.rowCount() == 0:
            raise ConfigError("Add at least one channel or turn off custom channels.")
        if not self.root.text().strip() and not self.custom.isChecked():
            raise ConfigError('Choose a library folder first.')
        self.draft.update({'media_root': str(Path(self.root.text()).expanduser().resolve()),
            'prefer_usb': False, 'channels': self.channel_entries() if self.custom.isChecked() else [],
            'tune_in': self.tune.currentText(), 'order': self.order.currentText(),
            'initial_volume': self.volume.value(), 'audio_device': self.audio.currentText() or 'auto',
            'scan_recursive': self.recursive.isChecked(), 'force_4_3': self.force43.isChecked(),
            'ui': {'theme': self.theme.currentText(), 'scale': self.scale.value(),
                   'high_contrast': self.contrast.isChecked(), 'reduced_motion': self.motion.isChecked()},
            'power_off_on_min_volume': False, 'volume_control': 'pi'})
        return self.draft.data

    def preview(self):
        try:
            config = config_from_dict(self.collect(), base_dir=self.draft.path.parent)
            self.on_preview(config)
            self.status.setText('Previewing. Cancel restores your saved appearance.')
        except (ConfigError, ValueError, RuntimeError, OSError) as exc:
            self.status.setText(str(exc))

    def prepare(self, *, save):
        if self.future is not None:
            return
        try:
            raw = copy.deepcopy(self.collect())
            validate_document(raw, self.draft.path)
        except (ConfigError, ValueError, RuntimeError, OSError) as exc:
            self.status.setText(str(exc))
            return
        self._saving = save
        self.status.setText('Checking your library…')
        self.tabs.setEnabled(False)
        self.save_button.setEnabled(False)
        def scan():
            cfg = validate_document(raw, self.draft.path)
            cfg = stable_config(cfg)
            lineup = build_lineup(cfg, duration_lookup=self.cache.get if self.cache else (lambda p: None))
            if not any(ch.episodes for ch in lineup):
                raise ConfigError('No videos found. Put videos inside one subfolder per show, then try again.')
            return cfg, lineup
        self.future = self.executor.submit(scan)
        self.timer.start()

    def _poll(self):
        if self.future is None or not self.future.done():
            return
        self.timer.stop()
        self.tabs.setEnabled(True)
        self.save_button.setEnabled(True)
        future, self.future = self.future, None
        try:
            self.prepared = future.result()
            cfg, lineup = self.prepared
            self.summary.setText(f'{len(lineup)} channels · {sum(len(ch.episodes) for ch in lineup)} episodes')
            if not self.custom.isChecked():
                self.fill_channels([{'number': ch.number, 'name': ch.name, 'path': str(ch.config.path), 'order': ch.config.order} for ch in lineup])
            if self._saving:
                self.draft.save()
                if self.on_saved:
                    self.on_saved(cfg, lineup)
                self.accept()
            else:
                self.status.setText('Channels are ready. Open Channels to review them, or choose Watch.')
                self.tabs.setCurrentIndex(1)
        except (ConfigError, ValueError, RuntimeError, OSError) as exc:
            self.status.setText(str(exc))

    def done(self, result):
        self.timer.stop()
        self.executor.shutdown(wait=False, cancel_futures=True)
        super().done(result)


class DesktopSession:
    def __init__(self, path, *, fullscreen=False):
        self.qt = application()
        self.path = Path(path)
        self.fullscreen = fullscreen
        self.service = LibraryService()
        self.tv = None
        self._shutdown = False
        self.dialog = None
        self.future = None
        self.warming = []
        self.error = None
        self._signature = None
        self._ticks = 0
        self.timer = QTimer()
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.tick)

    def show_settings(self, *, first_run=False):
        if self.dialog and self.dialog.isVisible():
            self.dialog.raise_()
            self.dialog.activateWindow()
            return
        try:
            dialog = SettingsDialog(self.path, first_run=first_run, on_saved=self.apply,
                on_preview=self.preview if self.tv else None, cache=self.service.cache)
        except (ConfigError, OSError) as exc:
            # Keep the damaged original intact; recovery uses a separately named config.
            self.path = self.path.with_name(self.path.stem + '.recovered.yaml')
            dialog = SettingsDialog(self.path, first_run=True, on_saved=self.apply, cache=self.service.cache)
            dialog.status.setText(f'{exc}. Save will create {self.path.name}; the original is preserved.')
        self.dialog = dialog
        if self.tv:
            for dev in getattr(self.tv.player, 'audio_devices', lambda: [])():
                if dev.get('name') and dialog.audio.findText(dev['name']) < 0:
                    dialog.audio.addItem(dev['name'])
        dialog.finished.connect(self.dialog_closed)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def preview(self, config):
        if self.tv:
            self.tv.player.apply_appearance(config)
            self.tv.overlay.clear_all()
            from .overlay import OverlayManager
            self.tv.overlay = OverlayManager(self.tv.player, config)
            self.tv._show_info()

    def dialog_closed(self, result):
        if result == QDialog.DialogCode.Rejected:
            if self.tv:
                self.preview(self.tv.config)
            else:
                self.qt.quit()

    def apply(self, config, lineup):
        if self.tv:
            self.tv.apply_config(config, lineup)
            self.tv.player.apply_appearance(self.tv.config)
        else:
            self.tv = TVApp.from_config(config, desktop=True, fullscreen=self.fullscreen, lineup=lineup)
            self.tv.on_settings = self.show_settings
            self.tv._running = True
            self.tv.start()
            marker = default_state_path().with_name('onboarding.json')
            if not marker.exists():
                self.tv.hint_visible = True
                self.tv.overlay.show_message('↑↓ channels · ←→ volume · G guide · S settings · F fullscreen', duration=10)
                write_json(marker, {'version': 1, 'shown': True})
        self._signature = self.signature(config, lineup)
        if not self.warming or all(f.done() for f in self.warming):
            self.warming = self.service.warm(lineup)

    @staticmethod
    def signature(config, lineup):
        return (config, getattr(lineup, "revision", tuple((ch.number, ch.config, tuple(ch.episodes)) for ch in lineup)))

    def tick(self):
        if self._shutdown:
            return
        try:
            self._ticks += 1
            if self.tv:
                self.tv.step()
                if not self.tv._running:
                    self.qt.quit()
                    return
                if self.tv.guide_open and self._ticks % 20 == 0:
                    self.tv._render_guide()
            if self.future and self.future.done():
                future, self.future = self.future, None
                prepared = future.result()
                if prepared and not (self.dialog and self.dialog.isVisible()):
                    config, lineup = prepared
                    self.error = None
                    if self._signature != self.signature(config, lineup):
                        self.apply(config, lineup)
            if self._ticks % 200 == 0 and self.future is None and not (self.dialog and self.dialog.isVisible()):
                self.future = self.service.scan(self.path)
            if self.warming and all(f.done() for f in self.warming):
                self.warming = []
                if self.tv:
                    for ch in self.tv.lineup:
                        ch._broadcast = None  # Rebuild lazily from the warmed duration cache.
        except (ConfigError, ValueError, RuntimeError, OSError) as exc:
            self.error = str(exc)
            if self.tv:
                self.tv.error = self.error
                self.tv.overlay.show_message('Library unavailable. S opens settings; reconnect your drive.', duration=10)
            else:
                self.show_settings(first_run=True)
                self.dialog.status.setText(self.error)

    def run(self, *, settings=False):
        if settings:
            self.show_settings(first_run=not self.path.exists())
        elif self.path.exists():
            self.future = self.service.scan(self.path)
        else:
            self.show_settings(first_run=True)
        self.timer.start()
        try:
            return self.qt.exec()
        finally:
            self._shutdown = True
            self.timer.stop()
            self.service.close()
            if self.tv:
                self.tv.shutdown()


def run_desktop(path, *, fullscreen=False, settings=False):
    return DesktopSession(path, fullscreen=fullscreen).run(settings=settings)
