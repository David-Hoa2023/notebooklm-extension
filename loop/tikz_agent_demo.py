import os
import sys
import subprocess
import re

# Reconfigure stdout to use UTF-8 to prevent encoding crashes on Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

SYSTEM_PROMPT = """You are an expert LaTeX and TikZ assistant.
Your sole job is to generate valid, compilable LaTeX code that uses the TikZ package to draw the figure described by the user.

CRITICAL REQUIREMENTS:
1. Use the 'standalone' document class with the 'tikz' package.
2. Return ONLY the raw LaTeX code. Do NOT wrap it in any explanation, intro, or markdown blocks. Just start with \\documentclass and end with \\end{document}.
3. Ensure all coordinates are mathematically correct based on the prompt.
4. Do not include external dependencies or packages other than tikz unless absolutely necessary.
"""

def extract_latex_code(raw_response: str) -> str:
    """
    Cleans the model response in case it contains markdown formatting.
    """
    cleaned = raw_response.strip()
    
    # 1. Try to extract content inside ```latex ... ``` or ```tikz ... ``` or general ``` ... ``` blocks
    code_block_match = re.search(r"```(?:latex|tikz)?\s*(.*?)\s*```", cleaned, re.DOTALL | re.IGNORECASE)
    if code_block_match:
        content = code_block_match.group(1).strip()
        if "\\documentclass" in content:
            return content
        cleaned = content
        
    # 2. Try to find the document structure from \documentclass to \end{document}
    match = re.search(r"\\documentclass.*\\end{document}", cleaned, re.DOTALL)
    if match:
        return match.group(0)
        
    # 3. If there is no \documentclass, but we see \begin{tikzpicture} and \end{tikzpicture}, wrap it
    if "\\begin{tikzpicture}" in cleaned and "\\end{tikzpicture}" in cleaned:
        tikz_match = re.search(r"\\begin{tikzpicture}.*\\end{tikzpicture}", cleaned, re.DOTALL)
        if tikz_match:
            tikz_code = tikz_match.group(0)
            return f"\\documentclass{{standalone}}\n\\usepackage{{tikz}}\n\\begin{{document}}\n{tikz_code}\n\\end{{document}}"
            
    return cleaned

def compile_latex(file_path: str, output_dir: str = ".") -> tuple[bool, str]:
    """
    Runs pdflatex on the generated .tex file to verify its validity.
    Returns (success_boolean, log_or_error_message).
    """
    try:
        # Run pdflatex non-interactively, with stdin closed to prevent prompts from hanging
        result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", f"-output-directory={output_dir}", file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=10 # Prevent endless compilation
        )
        
        if result.returncode == 0:
            return True, "Compilation successful."
        
        # If compilation failed, read the .log file to extract the relevant LaTeX error
        log_file = file_path.replace(".tex", ".log")
        if os.path.exists(log_file):
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                log_content = f.read()
            
            # Extract the last few lines of the log containing the actual error messages
            error_lines = []
            for line in log_content.split("\n"):
                if line.startswith("!") or "Error" in line or "Undefined control sequence" in line:
                    error_lines.append(line)
            
            error_msg = "\n".join(error_lines[-5:]) if error_lines else "LaTeX compilation failed with errors."
            return False, error_msg
        else:
            return False, result.stdout[-500:] # Fallback to stdout snippet
            
    except subprocess.TimeoutExpired:
        return False, "Compilation timed out (possibly an infinite loop in TikZ coordinate calculations or packages missing)."
    except Exception as e:
        return False, f"Execution error: {str(e)}"

def generate_tikz_loop(prompt: str, output_filename: str = "output_figure.tex", max_iterations: int = 5) -> bool:
    """
    An autonomous loop (Evaluator-Optimizer pattern) that generates and self-corrects 
    LaTeX TikZ code until it successfully compiles.
    """
    try:
        from openai import OpenAI
    except ImportError:
        print("❌ Error: The 'openai' package is not installed.")
        print("👉 Please run: pip install openai")
        return False

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ Error: OPENROUTER_API_KEY environment variable is not set.")
        print("👉 Please set it before running the script (e.g., $env:OPENROUTER_API_KEY='your_key' in PowerShell).")
        return False
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key
    )
    
    print(f"\n🚀 Starting loop for prompt: '{prompt}'")
    
    # We maintain the thread memory of failures and code versions to guide the LLM
    messages = [
        {"role": "user", "content": f"Please draw this using TikZ: {prompt}"}
    ]
    
    for i in range(1, max_iterations + 1):
        print(f"\n--- Iteration {i}/{max_iterations} ---")
        print("🤖 Generating/correcting TikZ code...")
        
        # OpenRouter / OpenAI compatibility format: System prompt goes as first message
        openai_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

        # Call the LLM
        response = client.chat.completions.create(
            model="~anthropic/claude-sonnet-latest",
            max_tokens=2048,
            temperature=0.0, # Low temperature for precise code generation
            messages=openai_messages
        )
        
        raw_code = response.choices[0].message.content
        latex_code = extract_latex_code(raw_code)
        
        # Save code to disk
        with open(output_filename, "w", encoding="utf-8") as f:
            f.write(latex_code)
            
        print(f"💾 Code saved to {output_filename}. Verifying...")
        
        # Verification Gate: Try compiling the file using pdflatex
        success, feedback = compile_latex(output_filename)
        
        if success:
            print("✅ Success! The LaTeX code compiled perfectly without errors.")
            print(f"🎉 Output PDF generated successfully.")
            return True
        else:
            print("❌ Compilation Failed!")
            print(f"⚠️ Compiler Feedback:\n{feedback}")
            
            if i == max_iterations:
                print("\n🛑 Max iterations reached. Loop terminated without success.")
                return False
                
            print("🔄 Feeding compiler logs back to the agent for self-correction...")
            # Append the failed code and the error logs to the conversation context
            messages.append({"role": "assistant", "content": raw_code})
            messages.append({
                "role": "user",
                "content": f"The code failed to compile with the following error:\n{feedback}\n\nPlease analyze the error, fix the TikZ coordinates or commands, and provide the fully corrected LaTeX document."
            })

if __name__ == "__main__":
    # Example usage:
    # Make sure you have OPENROUTER_API_KEY environment variable set or the default fallback is used.
    # To run this, you will need the openai package installed (pip install openai)
    # and pdflatex in your system PATH.
    
    user_prompt = "Vẽ một tam giác đều có cạnh là 2cm với các đỉnh được đặt tên là A, B, C."
    success = generate_tikz_loop(prompt=user_prompt, output_filename="tam_giac_deu.tex")

