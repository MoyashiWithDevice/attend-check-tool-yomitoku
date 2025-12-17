import csv
import os
from typing import List
from .extractor import StudentInfo

class CSVWriter:
    def write_merged(students: List[StudentInfo], output_path: str):
        """Writes all student info to a single CSV file."""
        fieldnames = ["surname", "name", "full_name", "student_id_full", "student_id_num", "confidence"]
        
        # Ensure directory exists if path has directory component
        dir_name = os.path.dirname(output_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        
        with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            for s in students:
                writer.writerow(s.model_dump())

    @staticmethod
    def write_split(students: List[StudentInfo], original_file_path: str, output_dir: str):
        """Writes student info for a single file to a CSV."""
        if not students:
            return

        base_name = os.path.splitext(os.path.basename(original_file_path))[0]
        output_path = os.path.join(output_dir, f"{base_name}_result.csv")
        fieldnames = ["surname", "name", "full_name", "student_id_full", "student_id_num", "confidence"]
        
        os.makedirs(output_dir, exist_ok=True)
        
        with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for s in students:
                data = s.model_dump()
                del data["file_name"] # Remove file_name as it's redundant in split mode
                writer.writerow(data)
