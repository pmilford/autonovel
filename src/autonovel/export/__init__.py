"""Export helpers — PIL/LaTeX/HTML heavy lifting factored out of commands.

Commands shell out to these via `bash python3 -c "..."` so the command
body stays short and the heavy lifting is Tier-1-testable.

Modules:
  - cover  — PIL composites for e-book cover and print-ready wraparound.
  - landing — HTML landing page renderer from the packaged template.
"""
