import os
import json
from src.dreaming.filters import clean_and_compress_trace_runs

class DreamReader:
    def load_trace(self, trace_path: str) -> dict:
        """
        Reads raw trace.jsonl, filters and compresses events,
        and returns a serializable DreamSessionBundle dictionary.
        """
        if not os.path.exists(trace_path):
            raise FileNotFoundError(f"Trace file not found: {trace_path}")
            
        runs = []
        raw_size = os.path.getsize(trace_path)
        
        with open(trace_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        runs.append(json.loads(line))
                    except Exception as e:
                        print(f"Error parsing trace line: {e}")
                        
        compressed_runs = clean_and_compress_trace_runs(runs)
        
        bundle = {
            "source_trace": trace_path,
            "raw_events_count": len(runs),
            "compressed_events_count": len(compressed_runs),
            "runs": compressed_runs
        }
        
        # Calculate compression ratio
        bundle_str = json.dumps(bundle, ensure_ascii=False)
        compressed_size = len(bundle_str.encode("utf-8"))
        
        compression_ratio = raw_size / max(1.0, compressed_size)
        bundle["compression_ratio"] = round(compression_ratio, 2)
        
        print(f"DreamReader: Loaded trace from {trace_path}. Events: {len(runs)} -> {len(compressed_runs)}. Compression: {bundle['compression_ratio']}x")
        return bundle

dream_reader = DreamReader()
