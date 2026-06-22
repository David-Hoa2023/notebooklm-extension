import re
import json

def extract_json(content: str) -> str:
    """
    Extracts the first JSON object or array from a string, handling markdown fences
    and extra conversational text gracefully.
    """
    content = content.strip()
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL | re.IGNORECASE)
    if match:
        content = match.group(1).strip()
    
    start_brace = content.find('{')
    start_bracket = content.find('[')
    
    if start_brace != -1 and (start_bracket == -1 or start_brace < start_bracket):
        for i in range(start_brace + 1, len(content) + 1):
            if content[i-1] == '}':
                sub = content[start_brace:i]
                try:
                    json.loads(sub)
                    return sub
                except json.JSONDecodeError:
                    pass
        end_brace = content.rfind('}')
        if end_brace != -1:
            return content[start_brace:end_brace+1]
            
    elif start_bracket != -1:
        for i in range(start_bracket + 1, len(content) + 1):
            if content[i-1] == ']':
                sub = content[start_bracket:i]
                try:
                    json.loads(sub)
                    return sub
                except json.JSONDecodeError:
                    pass
        end_bracket = content.rfind(']')
        if end_bracket != -1:
            return content[start_bracket:end_bracket+1]
            
    return content

def clean_electrical_analogy(text: str) -> str:
    """
    Cleans up the electrical current analogy from the generated STORM article text
    to align it with a professional AI feedback loop context.
    """
    analogy_str = 'This can also be understood as the "current intensity" of operations, drawing a parallel to the conventional symbol \'I\' for electrical current [15].'
    analogy_str_alt = 'This can also be understood as the "current intensity" of operations, drawing a parallel to the conventional symbol \'I\' for electrical current'
    clean_str = 'This can also be understood as the active, present-time stream or flow of information and feedback processed in loop engineering [1].'
    
    if analogy_str in text:
        return text.replace(analogy_str, clean_str)
    elif analogy_str_alt in text:
        return text.replace(analogy_str_alt, clean_str)
    return text
