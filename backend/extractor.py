import re
import math
from typing import List, Optional
from pydantic import BaseModel, Field
from .config_schema import AttendCheckConfig
from yomitoku.schemas import DocumentAnalyzerSchema, WordPrediction

class StudentInfo(BaseModel):
    student_id_full: str  # e.g. abc-1234567
    student_id_num: str   # e.g. 1234567
    surname: str          # e.g. Yamada
    name: str             # e.g. Taro
    full_name: str        # e.g. Yamada Taro
    confidence: float
    file_name: Optional[str] = None

class Extractor:
    def __init__(self, config: AttendCheckConfig):
        self.config = config
        self.id_pattern = re.compile(self.config.student_id_pattern)
        if self.config.name_exclusion_pattern:
            self.name_exclusion_pattern = re.compile(self.config.name_exclusion_pattern)
        else:
            self.name_exclusion_pattern = None

    def extract(self, result: DocumentAnalyzerSchema, file_name: str = "") -> List[StudentInfo]:
        students = []
        words = result.words
        
        # 1. Identify Student ID candidates and their containers
        # The ID might be part of a larger string: "Name(prefix-ID)" or "Name (prefix-ID)"
        # Or isolated "prefix-ID"
        
        # We look for the ID pattern *inside* word content.
        # But attend_check_config pattern is anchored with ^$.
        # We need an unanchored search pattern.
        # However, self.id_pattern is likely stricter.
        # Build search pattern dynamically from config prefix
        
        prefix = re.escape(self.config.student_id_prefix)
        id_search_pattern = re.compile(rf"({prefix}\d+)")
        
        candidates = []
        
        for word in words:
            # Check if this word *contains* an ID
            match = id_search_pattern.search(word.content)
            if match:
                if word.rec_score >= self.config.confidence_threshold:
                    candidates.append((word, match))

        seen_ids = set()

        for word, match in candidates:
            full_id = match.group(1)
            
            if full_id in seen_ids:
                continue
            seen_ids.add(full_id)
            
            # Extract numeric part (remove non-digits)
            id_num = re.sub(r"\D", "", full_id)
            
            # Find Name
            # Strategy:
            # 1. Check if name is in the SAME word buffer (e.g. "Yamada(prefix-123)")
            # 2. If not, look LEFT of the ID (because format is Name(ID))
            
            # Content before ID match start
            pre_id_content = word.content[:match.start()]
            
            raw_name = ""
            
            # Clean up pre_id_content (remove parens if they wrap the ID)
            # e.g. "Yamada(prefix-123" -> pre="Yamada("
            clean_pre = pre_id_content.strip()
            if clean_pre and clean_pre.endswith("("):
                clean_pre = clean_pre[:-1].strip()
            
            if clean_pre:
                raw_name = clean_pre
            else:
                # Look for words to the left
                raw_name = self._find_name_at_left(word, words)

            # Parse Name components
            surname, first_name, full_name = self._parse_name(raw_name)
            
            students.append(StudentInfo(
                student_id_full=full_id,
                student_id_num=id_num,
                surname=surname,
                name=first_name,
                full_name=full_name,
                confidence=word.rec_score,
                file_name=file_name
            ))

        return students

    def _find_name_at_left(self, id_word: WordPrediction, all_words: List[WordPrediction]) -> str:
        """
        Find name candidates to the LEFT of the ID.
        """
        id_box = id_word.points
        id_cy = (id_box[0][1] + id_box[2][1]) / 2
        id_height = abs(id_box[2][1] - id_box[0][1])
        id_left_x = min(p[0] for p in id_box)
        
        candidates = []
        for word in all_words:
            if word == id_word: continue
            
            # Exclusion check
            if self.name_exclusion_pattern and self.name_exclusion_pattern.search(word.content):
                continue
            
            # Skip if it looks like an ID
            if self.config.student_id_prefix and self.config.student_id_prefix in word.content:
                continue

            wb = word.points
            w_cy = (wb[0][1] + wb[2][1]) / 2
            w_right_x = max(p[0] for p in wb)
            
            # Check vertical alignment
            if abs(w_cy - id_cy) < (id_height * 0.8):
                # Check if it is to the LEFT
                if w_right_x < id_left_x:
                    candidates.append((word, w_right_x))
        
        # Sort by distance (right-most first, closest to ID)
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        name_parts = []
        last_x = id_left_x
        
        # Take up to 2 closest words? or just 1? 
        # Names can be "Yamada Taro" (2 words)
        for word, x in candidates:
            # Distance check
            dist = last_x - x
            # If distance is too big, maybe it's not the name
            if dist > id_height * 5: # relaxed threshold
                break
            
            # Prepend because scanning right-to-left
            name_parts.insert(0, word.content)
            last_x = min(p[0] for p in word.points)
            
            if len(name_parts) >= 2: break # Limit to 2 words usually

        return " ".join(name_parts)

    def _parse_name(self, raw_name: str):
        """
        Parse raw name string into surname, name, full_name.
        Handles alphabet exception.
        """
        # Clean up
        clean = raw_name.strip()
        clean = re.sub(r"[()]", "", clean) # Remove stray parens
        
        if not clean:
            return "", "", ""
            
        # Check if alphabet (regex: contains mainly a-zA-Z)
        # Using a simple heuristic: if >50% chars are ascii alpha
        alpha_count = sum(1 for c in clean if c.isalpha() and c.isascii())
        total_len = len(clean)
        is_alpha = (alpha_count / total_len) > 0.5 if total_len > 0 else False
        
        if is_alpha:
            return "", "", clean # Surname/Name empty, only Full Name
        
        # Japanese Name Parsing
        # Split by space (ideographic or ascii)
        # Regex split by whitespace
        parts = re.split(r"\s+|　", clean)
        parts = [p for p in parts if p] # filter empty
        
        if len(parts) >= 2:
            surname = parts[0]
            first_name = "".join(parts[1:]) # Join rest as first name
            full_name = f"{surname} {first_name}"
            return surname, first_name, full_name
        else:
            # Single word name -> Assume it's just Surname?? Or Full Name?
            # Requirement: "姓 名(prefix-ID)" -> implied space separation.
            # If no space, we can't reliably split.
            # Maybe return as full name only? Or put all in Surname?
            # Let's put in full_name, leave others empty or duplicate?
            # User said: "姓 名を空白にし、姓と名のみ出力するようにします" for ALPHABET.
            # For Japanese without space, it's ambiguous.
            # Let's assume input needs space. If no space, treat as full name only?
            # Or treat as Surname=Full?
            # Let's treat as Full Name only to be safe.
            return "", "", clean
