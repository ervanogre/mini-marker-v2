import os, threading, traceback
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from jnius import autoclass

Intent = autoclass('android.content.Intent')
Uri = autoclass('android.net.Uri')
Settings = autoclass('android.provider.Settings')
Context = autoclass('android.content.Context')
PowerManager = autoclass('android.os.PowerManager')
BuildVersion = autoclass('android.os.Build$VERSION')
py_activity = autoclass('org.kivy.android.PythonActivity').mActivity

class MiniMarkerApp(App):
    def build(self):
        root = BoxLayout(orientation='vertical', padding=24, spacing=14)
        self.lbl = Label(
            text="MINI MARKER STUDIO PRO\nDesign by ERVAN ALVIAN\n\nMenyiapkan server lokal...",
            halign="center", valign="middle",
            text_size=(Window.width - 48, None),
            font_size="15sp"
        )
        self.btn_bat = Button(
            text="NONAKTIFKAN PEMBATASAN BATERAI",
            size_hint=(1, None), height="52dp",
            background_color=(0.85, 0.45, 0.05, 1),
            font_size="14sp", bold=True
        )
        self.btn_bat.bind(on_release=self.request_no_battery_limit)

        btn_open = Button(
            text="BUKA MINI MARKER STUDIO",
            size_hint=(1, None), height="58dp",
            background_color=(0.01, 0.52, 0.78, 1),
            font_size="16sp", bold=True
        )
        btn_open.bind(on_release=self.open_in_browser)

        root.add_widget(self.lbl)
        root.add_widget(self.btn_bat)
        root.add_widget(btn_open)

        threading.Thread(target=self.start_server, daemon=True).start()
        Clock.schedule_once(self.check_battery_and_launch, 1.2)
        return root

    def is_unrestricted(self):
        try:
            if BuildVersion.SDK_INT >= 23:
                pm = py_activity.getSystemService(Context.POWER_SERVICE)
                return pm.isIgnoringBatteryOptimizations(py_activity.getPackageName())
        except Exception:
            pass
        return True

    def request_no_battery_limit(self, *args):
        pkg = py_activity.getPackageName()
        try:
            intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:" + pkg))
            py_activity.startActivity(intent)
        except Exception:
            try:
                intent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:" + pkg))
                py_activity.startActivity(intent)
            except Exception:
                pass

    def check_battery_and_launch(self, dt):
        if not self.is_unrestricted():
            self.lbl.text = "PERHATIAN: PEMBATASAN BATERAI MASIH AKTIF!\n\nKetuk tombol oranye di bawah dan pilih\n'Tidak ada pembatasan' / 'Izinkan' agar server tidak terhenti."
            self.request_no_battery_limit()
        else:
            self.btn_bat.text = "PEMBATASAN BATERAI NONAKTIF (AMAN)"
            self.btn_bat.background_color = (0.08, 0.62, 0.35, 1)
            self.lbl.text = "MINI MARKER STUDIO AKTIF!\nDesign by ERVAN ALVIAN\n\nMembuka aplikasi di browser..."
            self.open_in_browser()

    def start_server(self):
        try:
            import mini_marker
            mini_marker.app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False, threaded=True)
        except Exception:
            err = traceback.format_exc()
            Clock.schedule_once(lambda dt: setattr(self.lbl, 'text', f"Error Server:\n{err[-900:]}"), 0)

    def open_in_browser(self, *args):
        try:
            py_activity.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("http://127.0.0.1:5000")))
        except Exception as e:
            self.lbl.text = f"Buka Chrome dan akses:\nhttp://127.0.0.1:5000\n({e})"

if __name__ == "__main__":
    MiniMarkerApp().run()
