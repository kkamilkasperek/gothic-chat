import csv
import io
import json
import re
from pathlib import Path

from transformers import AutoTokenizer

MAX_TOKENS = 1024
MODEL_NAME = "BAAI/bge-m3"
INPUT_DIR = Path("data/parsed_json_examples")
OUTPUT_DIR = Path("data/chunks_examples")

# Global tokenizer instance to avoid loading it multiple times
_tokenizer = None

def get_tokenizer():
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    return _tokenizer

def process_article(data: dict) -> list[dict]:
    chunks = []
    title = data.get("title", "")
    article_type = data.get("type", "unknown")
    categories = data.get("categories", [])
    
    base_metadata = {
        "title": title,
        "type": article_type,
        "categories": categories
    }
    
    # 1. Process Basic Info (Infobox, Languages, Meta Templates)
    has_infobox = "infobox" in data and data["infobox"]
    has_languages = "languages" in data and data["languages"]
    has_meta = "meta_templates" in data and data["meta_templates"]
    
    if has_infobox or has_languages or has_meta:
        info_chunk = _process_basic_info(title, data.get("infobox", {}), data.get("languages", {}), data.get("meta_templates", []))
        if info_chunk:
            meta = base_metadata.copy()
            meta["section"] = "Informacje Podstawowe"
            context_prefix = f"Tytuł: {title}\nSekcja: Informacje Podstawowe\n\n"
            chunks.extend(_split_if_needed(info_chunk, meta, context_prefix))
            
    # 2. Process Sections
    for section in data.get("sections", []):
        chunks.extend(_process_section(title, section, [section.get("title", "")], base_metadata))
        
    # Add chunk index
    for i, chunk in enumerate(chunks):
        chunk["metadata"]["chunk_index"] = i
        
    return chunks

def _process_basic_info(title: str, infobox: dict, languages: dict, meta_templates: list) -> str:
    exclude_keys = {"obraz", "grafika", "ikona"}
    lines = [f"Tytuł: {title}"]
    
    if infobox:
        lines.append("Podstawowe informacje:")
        for k, v in infobox.items():
            if k.lower() not in exclude_keys:
                # Handle lists in infobox values
                val_str = ", ".join(v) if isinstance(v, list) else str(v)
                lines.append(f"- {k}: {val_str}")
                
    if meta_templates:
        lines.append("Dodatkowe informacje:")
        for tpl in meta_templates:
            name = tpl.get("name", "")
            params = tpl.get("params", {})
            if params:
                param_str = ", ".join(f"{k}: {v}" for k, v in params.items())
                lines.append(f"- {name} ({param_str})")
            else:
                lines.append(f"- {name}")
                
    if languages:
        lines.append("Inne języki:")
        for lang_code, lang_title in languages.items():
            lines.append(f"- {lang_code}: {lang_title}")
            
    return "\n".join(lines)

def _process_section(title: str, section: dict, hierarchy: list[str], base_metadata: dict) -> list[dict]:
    chunks = []
    text = section.get("text", "")
    
    if text:
        context = f"Tytuł: {title}\nSekcja: {' > '.join(hierarchy)}\n\n"
        full_text = context + text
        
        meta = base_metadata.copy()
        meta["section"] = " > ".join(hierarchy)
        
        chunks.extend(_split_if_needed(full_text, meta, context))
        
    # Process subsections recursively
    for sub in section.get("subsections", []):
        chunks.extend(_process_section(title, sub, hierarchy + [sub.get("title", "")], base_metadata))
        
    return chunks



def _split_if_needed(text: str, metadata: dict, context_prefix: str = "") -> list[dict]:
    tokenizer = get_tokenizer()
    tokens = tokenizer.encode(text, add_special_tokens=False)
    if len(tokens) <= MAX_TOKENS:
        return [{"text": text, "metadata": metadata}]
        
    # Hierarchical split logic: \n\n -> \n -> sentences
    chunks = []
    content_to_split = text[len(context_prefix):] if text.startswith(context_prefix) else text
    paragraphs = content_to_split.split("\n\n")
    
    current_chunk_text = context_prefix
    for para in paragraphs:
        para_with_newline = para + "\n\n"
        test_text = current_chunk_text + para_with_newline
        if len(tokenizer.encode(test_text, add_special_tokens=False)) <= MAX_TOKENS:
            current_chunk_text = test_text
        else:
            if current_chunk_text != context_prefix:
                chunks.append({"text": current_chunk_text.strip(), "metadata": metadata.copy()})
            
            # If a single paragraph is too long, we split by single newline
            if len(tokenizer.encode(context_prefix + para, add_special_tokens=False)) > MAX_TOKENS:
                lines = para.split("\n")
                sub_chunk_text = context_prefix
                for line in lines:
                    line_with_newline = line + "\n"
                    test_line = sub_chunk_text + line_with_newline
                    if len(tokenizer.encode(test_line, add_special_tokens=False)) <= MAX_TOKENS:
                        sub_chunk_text = test_line
                    else:
                        if sub_chunk_text != context_prefix:
                            chunks.append({"text": sub_chunk_text.strip(), "metadata": metadata.copy()})
                        sub_chunk_text = context_prefix + line_with_newline
                current_chunk_text = sub_chunk_text + "\n" # Prepare for next paragraph
            else:
                current_chunk_text = context_prefix + para_with_newline

    if current_chunk_text.strip() != context_prefix.strip():
        chunks.append({"text": current_chunk_text.strip(), "metadata": metadata.copy()})
        
    return chunks

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Loading tokenizer... Max tokens: {MAX_TOKENS}")
    get_tokenizer()  # Pre-load tokenizer

    json_files = list(INPUT_DIR.glob("*.json"))
    print(f"Found {len(json_files)} articles to process.")

    for i, file_path in enumerate(json_files, 1):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            chunks = process_article(data)
            
            out_file = OUTPUT_DIR / file_path.name
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(chunks, f, ensure_ascii=False, indent=2)
                
            txt_dir = OUTPUT_DIR / "txt" / file_path.stem
            txt_dir.mkdir(parents=True, exist_ok=True)
            for j, chunk in enumerate(chunks):
                with open(txt_dir / f"chunk_{j}.txt", "w", encoding="utf-8") as f:
                    f.write(chunk["text"])
                
            print(f"[{i}/{len(json_files)}] Processed {file_path.name} -> {len(chunks)} chunks")
            
        except Exception as e:
            print(f"Error processing {file_path.name}: {e}")

if __name__ == "__main__":
    main()
