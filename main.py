import os, sys, threading, traceback
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from jnius import autoclass
from android.runnable import run_on_ui_thread

WebView = autoclass('android.webkit.WebView')
WebViewClient = autoclass('android.webkit.WebViewClient')
LayoutParams = autoclass('android.view.ViewGroup$LayoutParams')
Intent = autoclass('android.content.Intent')
Uri = autoclass('android.net.Uri')
py_activity = autoclass('org.kivy.android.PythonActivity').mActivity

class MiniMarkerApp(App):
    def build(self):
        root = BoxLayout(orientation='vertical', padding=24, spacing=14)
        self.lbl = Label(
            text="Memuat Mini Marker Studio...\nDesign by ERVAN ALVIAN",
            halign="center", valign="middle",
            text_size=(Window.width - 48, None),
            font_size="15sp"
        )
        btn_chrome = Button(
            text="Buka di Browser Chrome (Full Fitur)",
            size_hint=(1, None),
            height="52dp",
            background_color=(0.01, 0.52, 0.78, 1),
            font_size="15sp"
        )
        btn_chrome.bind(on_release=self.open_in_browser)
        root.add_widget(self.lbl)
        root.add_widget(btn_chrome)

        threading.Thread(target=self.start_server, daemon=True).start()
        Clock.schedule_once(self.attach_webview, 2.5)
        return root

    def start_server(self):
        try:
            import mini_marker
            mini_marker.app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
        except Exception:
            err = traceback.format_exc()
            Clock.schedule_once(lambda dt: setattr(self.lbl, 'text', f"Error Server:\n{err[-900:]}"), 0)

    def open_in_browser(self, *args):
        try:
            intent = Intent(Intent.ACTION_VIEW, Uri.parse("http://127.0.0.1:5000"))
            py_activity.startActivity(intent)
        except Exception as e:
            self.lbl.text = f"Gagal membuka browser:\n{e}"

    @run_on_ui_thread
    def attach_webview(self, dt):
        try:
            webview = WebView(py_activity)
            settings = webview.getSettings()
            settings.setJavaScriptEnabled(True)
            settings.setDomStorageEnabled(True)
            settings.setAllowFileAccess(True)
            webview.setWebViewClient(WebViewClient())
            params = LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT)
            py_activity.addContentView(webview, params)
            webview.loadUrl("http://127.0.0.1:5000")
        except Exception:
            self.lbl.text = "Server Mini Marker Studio Aktif!\nKetuk tombol di bawah untuk membuka."

if __name__ == "__main__":
    MiniMarkerApp().run()
