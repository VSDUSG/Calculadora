"""Conversão de imagens DICOM para PNG (visualização na web e no laudo)."""
import logging
import os

import numpy as np
from PIL import Image
from pydicom import dcmread

from . import config

log = logging.getLogger("daikon.imagens")


def _para_8bits(arr: np.ndarray) -> np.ndarray:
    if arr.dtype == np.uint8:
        return arr
    arr = arr.astype(np.float32)
    minimo, maximo = float(arr.min()), float(arr.max())
    if maximo <= minimo:
        return np.zeros(arr.shape, dtype=np.uint8)
    return (((arr - minimo) / (maximo - minimo)) * 255.0).astype(np.uint8)


def gerar_png(caminho_dcm: str, sop_uid: str):
    """Gera um PNG a partir do DICOM. Para cine (multiframe) usa o 1º frame.

    Retorna (caminho_png ou None, quantidade_de_frames).
    """
    frames = 1
    try:
        ds = dcmread(caminho_dcm)
        frames = int(getattr(ds, "NumberOfFrames", 1) or 1)
        arr = ds.pixel_array

        fotometria = str(getattr(ds, "PhotometricInterpretation", "MONOCHROME2"))
        if fotometria.startswith("YBR"):
            from pydicom.pixels import convert_color_space
            arr = convert_color_space(arr, fotometria, "RGB", per_frame=True)
        elif fotometria == "PALETTE COLOR":
            from pydicom.pixels import apply_color_lut
            arr = apply_color_lut(arr, ds)

        if frames > 1:
            arr = arr[0]

        arr = _para_8bits(arr)
        if fotometria == "MONOCHROME1":
            arr = 255 - arr

        img = Image.fromarray(arr)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        os.makedirs(config.PNG_DIR, exist_ok=True)
        caminho_png = os.path.join(config.PNG_DIR, f"{sop_uid}.png")
        img.save(caminho_png, "PNG")
        return caminho_png, frames
    except Exception:
        log.exception("Não foi possível converter %s para PNG", caminho_dcm)
        return None, frames
