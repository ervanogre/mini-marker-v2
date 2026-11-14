[app]
title = Mini Marker Studio
package.name = minimarkerstudio
package.domain = org.ervanalvian
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,dxf,xlsx
version = 1.0
requirements = python3,kivy,flask,werkzeug,jinja2,markupsafe,itsdangerous,click,ezdxf,matplotlib,numpy,pillow,openpyxl,pyjnius,android
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
android.api = 33
android.minapi = 24
android.archs = arm64-v8a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
