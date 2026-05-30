# pyinstaller/windows.spec
from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(SPEC)))
block_cipher = None

def collect_item_hiddenimports(root):
    modules = []
    items_root = os.path.join(root, 'asterix_decoder', 'data_items')
    for current_root, _, filenames in os.walk(items_root):
        for filename in filenames:
            if not (filename.startswith('item_') and filename.endswith('.py')):
                continue
            source_path = os.path.join(current_root, filename)
            relative = os.path.relpath(source_path, root)
            module_name = relative[:-3].replace(os.sep, '.')
            modules.append(module_name)
    return sorted(set(modules))

def safe_collect(package):
    try:
        d, b, h = collect_all(package)
        return d, b, h
    except Exception as e:
        print(f"[WARN] collect_all('{package}') failed: {e}")
        return [], [], []

def safe_metadata(package):
    try:
        return copy_metadata(package)
    except Exception as e:
        print(f"[WARN] copy_metadata('{package}') failed: {e}")
        return []

uv_d, uv_b, uv_h = safe_collect('uvicorn')
st_d, st_b, st_h = safe_collect('starlette')
fa_d, fa_b, fa_h = safe_collect('fastapi')
ws_d, ws_b, ws_h = safe_collect('websockets')
wv_d, wv_b, wv_h = safe_collect('webview')
pn_d, pn_b, pn_h = safe_collect('pythonnet')
cl_d, cl_b, cl_h = safe_collect('clr_loader')
mp_d, mp_b, mp_h = safe_collect('multipart')       # python-multipart

# python-multipart: collect both possible module names + metadata
mp_d, mp_b, mp_h = safe_collect('multipart')
mp2_d, mp2_b, mp2_h = safe_collect('python_multipart')
item_hiddenimports = collect_item_hiddenimports(ROOT)

# copy_metadata is required so FastAPI's runtime check finds the package
multipart_meta = (
    safe_metadata('python-multipart')
    + safe_metadata('python_multipart')
    + safe_metadata('multipart')
)

all_datas = (
    [(os.path.join(ROOT, 'frontend'), 'frontend')]
    + uv_d + st_d + fa_d + ws_d + wv_d + pn_d + cl_d
    + mp_d + mp2_d
    + multipart_meta
)
all_binaries = uv_b + st_b + fa_b + ws_b + wv_b + pn_b + cl_b + mp_b + mp2_b
all_hidden = (
    uv_h + st_h + fa_h + ws_h + wv_h + pn_h + cl_h + mp_h + mp2_h
    + collect_submodules('uvicorn')
    + collect_submodules('starlette')
    + collect_submodules('fastapi')
    + collect_submodules('websockets')
    + collect_submodules('multipart')
    + item_hiddenimports
    + [
        'multipart',
        'multipart.exceptions',
        'webview.platforms.winforms',
        'webview.platforms.edgechromium',
        'clr',
        'multiprocessing',
        'asyncio',
        'h11',
        'anyio',
        'anyio._backends._asyncio',
        'anyio._backends._trio',
    ]
)

a = Analysis(
    [os.path.join(ROOT, 'run.py')],
    pathex=[ROOT],
    binaries=all_binaries,
    datas=all_datas,
    hiddenimports=all_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ATM_analyzer',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    runtime_tmpdir=None,
)
