[app]
title = Mini Marker Studio
package.name = minimarkerstudio
package.domain = org.ervanalvian
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,dxf,xlsx
version = 1.0
requirements = python3==3.11.5,hostpython3==3.11.5,kivy==2.3.0,flask,werkzeug,jinja2,markupsafe,itsdangerous,click,numpy==1.26.4,matplotlib==3.8.4,pillow,pyjnius,android,ezdxf,openpyxl,typing_extensions,pyparsing,fonttools,cycler,kiwisolver,python-dateutil,et_xmlfile
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
android.api = 33
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
