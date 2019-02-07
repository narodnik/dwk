from PySide2.QtCore import QObject, Signal, Property, QUrl, qVersion
from PySide2.QtQml import QQmlApplicationEngine
from PySide2.QtWebEngine import QtWebEngine
from PySide2.QtWidgets import QApplication
import sys

class SourceTextProperty(QObject):

    def __init__(self, text):
        QObject.__init__(self)
        self._source_text = text

    def _text(self):
        return self._source_text

    def _set_text(self, text):
        self._source_text = text
        self.text_changed.emit()

    @Signal
    def text_changed(self):
        pass

    text = Property(str, _text, _set_text, notify=text_changed)

class HtmlOutputProperty(QObject):

    def __init__(self, text):
        QObject.__init__(self)
        self._html_text = text

    def _text(self):
        return self._html_text

    def _set_text(self, text):
        self._html_text = text
        self.text_changed.emit()

    @Signal
    def text_changed(self):
        pass

    text = Property(str, _text, _set_text, notify=text_changed)

def main():
    app = QApplication([])
    QtWebEngine.initialize()

    engine = QQmlApplicationEngine()
    source_text_property = SourceTextProperty(open('sample.md').read())
    html_output_property = HtmlOutputProperty(open('build/main.html').read())
    engine.rootContext().setContextProperty('source_text', source_text_property)
    engine.rootContext().setContextProperty('html_output', html_output_property)
    engine.load(QUrl.fromLocalFile('view.qml'))
    if not engine.rootObjects():
        return -1

    return app.exec_()

if __name__ == '__main__':
    print(qVersion())
    sys.exit(main())

