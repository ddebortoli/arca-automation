"""Reusable widgets for the PyQt6 desktop app."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class SecretLineEdit(QWidget):
    """Password-like input with an eye toggle button."""

    textChanged = pyqtSignal(str)

    def __init__(self, placeholder: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.setSpacing(6)

        self._edit = QLineEdit()
        self._edit.setPlaceholderText(placeholder)
        self._edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._edit.textChanged.connect(self.textChanged.emit)

        self._eye_btn = QPushButton("👁")
        self._eye_btn.setObjectName("btn_eye")
        self._eye_btn.setFixedWidth(28)
        self._eye_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._eye_btn.clicked.connect(self._toggle_visibility)

        layout.addWidget(self._edit)
        layout.addWidget(self._eye_btn)

    def _toggle_visibility(self) -> None:
        if self._edit.echoMode() == QLineEdit.EchoMode.Password:
            self._edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self._eye_btn.setText("🙈")
            return
        self._edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._eye_btn.setText("👁")

    def text(self) -> str:
        return self._edit.text()

    def setText(self, text: str) -> None:  # noqa: N802
        self._edit.setText(text)

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802
        self._edit.setEnabled(enabled)
        self._eye_btn.setEnabled(enabled)


def make_field(label_text: str, widget: QWidget, optional: bool = False) -> QWidget:
    """Wrap an input widget with a label."""
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)

    header = QHBoxLayout()
    header.setContentsMargins(0, 0, 0, 0)
    lbl = QLabel(label_text)
    lbl.setObjectName("field_label")
    header.addWidget(lbl)

    if optional:
        badge = QLabel("opcional")
        badge.setStyleSheet("font-size:10px; color:#888;")
        header.addWidget(badge)

    header.addStretch()
    layout.addLayout(header)
    layout.addWidget(widget)
    return container


class CardWidget(QFrame):
    """Card-style container."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 14, 16, 14)
        self._layout.setSpacing(12)

    def layout(self) -> QVBoxLayout:  # type: ignore[override]
        return self._layout


def make_divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Plain)
    line.setStyleSheet("color: #e8e8e4;")
    return line


def make_section_header(title: str, desc: str = "") -> QWidget:
    w = QWidget()
    layout = QVBoxLayout(w)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)

    t = QLabel(title)
    t.setObjectName("section_title")
    layout.addWidget(t)

    if desc:
        d = QLabel(desc)
        d.setObjectName("section_desc")
        d.setWordWrap(True)
        layout.addWidget(d)
    return w


class AlertBanner(QLabel):
    """Banner for warnings/success."""

    def __init__(
        self, text: str = "", kind: str = "warning", parent: QWidget | None = None
    ) -> None:
        super().__init__(text, parent)
        self.setWordWrap(True)
        self.setKind(kind)

    def setKind(self, kind: str) -> None:  # noqa: N802
        obj = "alert_warning" if kind == "warning" else "alert_success"
        self.setObjectName(obj)


def make_stat_card(label: str, value: str, color: str = "default") -> tuple[QWidget, QLabel]:
    """Create a small stat card like the HTML mockup.

    color supports: default | green | amber.
    """
    card = QWidget()
    card.setObjectName("stat_card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(4)

    lbl = QLabel(label)
    num = QLabel(value)

    if color == "green":
        num.setStyleSheet("color: #1D9E75; font-size: 20px; font-weight: 600;")
    elif color == "amber":
        num.setStyleSheet("color: #EF9F27; font-size: 20px; font-weight: 600;")
    else:
        num.setStyleSheet("font-size: 20px; font-weight: 600;")

    lbl.setObjectName("section_desc")
    layout.addWidget(lbl)
    layout.addWidget(num)
    return card, num
