import os
import re
import json
import subprocess
from pathlib import Path
from datetime import timedelta

# === CONFIG ===
AUDIO_NAME = "output2.wav"
INPUT_DIR = Path("input")  # directory with input .wav file
OUTPUT_DIR = Path("output")  # all outputs (.json, .txt, .md) will go here
RAW_JSON = OUTPUT_DIR / "output2.json"
RAW_TXT = OUTPUT_DIR / "output2.txt"
FORMATTED_JSON_TXT = OUTPUT_DIR / f"{AUDIO_NAME}.formatted_dialog.txt"
MERGED_MD = OUTPUT_DIR / f"{AUDIO_NAME}.merged.md"
RUN_BAT = "run.bat"


def format_timestamp(seconds):
    return str(timedelta(seconds=round(seconds, 2)))


def run_whisper_bat():
    print(f"[INFO] Running: {RUN_BAT}")
    audio_path = INPUT_DIR / AUDIO_NAME
    result = subprocess.run([RUN_BAT, str(audio_path)], shell=True)
    if result.returncode != 0:
        print(f"[ERROR] Failed to run {RUN_BAT}")
        exit(1)
    print("[INFO] Transcription completed.")


def extract_segments_to_txt():
    if not RAW_JSON.exists():
        print(f"[ERROR] JSON not found: {RAW_JSON}")
        return

    with open(RAW_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    segments = data.get("segments", [])
    if not segments:
        print("[INFO] No segments found in JSON.")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(FORMATTED_JSON_TXT, "w", encoding="utf-8") as out:
        for seg in segments:
            start = format_timestamp(seg["start"])
            end = format_timestamp(seg["end"])
            speaker = seg.get("speaker", "SPEAKER_??")
            text = seg.get("text", "").strip()
            out.write(f"[{start} - {end}] {speaker}: {text}\n")
    print(f"[INFO] Saved timestamped segments to: {FORMATTED_JSON_TXT}")


def group_and_format_dialog(input_file, output_md):
    print(f"[INFO] Reading: {input_file}")
    if not input_file.exists():
        print(f"[ERROR] File not found: {input_file}")
        return

    with input_file.open("r", encoding="utf-8") as f:
        lines = f.readlines()

    dialog = []
    current_speaker = None
    current_block = []

    for idx, line in enumerate(lines):
        line = line.strip()
        match = re.match(r"\[(.+?) - (.+?)\] (SPEAKER_\d{2}|Speaker \d+): (.+)", line)
        if not match:
            print(f"[WARNING] Line {idx + 1} did not match format: {line}")
            continue

        start, end, speaker, text = match.groups()
        if speaker != current_speaker:
            if current_block:
                dialog.append((current_speaker, current_block))
            current_speaker = speaker
            current_block = [(start, end, text)]
        else:
            current_block.append((start, end, text))

    if current_block:
        dialog.append((current_speaker, current_block))

    speaker_map = {}
    speaker_counter = 1

    with output_md.open("w", encoding="utf-8") as out:
        for raw_speaker, blocks in dialog:
            if raw_speaker not in speaker_map:
                speaker_map[raw_speaker] = f"Speaker {speaker_counter}"
                speaker_counter += 1
            name = speaker_map[raw_speaker]
            out.write(f"### {name}\n\n")
            for start, end, text in blocks:
                out.write(f"- **[{start} - {end}]** {text}\n")
            out.write("\n")

    print(f"[DONE] Merged Markdown saved to: {output_md}")


if __name__ == "__main__":
    run_whisper_bat()
    extract_segments_to_txt()
    group_and_format_dialog(FORMATTED_JSON_TXT, MERGED_MD)