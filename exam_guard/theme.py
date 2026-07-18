APP_STYLESHEET = r"""
QWidget {
    color: #eaf2f5;
    background: #080d11;
    font-family: "Segoe UI Variable Text", "Segoe UI";
    font-size: 10pt;
}

QMainWindow, QDialog, QWidget#AppRoot, QWidget#AppBody {
    background: #080d11;
}

QLabel {
    background: transparent;
}

QFrame#Header {
    background: #0e151a;
    border: 0;
    border-bottom: 1px solid #27343c;
}

QLabel#BrandMark {
    background: #111c21;
    border: 1px solid #2b494d;
    border-radius: 6px;
}

QLabel#Brand {
    color: #f4f8fa;
    font-family: "Bahnschrift SemiCondensed", "Segoe UI Variable Display", "Segoe UI";
    font-size: 19pt;
    font-weight: 600;
}

QLabel#BrandAccent, QLabel#SectionTitle, QLabel#MetricLabel, QLabel#RailHint {
    color: #35d0c5;
    font-family: "Cascadia Mono", "Consolas";
    font-size: 8pt;
    font-weight: 700;
}

QLabel#RailHint {
    color: #667780;
    font-size: 7pt;
}

QLabel#StateBadge {
    background: #171f25;
    color: #a5b2b8;
    border: 1px solid #34414a;
    border-radius: 4px;
    padding: 5px 9px;
    font-family: "Cascadia Mono", "Consolas";
    font-size: 8pt;
    font-weight: 700;
}

QLabel#StateBadge[state="live"] {
    background: #102922;
    color: #61dfac;
    border-color: #245d4b;
}

QLabel#StateBadge[state="alert"] {
    background: #35171d;
    color: #ff8290;
    border-color: #77313d;
}

QFrame#HeaderDivider {
    color: #27343c;
    max-width: 1px;
    margin: 5px 3px;
}

QPushButton, QDoubleSpinBox, QSpinBox {
    min-height: 34px;
    color: #dce6ea;
    background: #171f27;
    border: 1px solid #31414a;
    border-radius: 4px;
    padding: 0 11px;
}

QPushButton {
    font-weight: 600;
}

QPushButton:hover, QDoubleSpinBox:hover, QSpinBox:hover {
    color: #ffffff;
    background: #1c2830;
    border-color: #35d0c5;
}

QPushButton:pressed {
    background: #223139;
}

QPushButton:focus, QDoubleSpinBox:focus, QSpinBox:focus {
    border: 1px solid #35d0c5;
}

QPushButton:disabled, QDoubleSpinBox:disabled, QSpinBox:disabled {
    color: #5d6970;
    background: #11171c;
    border-color: #202a30;
}

QPushButton[primary="true"] {
    color: #061311;
    background: #35d0c5;
    border-color: #35d0c5;
    font-weight: 700;
}

QPushButton[primary="true"]:hover {
    color: #020908;
    background: #54ddd3;
    border-color: #6be4dc;
}

QPushButton[primary="true"]:disabled {
    color: #5f7e7d;
    background: #16302f;
    border-color: #214342;
}

QPushButton[confirm="true"] {
    color: #7ce2b8;
    background: #10271f;
    border-color: #285743;
}

QPushButton[confirm="true"]:hover {
    color: #a0f0cf;
    background: #153328;
    border-color: #49d49d;
}

QPushButton[destructive="true"] {
    color: #ff8793;
    background: #2a151a;
    border-color: #5f2c35;
}

QPushButton[destructive="true"]:hover {
    color: #ffabb4;
    background: #371a21;
    border-color: #ff6575;
}

QToolButton {
    width: 34px;
    height: 34px;
    color: #dce6ea;
    background: #171f27;
    border: 1px solid #31414a;
    border-radius: 4px;
}

QToolButton:hover {
    background: #1c2830;
    border-color: #35d0c5;
}

QToolButton:disabled {
    background: #11171c;
    border-color: #202a30;
}

QFrame#MetricStrip {
    background: #10171d;
    border: 1px solid #27343c;
    border-radius: 6px;
}

QFrame#MetricCell {
    background: transparent;
    border: 0;
    border-right: 1px solid #243039;
}

QFrame#MetricCell[last="true"] {
    border-right: 0;
}

QLabel#MetricLabel {
    color: #71818a;
}

QLabel#MetricValue {
    color: #edf4f6;
    font-family: "Bahnschrift SemiCondensed", "Segoe UI Variable Display", "Segoe UI";
    font-size: 16pt;
    font-weight: 600;
}

QLabel#MetricValue[accent="true"] {
    color: #35d0c5;
}

QLabel#MetricValue[compact="true"] {
    font-size: 13pt;
}

QFrame#VideoShell, QFrame#SideRail {
    background: #0d1318;
    border: 1px solid #27343c;
    border-radius: 6px;
}

QFrame#PanelHeader {
    background: #11191f;
    border: 0;
    border-bottom: 1px solid #27343c;
}

QFrame#LegendSwatch {
    background: #49d49d;
    border: 0;
    border-radius: 3px;
}

QFrame#LegendSwatch[state="warning"] {
    background: #f3b85b;
}

QFrame#LegendSwatch[state="alert"] {
    background: #ff6575;
}

QLabel#LegendLabel {
    color: #81919a;
    font-size: 8pt;
}

QLabel#VideoView {
    color: #71818a;
    background: #05080b;
    border: 0;
}

QSplitter::handle {
    background: transparent;
    width: 10px;
}

QTabWidget {
    background: #0d1318;
}

QTabWidget::pane {
    background: #0d1318;
    border: 0;
    border-top: 1px solid #27343c;
}

QTabBar::tab {
    color: #7d8d95;
    background: #0d1318;
    min-width: 110px;
    padding: 10px 12px;
    border: 0;
    border-bottom: 2px solid transparent;
}

QTabBar::tab:hover {
    color: #c7d2d7;
    background: #11191f;
}

QTabBar::tab:selected {
    color: #eaf2f5;
    background: #11191f;
    border-bottom-color: #35d0c5;
    font-weight: 600;
}

QTableWidget {
    color: #cbd6da;
    background: #0d1318;
    alternate-background-color: #10171d;
    border: 0;
    gridline-color: #202a31;
    selection-background-color: #17333a;
    selection-color: #f5fafb;
    outline: 0;
}

QHeaderView::section {
    color: #71818a;
    background: #11191f;
    border: 0;
    border-bottom: 1px solid #27343c;
    padding: 8px 6px;
    font-family: "Cascadia Mono", "Consolas";
    font-size: 8pt;
    font-weight: 700;
}

QTableCornerButton::section {
    background: #11191f;
    border: 0;
    border-bottom: 1px solid #27343c;
}

QTableWidget::item {
    padding: 7px 5px;
    border: 0;
    border-bottom: 1px solid #1d272d;
}

QScrollBar:vertical {
    background: #0d1318;
    width: 10px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #34424a;
    min-height: 28px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #45606a;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
    height: 0;
}

QWidget#IncidentPage {
    background: #0d1318;
}

QFrame#Footer {
    background: transparent;
    border: 0;
    min-height: 22px;
}

QFrame#FooterDot {
    background: #35d0c5;
    border: 0;
    border-radius: 3px;
}

QLabel#FooterStatus {
    color: #81919a;
    font-family: "Cascadia Mono", "Consolas";
    font-size: 8pt;
}

QLabel#Policy {
    color: #617079;
    font-size: 8pt;
}

QFrame#Toast {
    background: #28151a;
    border: 1px solid #74313d;
    border-left: 4px solid #ff6575;
    border-radius: 6px;
}

QLabel#ToastTitle {
    color: #ff9aa5;
    background: transparent;
    font-size: 11pt;
    font-weight: 700;
}

QLabel#ToastBody {
    color: #d8b5ba;
    background: transparent;
}

QGroupBox {
    color: #dce6ea;
    background: #0e151a;
    margin-top: 14px;
    padding: 15px 12px 12px 12px;
    border: 1px solid #2a3740;
    border-radius: 6px;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: #35d0c5;
    background: #080d11;
}

QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
QSpinBox::up-button, QSpinBox::down-button {
    width: 18px;
    background: #1b252c;
    border: 0;
    border-left: 1px solid #31414a;
}

QCheckBox {
    color: #cbd6da;
    spacing: 8px;
    background: transparent;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    background: #11181e;
    border: 1px solid #40515b;
    border-radius: 3px;
}

QCheckBox::indicator:checked {
    background: #35d0c5;
    border-color: #35d0c5;
}

QToolTip {
    color: #eef5f7;
    background: #1a242b;
    border: 1px solid #3a4a53;
    padding: 5px 7px;
}
"""
