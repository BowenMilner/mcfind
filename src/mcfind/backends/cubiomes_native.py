from __future__ import annotations

from ctypes import CDLL, POINTER, Structure, byref, c_char, c_int, c_longlong
import platform
import shutil
import subprocess
from pathlib import Path

from mcfind.errors import McfindError
from mcfind.runtime import cache_home, ensure_dir


ROOT = Path(__file__).resolve().parents[3]
VENDOR = ROOT / "vendor" / "cubiomes"
NATIVE = ROOT / "src" / "mcfind" / "native" / "mcfind_cubiomes.c"


class NativeResult(Structure):
    _fields_ = [
        ("x", c_int),
        ("z", c_int),
        ("valid", c_int),
        ("exact", c_int),
    ]


def _library_name() -> str:
    system = platform.system()
    if system == "Darwin":
        return "libmcfind_cubiomes.dylib"
    if system == "Windows":
        return "mcfind_cubiomes.dll"
    return "libmcfind_cubiomes.so"


def build_native_library(cache_dir: str | None = None) -> Path:
    cc = shutil.which("cc")
    if not cc:
        raise McfindError("backend unavailable", hint="A C compiler is required to build the bundled cubiomes adapter.")
    build_dir = ensure_dir(cache_home(cache_dir) / "native")
    output = build_dir / _library_name()
    vendor_sources = [
        VENDOR / "finders.c",
        VENDOR / "generator.c",
        VENDOR / "layers.c",
        VENDOR / "biomes.c",
        VENDOR / "biomenoise.c",
        VENDOR / "noise.c",
        VENDOR / "util.c",
    ]
    sources = vendor_sources + [NATIVE]
    if output.exists():
        output_mtime = output.stat().st_mtime
        if all(source.stat().st_mtime <= output_mtime for source in sources):
            return output
    include_flag = f"-I{VENDOR}"
    cmd = [
        cc,
        "-O2",
        "-std=c11",
        include_flag,
    ]
    if platform.system() == "Darwin":
        cmd.extend(["-dynamiclib", "-o", str(output)])
    elif platform.system() == "Windows":
        cmd.extend(["-shared", "-o", str(output)])
    else:
        cmd.extend(["-shared", "-fPIC", "-o", str(output)])
    cmd.extend(str(source) for source in sources)
    cmd.append("-lm")
    completed = subprocess.run(cmd, capture_output=True, text=True)
    if completed.returncode != 0:
        raise McfindError(
            "backend unavailable",
            hint=(completed.stderr or completed.stdout or "Failed to compile the cubiomes adapter.").strip(),
        )
    return output


def load_native_library(cache_dir: str | None = None) -> CDLL:
    library = CDLL(str(build_native_library(cache_dir)))
    library.mcfind_query_structure.argtypes = [
        c_int,
        c_int,
        c_longlong,
        c_int,
        c_int,
        c_int,
        c_int,
        c_int,
        POINTER(NativeResult),
        POINTER(c_int),
        POINTER(c_char),
        c_int,
    ]
    library.mcfind_query_structure.restype = c_int
    library.mcfind_query_biome.argtypes = [
        c_int,
        c_int,
        c_int,
        c_int,
        c_longlong,
        c_int,
        c_int,
        c_int,
        c_int,
        POINTER(NativeResult),
        POINTER(c_int),
        POINTER(c_char),
        c_int,
    ]
    library.mcfind_query_biome.restype = c_int
    return library
