import os, sys, threading, traceback
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from jnius import autoclass

Intent = autoclass('android.content.Intent')
Uri = autoclass('android.net.Uri')
py_activity = autoclass('org.kivy.android.PythonActivity').mActivity

class MiniMarkerApp(App):
    def build(self):
        root = BoxLayout(orientation='vertical', padding=28, spacing=18)
        self.lbl = Label(
            text="MINI MARKER STUDIO\nDesign by ERVAN ALVIAN\n\nMenyiapkan server lokal...",
            halign="center", valign="middle",
            text_size=(Window.width - 56, None),
            font_size="16sp"
        )
        btn_open = Button(
            text="BUKA MINI MARKER STUDIO",
            size_hint=(1, None),
            height="58dp",
            background_color=(0.01, 0.52, 0.78, 1),
            font_size="16sp",
            bold=True
        )
        btn_open.bind(on_release=self.open_in_browser)
        root.add_widget(self.lbl)
        root.add_widget(btn_open)

        threading.Thread(target=self.start_server, daemon=True).start()
        Clock.schedule_once(self.auto_launch, 2.0)
        return root

    def start_server(self):
        try:
            import mini_marker
            mini_marker.app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
        except Exception:
            err = traceback.format_exc()
            Clock.schedule_once(lambda dt: setattr(self.lbl, 'text', f"Error Server:\n{err[-900:]}"), 0)

    def auto_launch(self, dt):
        self.lbl.text = "MINI MARKER STUDIO AKTIF!\nDesign by ERVAN ALVIAN\n\nJangan tutup aplikasi ini dari background saat digunakan.\nKetuk tombol di bawah jika halaman belum terbuka."
        self.open_in_browser()

    def open_in_browser(self, *args):
        try:
            intent = Intent(Intent.ACTION_VIEW, Uri.parse("http://127.0.0.1:5000"))
            py_activity.startActivity(intent)
        except Exception as e:
            self.lbl.text = f"Silakan buka Chrome dan akses:\nhttp://127.0.0.1:5000\n({e})"

if __name__ == "__main__":
    MiniMarkerApp().run()
