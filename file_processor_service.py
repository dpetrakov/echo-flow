import os
import time
import shutil
import re
import json
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
import subprocess
import os.path
import calendar

def load_config():
    """Load configuration from .env file"""
    load_dotenv()
    return {
        'input_dir': os.getenv('INPUT_DIR', 'input'),
        'output_dir': os.getenv('OUTPUT_DIR', 'output'),
        'check_interval': int(os.getenv('CHECK_INTERVAL', '5'))  # check interval in seconds
    }

def ensure_directories():
    """Create required directories if they don't exist"""
    for dir_name in [config['input_dir'], config['output_dir']]:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            dir_path.mkdir(parents=True)
            print(f"Directory created: {dir_path}")

def log_files_in_dir(directory):
    """Log files in the specified directory"""
    print(f"\n=== Files in {directory} ===")
    dir_path = Path(directory)
    if not dir_path.exists():
        print(f"Directory {directory} does not exist!")
        return
    
    found_files = False
    for file_path in dir_path.glob('*'):
        if file_path.is_file():
            found_files = True
            print(f"File: {file_path.name} ({file_path.stat().st_size} bytes)")
    
    if not found_files:
        print(f"No files found in directory {directory}.")
    print("==========================================\n")

def format_timestamp(seconds):
    """Format time in MM:SS format or HH:MM:SS if over an hour"""
    total_seconds = round(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes}:{seconds:02d}"

def extract_segments_to_txt(json_file, txt_file):
    """Extract segments from JSON and save to TXT"""
    print(f"Extracting segments from {json_file.name}...")
    
    if not json_file.exists():
        print(f"[ERROR] JSON file not found: {json_file}")
        return False
    
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        segments = data.get("segments", [])
        if not segments:
            print("[INFO] No segments found in JSON file.")
            return False
        
        with open(txt_file, "w", encoding="utf-8") as out:
            for seg in segments:
                start = format_timestamp(seg["start"])
                end = format_timestamp(seg["end"])
                speaker = seg.get("speaker", "SPEAKER_??")
                text = seg.get("text", "").strip()
                out.write(f"[{start} - {end}] {speaker}: {text}\n")
        
        print(f"[INFO] Segments with timestamps saved to file: {txt_file.name}")
        return True
    except Exception as e:
        print(f"[ERROR] Error processing JSON: {str(e)}")
        return False

def format_duration_for_filename(seconds):
    """Format duration in MMSS format for filename"""
    total_seconds = round(seconds)
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:02d}{seconds:02d}"

def get_audio_duration(file_path):
    """Get audio duration using ffprobe"""
    try:
        cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
               '-of', 'default=noprint_wrappers=1:nokey=1', str(file_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip())
        return duration
    except Exception as e:
        print(f"Error getting audio duration: {str(e)}")
        return 0

def generate_filename_prefix(timestamp, duration):
    """Generate filename prefix based on date, time and duration"""
    dt = datetime.strptime(timestamp, '%Y%m%d_%H%M%S')
    
    # Extract components
    month_day = dt.strftime('%m%d')  # MMDD format
    day_of_week = calendar.day_name[dt.weekday()][:2].upper()  # First two letters of day name, uppercase
    time_str = dt.strftime('%H%M%S')  # HHMMSS format
    
    # Format duration
    duration_str = format_duration_for_filename(duration)
    
    return f"{month_day}_{day_of_week}_{time_str}_{duration_str}"

def update_bat_file_with_timestamp(timestamp):
    """Update run.bat with timestamp for output filenames"""
    try:
        run_bat_path = Path("run.bat")
        if not run_bat_path.exists():
            print("[ERROR] run.bat file not found")
            return False
        
        # Read the original content
        with open(run_bat_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Create a backup
        with open(run_bat_path.with_suffix(".bak"), "w", encoding="utf-8") as f:
            f.write(content)
        
        # Set environment variable for timestamp
        os.environ["WHISPER_TIMESTAMP"] = timestamp
        
        print(f"[INFO] Set timestamp for WhisperX output files: {timestamp}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to update run.bat: {str(e)}")
        return False

def find_whisperx_outputs(output_dir, file_name, timestamp):
    """Find all files created by WhisperX for the given input file"""
    # List of possible intermediate file extensions
    extensions = [".json", ".txt", ".srt", ".vtt", ".tsv"]
    
    # List of patterns to search for files
    patterns = [
        f"{file_name}.json",  # Standard JSON file
        f"{file_name}_*.json",  # JSON files with any suffix
        f"{file_name}*.txt",   # TXT files
        f"{file_name}*.srt",   # SRT files 
        f"{file_name}*.vtt",   # VTT files
        f"{file_name}*.tsv",   # TSV files
        f"{file_name}_{timestamp}*.txt"  # Formatted TXT file
    ]
    
    result = set()  # Use a set instead of a list to avoid duplicates
    for pattern in patterns:
        for file_path in output_dir.glob(pattern):
            if file_path.is_file():
                # Exclude MD file and original audio file
                if not (file_path.suffix == '.md' or 
                        (file_path.suffix in ['.wav', '.mp3', '.ogg'] and timestamp in file_path.stem)):
                    result.add(file_path)
    
    return list(result)  # Return a list for compatibility

def check_no_speech(output):
    """Check if the output contains 'No active speech found in audio'"""
    return "No active speech found in audio" in output

def group_and_format_dialog(input_file, output_md, original_filename, timestamp, duration):
    """Group and format dialog in Markdown format"""
    print(f"Formatting dialog to Markdown...")
    
    if not input_file.exists():
        print(f"[ERROR] File not found: {input_file}")
        return False
    
    try:
        with input_file.open("r", encoding="utf-8") as f:
            lines = f.readlines()
        
        dialog = []
        current_speaker = None
        current_block = []
        
        for idx, line in enumerate(lines):
            line = line.strip()
            match = re.match(r"\[(.+?) - (.+?)\] (SPEAKER_\d{2}|Speaker \d+): (.+)", line)
            if not match:
                print(f"[WARNING] Line {idx + 1} does not match format: {line}")
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
        
        # Форматированная дата и время для метаданных
        formatted_date = datetime.strptime(timestamp, '%Y%m%d_%H%M%S').strftime('%Y-%m-%d %H:%M:%S')
        
        with output_md.open("w", encoding="utf-8") as out:
            # Добавляем метаданные в формате Obsidian
            out.write("---\n")
            out.write(f"created: {formatted_date}\n")
            out.write(f"original_filename: {original_filename}\n")
            out.write(f"duration: {timedelta(seconds=duration)}\n")
            out.write("---\n\n")
            
            for raw_speaker, blocks in dialog:
                if raw_speaker not in speaker_map:
                    speaker_map[raw_speaker] = f"Speaker {speaker_counter}"
                    speaker_counter += 1
                name = speaker_map[raw_speaker]
                
                # Получаем время начала и окончания всего блока
                block_start = blocks[0][0]
                block_end = blocks[-1][1]
                
                out.write(f"### {name} *[{block_start} - {block_end}]*\n\n")
                for start, end, text in blocks:
                    # Убираем время из каждой строки
                    out.write(f"- {text}\n")
                out.write("\n")
        
        print(f"[DONE] Markdown file saved: {output_md.name}")
        return True
    except Exception as e:
        print(f"[ERROR] Error creating Markdown: {str(e)}")
        return False

def process_file(file_path):
    """Process a single file"""
    try:
        # Get absolute path to the file
        abs_file_path = file_path.resolve()
        file_name = file_path.stem
        file_ext = file_path.suffix
        
        # Create a single timestamp for all files in this processing
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        print(f"\n>>> Starting to process file: {abs_file_path} [Session: {timestamp}]")
        
        # Get audio duration
        duration = get_audio_duration(abs_file_path)
        print(f"Audio duration: {timedelta(seconds=duration)}")
        
        # Generate new filename prefix
        filename_prefix = generate_filename_prefix(timestamp, duration)
        
        # Update run.bat with the timestamp
        update_bat_file_with_timestamp(timestamp)
        
        # Check files in the output directory before processing
        print("Files in output directory before processing:")
        log_files_in_dir(config['output_dir'])
        
        # Run processing through run.bat
        print(f"Running script: run.bat {abs_file_path}")
        subprocess_result = subprocess.run(['run.bat', str(abs_file_path)], 
                                          check=True, 
                                          capture_output=True, 
                                          text=True)
        print(f"run.bat output:\n{subprocess_result.stdout}")
        if subprocess_result.stderr:
            print(f"run.bat errors:\n{subprocess_result.stderr}")
        
        # Check for "No active speech" message
        no_speech_detected = check_no_speech(subprocess_result.stdout)
        
        # Check files in the output directory after processing
        print("Files in output directory after processing:")
        log_files_in_dir(config['output_dir'])
        
        # Process JSON and create Markdown file
        output_dir = Path(config['output_dir'])
        md_file = None  # Initialize variable for MD file
        
        # Search for JSON file (various name patterns possible)
        json_file = None
        json_candidates = list(output_dir.glob(f"{file_name}.json"))
        if json_candidates:
            json_file = json_candidates[0]
            print(f"Found JSON file: {json_file.name}")
        
        if not json_file:
            json_candidates = list(output_dir.glob(f"{file_name}_*.json"))
            if json_candidates:
                json_file = json_candidates[0]
                print(f"Found JSON file with timestamp: {json_file.name}")
        
        if not json_file:
            json_candidates = list(output_dir.glob(f"{file_name}.wav.json"))
            if json_candidates:
                json_file = json_candidates[0]
                print(f"Found JSON file with .wav suffix: {json_file.name}")
        
        # Create names for output files with new naming scheme
        txt_file = output_dir / f"{filename_prefix}_formatted.txt"
        md_file = output_dir / f"{filename_prefix}_transcript.md"
        
        # Create MD file based on JSON, if found
        if json_file and not no_speech_detected:
            print("Found JSON file, starting conversion to Markdown...")
            if extract_segments_to_txt(json_file, txt_file):
                group_and_format_dialog(txt_file, md_file, file_path.name, timestamp, duration)
        else:
            if no_speech_detected:
                print(f"[INFO] No active speech detected in the audio file")
            else:
                print(f"[ERROR] JSON file not found in directory {output_dir}")
        
        # Create a new filename with the new naming scheme
        new_name = f"{filename_prefix}_transcript{file_ext}"
        output_path = Path(config['output_dir']) / new_name
        
        # Move the original file to the output directory
        print(f"\n>>> Moving original file to output directory: {file_path.name} -> {output_path.name}")
        shutil.move(str(file_path), str(output_path))
        print(f"File moved successfully.")
        
        # Delete intermediate files in the output directory
        print("Searching for intermediate files to delete...")
        intermediate_files = find_whisperx_outputs(output_dir, file_name, timestamp)
        
        # Check if MD file was created
        md_created = md_file and md_file.exists()
        
        if intermediate_files:
            print(f"Found {len(intermediate_files)} intermediate files:")
            for intermediate_file in intermediate_files:
                try:
                    # Check if this is a JSON file that should be preserved on error
                    is_json = intermediate_file.suffix.lower() == '.json'
                    if is_json and not md_created and not no_speech_detected:
                        print(f"Preserving JSON file for debugging: {intermediate_file.name}")
                        continue  # Skip deleting JSON file
                        
                    print(f"Deleting intermediate file: {intermediate_file.name}")
                    if intermediate_file.exists():
                        intermediate_file.unlink()
                    else:
                        print(f"File {intermediate_file.name} no longer exists.")
                except Exception as e:
                    print(f"Error deleting file {intermediate_file.name}: {str(e)}")
        else:
            print("No intermediate files found.")
        
        # Check for the final MD file
        if md_created:
            print(f"\n>>> File {file_path.name} processed successfully, Markdown created: {md_file.name}")
        else:
            # Create MD file with error information
            error_md_file = output_dir / f"{filename_prefix}_transcript_error.md"
            try:
                with error_md_file.open("w", encoding="utf-8") as f:
                    # Добавляем метаданные в формате Obsidian
                    f.write("---\n")
                    f.write(f"created: {datetime.strptime(timestamp, '%Y%m%d_%H%M%S').strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"original_filename: {file_path.name}\n")
                    f.write(f"duration: {timedelta(seconds=duration)}\n")
                    f.write(f"error: {'No speech detected' if no_speech_detected else 'Processing error'}\n")
                    f.write("---\n\n")
                    
                    if no_speech_detected:
                        f.write(f"# No speech detected in file {file_path.name}\n\n")
                        f.write(f"Processing date and time: {timestamp.replace('_', ' ')}\n\n")
                        f.write("## File Information\n\n")
                        f.write(f"- Filename: {file_path.name}\n")
                        f.write(f"- Size: {file_path.stat().st_size} bytes\n")
                        f.write(f"- Moved to: {output_path.name}\n\n")
                        f.write("The audio file was processed, but no speech was detected. This could be due to:\n\n")
                        f.write("- Silent audio file\n")
                        f.write("- Very low volume speech\n")
                        f.write("- Non-speech audio content\n")
                        f.write("- Format not compatible with speech recognition\n")
                    else:
                        f.write(f"# Error processing file {file_path.name}\n\n")
                        f.write(f"Processing date and time: {timestamp.replace('_', ' ')}\n\n")
                        
                        # Add information about JSON file if found
                        if json_file and json_file.exists():
                            f.write(f"JSON file preserved for debugging: `{json_file.name}`\n\n")
                        
                        f.write("## Processing Output\n\n")
                        f.write("```\n")
                        if 'subprocess_result' in locals() and subprocess_result:
                            f.write(subprocess_result.stdout)
                            if subprocess_result.stderr:
                                f.write("\n\n### Errors:\n")
                                f.write(subprocess_result.stderr)
                        else:
                            f.write("No processing output available.")
                        f.write("\n```\n\n")
                        
                        f.write("## Possible Error Causes\n\n")
                        f.write("- File format not supported\n")
                        f.write("- File does not contain speech\n")
                        f.write("- Error in speech recognition\n")
                        f.write("- Error in speaker identification\n")
                        
                        f.write("\n## File Information\n\n")
                        f.write(f"- Filename: {file_path.name}\n")
                        f.write(f"- Size: {file_path.stat().st_size} bytes\n")
                        f.write(f"- Moved to: {output_path.name}\n")
                    
                if no_speech_detected:
                    print(f"\n>>> File {file_path.name} contains no speech. Created information Markdown: {error_md_file.name}")
                else:
                    print(f"\n>>> File {file_path.name} processed with errors. Created error information Markdown: {error_md_file.name}")
                
                if json_file and json_file.exists() and not no_speech_detected:
                    print(f"JSON file preserved for debugging: {json_file.name}")
            except Exception as e:
                print(f"Error creating error information MD file: {str(e)}")
        
        return True
    except Exception as e:
        print(f"Error processing file {file_path}: {str(e)}")
        return False

def main():
    """Main service loop"""
    print(f"Service started. Monitoring directory: {config['input_dir']}")
    
    # Create necessary directories at startup
    ensure_directories()
    
    while True:
        try:
            # Check for new files
            input_dir = Path(config['input_dir'])
            for file_path in input_dir.glob('*'):
                if file_path.is_file():
                    # Ignore syncthing temporary files
                    if file_path.name.startswith("~syncthing~") and file_path.name.endswith(".tmp"):
                        print(f"Ignoring syncthing temporary file: {file_path.name}")
                        continue
                        
                    print(f"New file detected: {file_path.name}")
                    process_file(file_path)
            
            # Wait before next check
            time.sleep(config['check_interval'])
            
        except Exception as e:
            print(f"Error in main loop: {str(e)}")
            time.sleep(config['check_interval'])

if __name__ == "__main__":
    config = load_config()
    main() 


    # TODO: удалять аудио файлы старше недели из processed
    # TODO: 
