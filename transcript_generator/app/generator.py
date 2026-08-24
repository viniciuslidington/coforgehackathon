import os
import random
import time
from datetime import datetime, timedelta
import requests
import boto3
import logging
from app.config import GEMINI_KEY, R2_ENDPOINT, R2_ACCESS_KEY, R2_SECRET_KEY, BUCKET_NAME

logger = logging.getLogger("transcript-generator")

# ==========================================
# PARAMETERS
# ==========================================
TRADERS_EN = ["John", "Mike", "Sarah", "David", "Emma", "James", "William", "Olivia", "Robert", "Mary", "Alex", "Chris", "Katie", "Sam", "Jessica"]
TOPICS_CONVO = ["S&P 500 rebalancing and sector rotation", "Tech sector earnings", "Fed interest rate hike expectations", "Treasury yields inversion", "Crypto volatility", "Forex EUR/USD parity", "Oil futures"]
TOPICS_HOOT = ["Massive block trade alert on SPY", "Order flow imbalance", "Breaking news squawk on CPI", "Margin call liquidations", "Dark pool activity"]
LANGUAGES = ["Spanish", "French", "German", "Mandarin", "Japanese", "Italian", "Russian"]
SIZES = [("short", "around 1 minute, 5 to 8 lines"), ("medium", "around 3 minutes, 15 to 20 lines"), ("long", "around 5 minutes, 30 to 40 lines")]

OUTPUT_DIR = "/tmp/transcripts_vtt"

def get_s3_client():
    return boto3.client(
        's3',
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_KEY,
        region_name='auto'
    )

def get_random_business_day() -> str:
    start_date = datetime(2025, 1, 1)
    end_date = datetime(2026, 1, 1)
    while True:
        random_days = random.randint(0, (end_date - start_date).days)
        date_candidate = start_date + timedelta(days=random_days)
        if date_candidate.weekday() < 5:
            return date_candidate.strftime("%Y-%m-%d")

def call_gemini_direct(prompt: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent?key={GEMINI_KEY}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 16000, "temperature": 0.8}
    }
    
    response = requests.post(url, headers=headers, json=payload, timeout=120)
    if response.status_code == 200:
        return response.json()['candidates'][0]['content']['parts'][0]['text'].replace('```vtt', '').replace('```', '').strip()
    elif response.status_code == 429:
        raise Exception("429")
    else:
        raise Exception(f"Error {response.status_code}: {response.text}")

def process_single_transcript(file_id: int, call_type: str, s3_client):
    business_date = get_random_business_day()
    
    if call_type == "hoot_call":
        trader_1 = random.choice(TRADERS_EN)
        topic = random.choice(TOPICS_HOOT)
        prompt = f"""Generate an audio transcript in strict .VTT format of a 'Hoot Call' (a squawk box broadcast to the trading floor).
        Speaker: {trader_1} (The Announcer/Squawk)
        Topic: {topic}
        Tone: Urgent, fast-paced.
        Length: Short (3 to 6 broadcast lines).
        Note Date: {business_date}
        Output ONLY valid VTT code."""
        file_name = f"{file_id:05d}_hootcall_{trader_1}.vtt"
        
    else:
        # 1. Randomly decide if it's a 2, 3, or 4 person call
        num_participants = random.randint(2, 4)
        active_traders = random.sample(TRADERS_EN, num_participants)

        # 2. Find who is NOT in the call to be mentioned
        absent_pool = list(set(TRADERS_EN) - set(active_traders))
        mentioned_traders = random.sample(absent_pool, random.randint(1, 2))

        topic = random.choice(TOPICS_CONVO)

        prompt = f"""Generate an EXTENSIVE audio transcript in strict .VTT format of a multi-person TRADING desk conversation.

        Parameters:
        - Language: English
        - Active Participants on the call: {', '.join(active_traders)}
        - Traders NOT on the call who MUST be mentioned: {', '.join(mentioned_traders)}
        - Core Topic: {topic}
        - Note Date: {business_date}

        CONVERSATION TIMELINE (FLUID GUIDE):
        Follow this general pacing to ensure the conversation naturally reaches around 15 minutes. These are soft boundaries, let the dialogue flow organically through these phases:
        - 00:00 to ~04:00: The Open. Casual banter, reviewing overnight markets, and introducing the topic '{topic}'.
        - ~04:00 to ~09:00: Deep Dive. Extensive back-and-forth debating the core topic, analyzing terminal data, and mentioning absent traders.
        - ~09:00 to ~12:00: The Catalyst. A sudden piece of news, a block trade alert, or a disagreement shifts the tone to urgent.
        - ~12:00 to ~15:00: The Resolution. Deciding on execution strategies, adjusting VaR limits, and wrapping up the call.

        CRITICAL RULES FOR NATURAL CONVERSATION & TIMESTAMPS:
        1. NO ROBOTIC PACING: Timestamps MUST vary based on text length. A short "Yeah" takes 1-2 seconds. A long explanation takes 10-25 seconds.
        2. MESSY DIALOGUE: Real traders interrupt each other, use filler words (uh, um, right), trail off, and talk over one another.
        3. GAP TIMES: Leave micro-gaps (0.5 to 1 second) between speakers, or make them overlap slightly for interruptions.
        4. COMPLETE THE TIMELINE: You MUST generate enough dialogue to chronologically reach the ~15:00 minute mark. Do not end the conversation early.

        VTT Rules:
        - Start with WEBVTT
        - Timestamps format: 00:MM:SS.mmm --> 00:MM:SS.mmm
        - Speaker format: <v SpeakerName> Dialogue here.
        - Output ONLY valid VTT code. Do not wrap in markdown or add extra explanations."""
        
        # Name the file indicating the number of participants for your own tracking
        file_name = f"{file_id:05d}_convo_{num_participants}p_{active_traders[0]}.vtt"

    local_path = f"{OUTPUT_DIR}/{file_name}"
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for attempt in range(3):
        try:
            logger.info(f"[{file_id}] Requesting text from Gemini (Attempt {attempt+1})...")
            vtt_text = call_gemini_direct(prompt)
            
            with open(local_path, "w", encoding="utf-8") as f:
                f.write(vtt_text)
            
            logger.info(f"[{file_id}] Uploading to Cloudflare R2...")
            s3_client.upload_file(local_path, BUCKET_NAME, file_name)
            os.remove(local_path)
            logger.info(f"[{file_id}] Successfully processed and uploaded {file_name}")
            time.sleep(5) # Delay entre chamadas para evitar rate limit
            return
            
        except Exception as e:
            if "429" in str(e):
                logger.warning(f"[{file_id}] API Rate Limit (429). Pausing for 20s...")
                time.sleep(20)
            else:
                logger.error(f"[{file_id}] Failed {file_name}: {e}")
                time.sleep(5)

def run_batch_generation(total_convos: int = 56, total_hoots: int = 34):
    logger.info("Starting background batch generation...")
    s3_client = get_s3_client()
    file_types = ["conversation_en"] * total_convos + ["hoot_call"] * total_hoots
    random.shuffle(file_types)

    for i, call_type in enumerate(file_types, 1):
        process_single_transcript(i, call_type, s3_client)
        
    logger.info("Batch generation complete!")