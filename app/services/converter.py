"""Word (.docx) -> PDF. On Windows, drives Microsoft Word directly (pywin32)."""
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

_lock = threading.Lock()          # one conversion at a time


class ConversionError(RuntimeError):
    pass


# ---------------------------------------------------------------- LibreOffice
def _find_soffice():
    for name in ("soffice", "libreoffice"):
        p = shutil.which(name)
        if p:
            return p
    for p in (r"C:\Program Files\LibreOffice\program\soffice.exe",
              r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
              "/Applications/LibreOffice.app/Contents/MacOS/soffice"):
        if os.path.exists(p):
            return p
    return None


def _libreoffice(docx: Path, pdf: Path) -> None:
    exe = _find_soffice()
    with tempfile.TemporaryDirectory() as profile, tempfile.TemporaryDirectory() as out:
        cmd = [exe, f"-env:UserInstallation={Path(profile).as_uri()}", "--headless",
               "--convert-to", "pdf", "--outdir", out, str(docx)]
        subprocess.run(cmd, check=True, capture_output=True, timeout=240)
        produced = Path(out) / (docx.stem + ".pdf")
        if not produced.exists():
            raise ConversionError("LibreOffice produced no PDF")
        shutil.move(str(produced), str(pdf))


# ----------------------------------------------------------------- MS Word
def _word_com_available() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import pythoncom  # noqa: F401
        import win32com.client  # noqa: F401
        return True
    except ImportError:
        return False


def _word_com(docx: Path, pdf: Path) -> None:
    import pythoncom
    import win32com.client.dynamic as dyn

    pythoncom.CoInitialize()                       # needed: Flask runs us in a worker thread
    word = doc = None
    try:
        word = dyn.Dispatch("Word.Application")    # dynamic = no gen_py cache
        word.Visible = False
        word.DisplayAlerts = 0                     # never show pop-up dialogs
        doc = word.Documents.Open(str(docx.resolve()), ReadOnly=True,
                                  AddToRecentFiles=False, ConfirmConversions=False)
        doc.SaveAs2(str(pdf.resolve()), FileFormat=17)       # 17 = PDF
    finally:
        try:
            if doc is not None:
                doc.Close(False)
        except Exception:
            pass
        try:
            if word is not None:
                word.Quit()
        except Exception:
            pass
        pythoncom.CoUninitialize()


def _word_docx2pdf(docx: Path, pdf: Path) -> None:
    from docx2pdf import convert
    convert(str(docx.resolve()), str(pdf.resolve()))


def _word_available() -> bool:
    if _word_com_available():
        return True
    try:
        import docx2pdf  # noqa: F401
        return sys.platform in ("win32", "darwin")
    except ImportError:
        return False


def _word(docx: Path, pdf: Path) -> None:
    errors = []
    if _word_com_available():
        try:
            return _word_com(docx, pdf)
        except Exception as e:
            errors.append(f"direct Word: {e}")
    try:
        return _word_docx2pdf(docx, pdf)
    except Exception as e:
        errors.append(f"docx2pdf: {e}")
    raise ConversionError("; ".join(errors))


# -------------------------------------------------------------------- public
def available_engines() -> list:
    out = []
    if _word_available():
        out.append("word")
    if _find_soffice():
        out.append("libreoffice")
    return out


def docx_to_pdf(docx: Path, pdf: Path, mode: str = "auto") -> str:
    order = {"auto": ["word", "libreoffice"], "word": ["word"], "libreoffice": ["libreoffice"]}[mode]
    errors = []
    pdf.unlink(missing_ok=True)
    with _lock:
        for engine in order:
            try:
                if engine == "word" and _word_available():
                    _word(docx, pdf)
                elif engine == "libreoffice" and _find_soffice():
                    _libreoffice(docx, pdf)
                else:
                    continue
                if pdf.exists():
                    return engine
                errors.append(f"{engine}: no PDF was produced")
            except Exception as e:
                errors.append(f"{engine}: {e}")
    raise ConversionError(
        "No PDF converter worked. " + (" | ".join(errors) if errors else
        "None found - install Microsoft Word + 'pip install pywin32', or LibreOffice (free)."))