"""
Video Frame Extractor
=====================
Extrahiert Frames aus einem MP4-Video in definierbaren Zeitintervallen.

Verwendung:
    python extract_frames.py video.mp4 --interval 100 --format webp --quality 85

Abhängigkeiten:
    pip install opencv-python-headless pillow
"""

import cv2
import argparse
import os
import sys
from pathlib import Path
from PIL import Image


# ── Unterstützte Formate mit Empfehlungen ──────────────────────────────────
FORMATS = {
    "png": {
        "ext": ".png",
        "desc": "Verlustfrei, große Dateien (~2-5 MB/Frame)",
        "cv2_params": [cv2.IMWRITE_PNG_COMPRESSION, 6],  # 0-9, höher = kleiner aber langsamer
    },
    "webp": {
        "ext": ".webp",
        "desc": "⭐ Empfohlen – verlustfrei oder lossy, ~60-80% kleiner als PNG",
        "cv2_params": [cv2.IMWRITE_WEBP_QUALITY, 90],
    },
    "jpg": {
        "ext": ".jpg",
        "desc": "Lossy, klein (~100-300 KB), keine Transparenz",
        "cv2_params": [cv2.IMWRITE_JPEG_QUALITY, 92],
    },
    "avif": {
        "ext": ".avif",
        "desc": "Modernster Codec, beste Kompression – braucht Pillow",
        "cv2_params": None,  # wird über Pillow gespeichert
    },
}


def extract_frames(
    video_path: str,
    output_dir: str = "frames",
    interval_ms: int = 100,
    fmt: str = "webp",
    quality: int | None = None,
    max_frames: int | None = None,
):
    """
    Extrahiert Frames aus einem Video.

    Args:
        video_path:   Pfad zum Eingabevideo
        output_dir:   Zielordner für die extrahierten Bilder
        interval_ms:  Zeitintervall zwischen Frames in Millisekunden
        fmt:          Bildformat (png, webp, jpg, avif)
        quality:      Qualität (1-100), überschreibt den Standard des Formats
        max_frames:   Maximale Anzahl zu extrahierender Frames (None = alle)
    """
    if fmt not in FORMATS:
        print(f"Fehler: Format '{fmt}' nicht unterstützt. Wähle aus: {list(FORMATS.keys())}")
        sys.exit(1)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Fehler: Video '{video_path}' konnte nicht geöffnet werden.")
        sys.exit(1)

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_s = total_frames / fps if fps > 0 else 0

    print(f"Video:      {video_path}")
    print(f"FPS:        {fps:.2f}")
    print(f"Frames:     {total_frames}")
    print(f"Dauer:      {duration_s:.2f}s")
    print(f"Intervall:  {interval_ms}ms")
    print(f"Format:     {fmt} ({FORMATS[fmt]['desc']})")
    print(f"Ausgabe:    {output_dir}/")
    print("-" * 50)

    os.makedirs(output_dir, exist_ok=True)

    format_info = FORMATS[fmt]
    frame_count = 0
    current_ms = 0.0

    while True:
        if max_frames and frame_count >= max_frames:
            break

        cap.set(cv2.CAP_PROP_POS_MSEC, current_ms)
        ret, frame = cap.read()
        if not ret:
            break

        timestamp_s = current_ms / 1000.0
        filename = f"frame_{frame_count:05d}_{timestamp_s:.3f}s{format_info['ext']}"
        filepath = os.path.join(output_dir, filename)

        # AVIF geht über Pillow, alles andere direkt über OpenCV
        if fmt == "avif":
            img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            q = quality if quality else 75
            img.save(filepath, format="AVIF", quality=q)
        else:
            params = list(format_info["cv2_params"])  # Kopie
            if quality is not None:
                # Qualitätsparameter überschreiben
                if fmt == "jpg":
                    params = [cv2.IMWRITE_JPEG_QUALITY, quality]
                elif fmt == "webp":
                    params = [cv2.IMWRITE_WEBP_QUALITY, quality]
                elif fmt == "png":
                    params = [cv2.IMWRITE_PNG_COMPRESSION, min(9, max(0, (100 - quality) // 10))]
            cv2.imwrite(filepath, frame, params)

        size_kb = os.path.getsize(filepath) / 1024
        print(f"  [{frame_count:5d}] {timestamp_s:8.3f}s → {filename}  ({size_kb:.0f} KB)")

        frame_count += 1
        current_ms += interval_ms

    cap.release()
    print("-" * 50)
    print(f"Fertig! {frame_count} Frames extrahiert nach '{output_dir}/'")


def main():
    parser = argparse.ArgumentParser(
        description="Extrahiert Frames aus einem Video in definierten Zeitintervallen.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Formatempfehlungen:
  webp   ⭐ Bestes Verhältnis Qualität/Größe (Standard)
  png       Verlustfrei, wenn pixelgenaue Reproduktion nötig
  jpg       Kleinste Dateien, gut für Vorschauen
  avif      Modernster Codec, beste Kompression (benötigt pillow-avif)

Beispiele:
  python extract_frames.py video.mp4
  python extract_frames.py video.mp4 --interval 500 --format png
  python extract_frames.py video.mp4 -i 1000 -f jpg -q 85 --max 50
        """,
    )
    parser.add_argument("video", help="Pfad zum Eingabevideo")
    parser.add_argument("-i", "--interval", type=int, default=100, help="Intervall in ms (Standard: 100)")
    parser.add_argument("-o", "--output", default="frames", help="Ausgabeordner (Standard: frames)")
    parser.add_argument("-f", "--format", default="webp", choices=FORMATS.keys(), help="Bildformat (Standard: webp)")
    parser.add_argument("-q", "--quality", type=int, help="Qualität 1-100 (überschreibt Formatstandard)")
    parser.add_argument("--max", type=int, dest="max_frames", help="Maximale Anzahl Frames")

    args = parser.parse_args()

    extract_frames(
        video_path=args.video,
        output_dir=args.output,
        interval_ms=args.interval,
        fmt=args.format,
        quality=args.quality,
        max_frames=args.max_frames,
    )


if __name__ == "__main__":
    main()
