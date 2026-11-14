import threading, time
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.label import Label
from jnius import autoclass
from android.runnable import run_on_ui_thread
import mini_marker

WebView = autoclass('android.webkit.WebView')
WebViewClient = autoclass('android.webkit.WebViewClient')
activity = autoclass('org.kivy.android.PythonActivity').mActivity

class MiniMarkerApp(App):
    def build(self):
        threading.Thread(target=self.start_server, daemon=True).start()
        Clock.schedule_once(self.open_webview, 2.5)
        return Label(text="Memuat Mini Marker Studio...\nDesign by ERVAN ALVIAN", halign="center")

    def start_server(self):
        mini_marker.app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)

    @run_on_ui_thread
    def open_webview(self, dt):
        webview = WebView(activity)
        settings = webview.getSettings()
        settings.setJavaScriptEnabled(True)
        settings.setDomStorageEnabled(True)
        settings.setAllowFileAccess(True)
        webview.setWebViewClient(WebViewClient())
        activity.setContentView(webview)
        webview.loadUrl("http://127.0.0.1:5000")

if __name__ == "__main__":
    MiniMarkerApp().run()
