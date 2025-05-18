from vosk import Model, KaldiRecognizer
import pyaudio
from rapidfuzz import process
import queue
import json

# def voice_listener(songs, trigger_manager):
#     print("🎤 Voice listener started")
#     model = vosk.Model("models/vosk-model-small-en-us-0.15")
#     q = queue.Queue()
#     samplerate = 16000

#     def callback(indata, frames, time, status):
#         q.put(bytes(indata))

#     with sd.RawInputStream(samplerate=samplerate, blocksize=8000, dtype='int16',
#                            channels=1, callback=callback):
#         rec = vosk.KaldiRecognizer(model, samplerate)
#         while True:
#             data = q.get()
#             if rec.AcceptWaveform(data):
#                 result = json.loads(rec.Result())
#                 text = result.get("text", "").lower()
#                 print(f"🗣️ Heard: {text}")
#                 if text:
#                     for song in songs:
#                         # doesnt handle fuzzy matches
#                         if "triggers" in song and any(phrase in text for phrase in song["triggers"]):
#                             trigger_manager.trigger_song(song, source="Voice")
#                             break

def voice_listener(songs, callback):
    try:
        print("🔊 Starting voice listener thread")
        
        # Build trigger map first
        trigger_map = {}
        for index, song in enumerate(songs):
            for phrase in song.get("triggers", []):
                trigger_map[phrase.lower()] = index

        def match_song(transcript):
            transcript = transcript.lower()

            # First, try direct substring matches
            for trigger, index in trigger_map.items():
                if trigger in transcript:
                    return index

            # Fallback: fuzzy match against trigger keys
            match = process.extractOne(transcript, list(trigger_map.keys()), score_cutoff=70)
            
            if match:
                best_match, score, _ = match
                return trigger_map[best_match]

            # No match found
            return None



        print("Loading Vosk model...")
        model = Model("models/vosk-model-small-en-us-0.15")
        print("Model loaded")

        recognizer = KaldiRecognizer(model, 16000)
        print("Recognizer created")

        print("Creating PyAudio object...")
        p = pyaudio.PyAudio()
        print("Opening stream...")
        stream = p.open(
            format=pyaudio.paInt16,        # 16-bit signed int
            channels=1,                    # Mono channel
            rate=16000,                    # Sample rate (Hz)
            input=True,                    # Input stream
            frames_per_buffer=8000         # Buffer size
        )

        print("Starting stream...")
        stream.start_stream()
        print("Stream started ✅")

        while True:
            try:
                data = stream.read(4000, exception_on_overflow=False)
            except Exception as e:
                print("⚠️ Error reading audio stream:", e)
                continue

            if recognizer.AcceptWaveform(data):
                result = recognizer.Result()
                print("Recognized:", result)
                # TODO: match and trigger birds
                index = match_song(result)
                if index:
                    callback(index)
            else:
                print("Partial:", recognizer.PartialResult())

    except Exception as e:
        print("❌ Exception in voice_listener thread:", e)
        import traceback
        traceback.print_exc()
