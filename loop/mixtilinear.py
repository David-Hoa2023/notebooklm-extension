import os
from tikz_agent_demo import generate_tikz_loop

prompt = """
Draw a geometric diagram in TikZ illustrating the A-mixtilinear circle of triangle ABC.
CRITICAL: Do NOT write any calculations, explanations, comments, or intro text. Do not wrap in markdown code blocks. Output ONLY the raw LaTeX TikZ code starting with \\documentclass and ending with \\end{document}.

Use the following mathematically pre-computed coordinates:
- O = (0,0) (origin, center of circumcircle (O))
- Circumcircle (O): center (0,0), radius 3
- Triangle vertices:
  A = (-1.026, 2.819)
  B = (-2.598, -1.5)
  C = (2.598, -1.5)
- Incenter I = (-0.521, -0.046)
- Incircle (I): center (-0.521, -0.046), radius 1.454
- A-mixtilinear circle: center O_a = (-0.353, -1.0), radius 1.939
- Tangent point E on AB: E = (-2.175, -0.337)
- Tangent point F on AC: F = (1.133, 0.246)
- Tangent point X on circumcircle (O): X = (-0.997, -2.829)
- Midpoint of arc BC containing A: M'_A = (0, 3)

Requirements:
1. Draw circumcircle (O), incircle (I), and mixtilinear circle (w_a) using the given coordinates and radii.
2. Draw the triangle ABC.
3. Draw the segment EF and plot point I (which is the midpoint of EF).
4. Draw the line starting from X, passing through I, and ending at M'_A.
5. Clearly plot and label points A, B, C, O, I, E, F, X, M'_A.
6. Use professional and distinct colors (e.g. blue for circumcircle, teal for incircle, red for mixtilinear circle, dark gray for triangle, dashed purple for line XI).
"""

if __name__ == "__main__":
    generate_tikz_loop(prompt=prompt, output_filename="mixtilinear.tex", max_iterations=5)
