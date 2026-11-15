import os, sys, threading, traceback
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.label import Label
from jnius import autoclass, PythonJavaClass, java_method
from android.runnable import run_on_ui_thread
from android import activity as android_activity

WebView = autoclass('android.webkit.WebView')
WebViewClient = autoclass('android.webkit.WebViewClient')
WebChromeClient = autoclass('android.webkit.WebChromeClient')
Intent = autoclass('android.content.Intent')
Uri = autoclass('android.net.Uri')
py_activity = autoclass('org.kivy.android.PythonActivity').mActivity

file_path_callback = None

class CustomWebChromeClient(PythonJavaClass):
    __javainterfaces__ = ['android/webkit/WebChromeClient']
    __javacontext__ = 'app'

    @java_method('(Landroid/webkit/WebView;Landroid/webkit/ValueCallback;Landroid/webkit/WebChromeClient$FileChooserParams;)Z')
    def onShowFileChooser(self, webView, filePathCallback, fileChooserParams):
        global file_path_callback
        if file_path_callback is not None:
            file_path_callback.onReceiveValue(None)
        file_path_callback = filePathCallback
        intent = Intent(Intent.ACTION_GET_CONTENT)
        intent.addCategory(Intent.CATEGORY_OPENABLE)
        intent.setType("*/*")
        py_activity.startActivityForResult(Intent.createChooser(intent, "Pilih File"), 1001)
        return True

def on_activity_result(requestCode, resultCode, intent):
    global file_path_callback
    if requestCode == 1001 and file_path_callback is not None:
        results = None
        if resultCode == -1 and intent is not None:
            data_str = intent.getDataString()
            if data_str:
                results = [Uri.parse(data_str)]
        file_path_callback.onReceiveValue(results)
        file_path_callback = None

android_activity.bind(on_activity_result=on_activity_result)

class MiniMarkerApp(App):
    def build(self):
        self.lbl = Label(
            text="Memuat Mini Marker Studio...\nDesign by ERVAN ALVIAN",
            halign="left", valign="middle",
            text_size=(Window.width - 40, None),
            font_size="12sp"
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
            webview.setWebViewClient(WebViewClient())
            self.chrome_client = CustomWebChromeClient()
            webview.setWebChromeClient(self.chrome_client)
            py_activity.setContentView(webview)
            webview.loadUrl("http://127.0.0.1:5000")
        except Exception as e:
            self.lbl.text = f"Error UI:\n{e}"

if __name__ == "__main__":
    MiniMarkerApp().run()
