"""Small, dependency-free WebVTT parser used before passing text to agents."""
from __future__ import annotations
import re
from dataclasses import dataclass

# Regex flexível que aceita tempos com ou sem as horas (00:00:00.000 ou 00:00.000)
TIMING_LINE = re.compile(r"(?P<start>(?:\d{1,2}:)?\d{1,2}:\d{2}\.\d{3})\s*-->\s*(?P<end>(?:\d{1,2}:)?\d{1,2}:\d{2}\.\d{3})")
TAG = re.compile(r"<[^>]+>")

@dataclass(frozen=True)
class Caption:
    start: str
    end: str
    text: str

def timestamp_seconds(timestamp: str) -> float:
    parts = timestamp.split(":")
    if len(parts) == 3:
        hours, minutes, seconds = parts
    elif len(parts) == 2:
        hours = "0"
        minutes, seconds = parts
    else:
        hours = "0"
        minutes = "0"
        seconds = parts[0]
        
    whole_seconds, milliseconds = seconds.split(".")
    return int(hours) * 3600 + int(minutes) * 60 + int(whole_seconds) + int(milliseconds) / 1000

def process_caption_text(raw_text: str) -> str:
    """Limpa e padroniza as loucuras geradas pelo LLM."""
    # 1. Converte <v Nome> para Nome:
    text = re.sub(r"<v\s+([^>]+)>", r"\1: ", raw_text)
    
    # 2. Converte [Nome]: para Nome: (Para casos como [SPEAKER_SAM]:)
    text = re.sub(r"\[([^\]]+)\]:\s*", r"\1: ", text)
    
    # 3. Remove descrições de áudio/efeitos (ex: [TRAFFIC BUZZ])
    text = re.sub(r"\[.*?\]", "", text)
    
    # 4. Remove a string "SPEAKER_" se o LLM tiver sido repetitivo
    text = re.sub(r"SPEAKER_", "", text)
    
    # 5. Remove tags nativas do VTT (como </v>)
    text = TAG.sub("", text)
    
    # 6. Limpa espaços duplos criados pelas remoções acima
    return re.sub(r"\s+", " ", text).strip()

def parse_vtt(raw_vtt: str) -> list[Caption]:
    """Extract time-stamped spoken captions, rejecting malformed uploads."""
    normalized = raw_vtt.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    
    captions: list[Caption] = []
    lines = normalized.split("\n")
    
    current_start = None
    current_end = None
    current_text = []

    for line in lines:
        line = line.strip()
        
        # Ignora silenciosamente cabeçalhos inventados pelo LLM
        if line.startswith("WEBVTT") or line.startswith("Kind:") or line.startswith("Language:") or line.startswith("Note Date:"):
            continue

        if not line:
            # Fim de um bloco de fala
            if current_start and current_text:
                raw_text = " ".join(current_text)
                clean_text = process_caption_text(raw_text)
                if clean_text:
                    captions.append(Caption(start=current_start, end=current_end, text=clean_text))
            
            current_start = None
            current_end = None
            current_text = []
            continue

        match = TIMING_LINE.search(line)
        if match:
            current_start = match.group("start")
            current_end = match.group("end")
        elif current_start:
            # Se já pegamos o tempo, as próximas linhas são diálogo
            current_text.append(line)

    # Processa o último bloco caso o LLM não tenha deixado linha em branco no final
    if current_start and current_text:
        raw_text = " ".join(current_text)
        clean_text = process_caption_text(raw_text)
        if clean_text:
            captions.append(Caption(start=current_start, end=current_end, text=clean_text))

    if not captions:
        print("[AVISO] Nenhum diálogo legível encontrado. Retornando arquivo seguro.")
        return [Caption(start="00:00:00.000", end="00:00:00.000", text="Nenhum diálogo legível encontrado.")]
        
    return captions

def transcript_from_captions(captions: list[Caption]) -> str:
    return "\n".join(f"[{cue.start}–{cue.end}] {cue.text}" for cue in captions)

def duration_seconds(captions: list[Caption]) -> int:
    """Return the elapsed duration from the first cue start to the last cue end."""
    if len(captions) == 1 and captions[0].text == "Nenhum diálogo legível encontrado.":
        return 0
    return max(0, round(timestamp_seconds(captions[-1].end) - timestamp_seconds(captions[0].start)))

def participants_from_captions(captions: list[Caption]) -> list[str]:
    """Get unique speaker names in first-appearance order from caption text."""
    names: list[str] = []
    for caption in captions:
        possible_name, separator, _ = caption.text.partition(":")
        name = possible_name.strip()
        if separator and name and name not in names:
            names.append(name)
    return names

def format_timestamp(seconds: float) -> str:
    """Format elapsed seconds for display: M:SS, or H:MM:SS past one hour."""
    total = round(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"
