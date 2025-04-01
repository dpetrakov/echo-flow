#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import shutil
import logging
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("file_monitor.log"),
        logging.StreamHandler()
    ]
)

# Load environment variables from .env file
load_dotenv()

# Get variables from .env
input_dir = os.getenv("INPUT_DIR")
monitored_dir = os.getenv("MONITORED_DIR")
min_file_size = int(os.getenv("MIN_FILE_SIZE_KB", "100")) * 1024  # Size in KB
check_interval = int(os.getenv("CHECK_INTERVAL", "5"))  # Check interval in seconds
output_dir = os.getenv("OUTPUT_DIR")  # Directory for output data (transcripts)

def safe_copy_file(src, dst):
    """Safe file copying using cp to bypass access restrictions"""
    try:
        # Use cp command to bypass access restrictions in macOS
        result = subprocess.run(['cp', src, dst], capture_output=True, text=True)
        
        if result.returncode != 0:
            logging.error(f"Error copying file with cp: {result.stderr}")
            return False
        return True
    except Exception as e:
        logging.error(f"Error running cp command: {str(e)}")
        return False

def safe_delete_file(file_path):
    """Safe file deletion"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logging.info(f"File successfully deleted: {file_path}")
            return True
        else:
            logging.warning(f"File does not exist: {file_path}")
            return False
    except Exception as e:
        logging.error(f"Error deleting file {file_path}: {str(e)}")
        return False

def process_pdf_file(file_path):
    """Process PDF file using marker_single"""
    try:
        logging.info(f"Starting PDF file processing: {file_path}")
        
        # Get Gemini API key from .env file
        gemini_api_key = os.getenv("GEMENI_API_KEY")
        
        if not gemini_api_key:
            logging.warning("Gemini API key not found in .env file. Processing will be done without using LLM.")
        
        # Optimized parameters for marker_single
        command = [
            'marker_single',
            str(file_path),
            '--output_dir', output_dir,
            '--output_format', 'markdown',
            '--disable_tqdm',               # Disable progress bars for background process
            '--max_concurrency', '3'        # Optimal number of parallel requests
        ]
        
        # If Gemini API key is available, add parameters for using LLM
        if gemini_api_key:
            command.extend([
                '--use_llm',                  # Enable LLM for better quality
                '--gemini_api_key', gemini_api_key,
                '--model_name', 'gemini-2.0-flash'  # Fast model with good quality
            ])
        
        logging.info(f"Executing command: {' '.join(command)}")
        
        result = subprocess.run(
            command,
            capture_output=True, 
            text=True
        )
        
        if result.returncode != 0:
            logging.error(f"Error processing PDF: {result.stderr}")
            return False
        
        logging.info(f"PDF file successfully processed: {file_path}")
        return True
    except Exception as e:
        logging.error(f"Error running marker_single: {str(e)}")
        return False

def get_file_size(file_path):
    """Get file size"""
    try:
        # Use ls -l command to check file size
        result = subprocess.run(['ls', '-l', str(file_path)], capture_output=True, text=True)
        if result.returncode != 0:
            logging.error(f"Failed to get file information: {result.stderr}")
            return -1
        
        # Parse file size from ls -l output
        try:
            file_size = int(result.stdout.split()[4])
            return file_size
        except (IndexError, ValueError):
            logging.error(f"Failed to determine file size: {result.stdout}")
            return -1
    except Exception as e:
        logging.error(f"Error getting file size for {file_path}: {str(e)}")
        return -1

class FileMonitorHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        # Dictionary to track already processed files
        self.processed_files = {}
    
    def on_created(self, event):
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        
        # Check if we've already processed this file
        if str(file_path) in self.processed_files:
            return
        
        # Small delay to allow the file to be fully written
        time.sleep(1)
        
        file_suffix = file_path.suffix.lower()
        
        # Processing WAV files
        if file_suffix == '.wav':
            self.handle_wav_file(file_path)
        # Processing PDF files
        elif file_suffix == '.pdf':
            self.handle_pdf_file(file_path)
        # Processing TXT files - do through on_modified,
        # as text files may be appended after creation
        elif file_suffix == '.txt' and file_path.name.endswith('_formatted.txt'):
            # Mark file as pending for processing on modification
            self.processed_files[str(file_path)] = "pending"
    
    def on_modified(self, event):
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        file_suffix = file_path.suffix.lower()
        
        # Process only TXT files with specific format
        if file_suffix == '.txt' and file_path.name.endswith('_formatted.txt'):
            # Check file status (if it was created earlier)
            if str(file_path) in self.processed_files and self.processed_files[str(file_path)] == "pending":
                logging.info(f"File modified and ready for processing: {file_path}")
                
                # Wait to ensure the file is no longer being modified
                time.sleep(3)
                
                # Process the file
                self.handle_txt_file(file_path)
                
                # Mark file as processed
                self.processed_files[str(file_path)] = "processed"
    
    def handle_wav_file(self, file_path):
        """Process WAV file"""
        try:
            file_size = get_file_size(file_path)
            if file_size < 0:
                return
            
            if file_size >= min_file_size:
                # Copy file to INPUT_DIR
                dest_path = os.path.join(input_dir, file_path.name)
                logging.info(f"Copying {file_path} (size: {file_size/1024:.2f} KB) to {dest_path}")
                
                if safe_copy_file(str(file_path), dest_path):
                    logging.info(f"WAV file successfully copied: {file_path.name}")
                    
                    # Delete original file after successful copy
                    if safe_delete_file(str(file_path)):
                        logging.info(f"Original WAV file deleted: {file_path}")
                    else:
                        logging.error(f"Failed to delete original WAV file: {file_path}")
                else:
                    logging.error(f"Failed to copy WAV file: {file_path}")
            else:
                logging.info(f"File {file_path} is too small ({file_size/1024:.2f} KB < {min_file_size/1024} KB)")
        except Exception as e:
            logging.error(f"Error processing WAV file {file_path}: {str(e)}")
    
    def handle_pdf_file(self, file_path):
        """Process PDF file"""
        try:
            file_size = get_file_size(file_path)
            if file_size < 0:
                return
            
            # Size check may be optional for PDF files
            if file_size >= min_file_size:
                logging.info(f"Detected PDF file {file_path} (size: {file_size/1024:.2f} KB)")
                
                # Process PDF file using marker_single
                if process_pdf_file(file_path):
                    logging.info(f"PDF file successfully processed: {file_path.name}")
                    
                    # Delete original file after successful processing
                    if safe_delete_file(str(file_path)):
                        logging.info(f"Original PDF file deleted: {file_path}")
                    else:
                        logging.error(f"Failed to delete original PDF file: {file_path}")
                else:
                    logging.error(f"Failed to process PDF file: {file_path}")
            else:
                logging.info(f"PDF file {file_path} is too small ({file_size/1024:.2f} KB < {min_file_size/1024} KB)")
        except Exception as e:
            logging.error(f"Error processing PDF file {file_path}: {str(e)}")

    def handle_txt_file(self, file_path):
        """Process TXT file (automatic deletion after creation)"""
        try:
            # Additional check if file is formatted text
            if file_path.name.endswith('_formatted.txt'):
                logging.info(f"Detected TXT file {file_path}, will be deleted")
                
                # Small delay to allow time for file operations to complete
                time.sleep(2)
                
                # Delete TXT file
                if safe_delete_file(str(file_path)):
                    logging.info(f"TXT file successfully deleted: {file_path}")
                else:
                    logging.error(f"Failed to delete TXT file: {file_path}")
        except Exception as e:
            logging.error(f"Error processing TXT file {file_path}: {str(e)}")

def start_monitoring():
    logging.info(f"Starting directory monitoring: {monitored_dir}")
    logging.info(f"WAV files will be copied to: {input_dir}")
    logging.info(f"PDF files will be processed with output to: {output_dir}")
    logging.info(f"Minimum file size: {min_file_size/1024} KB")
    
    # Check directory existence
    if not os.path.exists(monitored_dir):
        logging.error(f"Monitored directory does not exist: {monitored_dir}")
        return
        
    if not os.path.exists(input_dir):
        logging.error(f"Target directory for WAV does not exist: {input_dir}")
        return
    
    if not os.path.exists(output_dir):
        logging.error(f"Output directory for PDF does not exist: {output_dir}")
        return
    
    # Create event handler and observer
    event_handler = FileMonitorHandler()
    observer = Observer()
    observer.schedule(event_handler, monitored_dir, recursive=False)
    
    # Start observer in separate thread
    observer.start()
    
    try:
        logging.info("Monitoring started. Press Ctrl+C to stop.")
        while True:
            time.sleep(check_interval)
    except KeyboardInterrupt:
        observer.stop()
    
    observer.join()
    logging.info("Monitoring stopped.")

if __name__ == "__main__":
    start_monitoring() 