# Encoding Policy

- Use UTF-8 (no BOM) for all Markdown and text files.
- Avoid CP949/ANSI encoding to prevent mojibake on GitHub and cross-OS editors.
- Windows PowerShell: prefer `Set-Content -Encoding utf8` and `Add-Content -Encoding utf8` for scripted edits.
- Validate rendering in both VS Code and GitHub Web before merging.
