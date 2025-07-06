from datetime import datetime

def log_processing(file_name, file_url, output_file_name, method):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"{timestamp}, {file_name}, {file_url}, {output_file_name}, {method}\n"
    with open("processing_log.csv", "a") as log_file:
        log_file.write(log_entry)
