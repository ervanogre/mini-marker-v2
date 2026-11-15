[app]
title = Mini Marker Studio
package.name = minimarkerstudio
package.domain = org.ervanalvian
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,dxf,xlsx
version = 1.0
requirements = python3==3.11.5,hostpython3==3.11.5,kivy==2.3.0,flask,werkzeug,jinja2,markupsafe,itsdangerous,click,pillow,pyjnius,android,openpyxl,typing_extensions,pyparsing,fonttools,et_xmlfile
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,WAKE_LOCK
android.api = 33
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
