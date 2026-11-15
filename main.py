import os, sys, threading, traceback
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.label import Label
from jnius import autoclass
from android.runnable import run_on_ui_thread

WebView = autoclass('android.webkit.WebView')
WebViewClient = autoclass('android.webkit.WebViewClient')
WebChromeClient = autoclass('android.webkit.WebChromeClient')
py_activity = autoclass('org.kivy.android.PythonActivity').mActivity

class MiniMarkerApp(App):
    def build(self):
        self.lbl = Label(
            text="Memuat Mini Marker Studio...\nDesign by ERVAN ALVIAN",
            halign="center", valign="middle",
            text_size=(Window.width - 40, None),
            font_size="14sp"
        )
        threading.Thread(target=self.start_server, daemon=True).start()
        Clock.schedule_once(self.open_webview, 2.5)
        return self.lbl

    def start_server(self):
        try:
            import mini_marker
            mini_marker.app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
        except Exception:
            err = traceback.format_exc()
            Clock.schedule_once(lambda dt: setattr(self.lbl, 'text', f"Error Server:\n{err[-900:]}"), 0)

    @run_on_ui_thread
    def open_webview(self, dt):
        try:
            webview = WebView(py_activity)
            settings = webview.getSettings()
            settings.setJavaScriptEnabled(True)
            settings.setDomStorageEnabled(True)
            settings.setAllowFileAccess(True)
            settings.setAllowContentAccess(True)
            webview.setWebViewClient(WebViewClient())
            webview.setWebChromeClient(WebChromeClient())
            py_activity.setContentView(webview)
            webview.loadUrl("http://127.0.0.1:5000")
        except Exception:
            err = traceback.format_exc()
            self.lbl.text = f"Error UI:\n{err[-900:]}"

if __name__ == "__main__":
    MiniMarkerApp().run()
