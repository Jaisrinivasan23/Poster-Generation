#!/usr/bin/env python3
"""
Fix indentation in templates.py after sed replacement
"""
import re

file_path = r"D:\Jaii's\Topmate\Email-forge(copy)\poster-generation-migration\backend\app\routers\templates.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern to find: async with database_service.connection() as conn:\n\n        # (code at same level)
# Should be: async with database_service.connection() as conn:\n            # (code indented one level)

lines = content.split('\n')
fixed_lines = []
in_async_with = False
indent_level = 0

i = 0
while i < len(lines):
    line = lines[i]

    # Check if this line is the async with statement
    if 'async with database_service.connection() as conn:' in line:
        fixed_lines.append(line)
        in_async_with = True
        # Calculate the base indent level
        indent_level = len(line) - len(line.lstrip())
        i += 1

        # Skip empty line if present
        if i < len(lines) and lines[i].strip() == '':
            i += 1

        # Indent all following lines until we hit a dedent
        while i < len(lines):
            next_line = lines[i]

            # If we hit a line at the same or less indent level (except empty lines), stop indenting
            if next_line.strip():
                next_indent = len(next_line) - len(next_line.lstrip())
                if next_indent <= indent_level:
                    break

            # Add 4 spaces of indentation if not already indented enough
            if next_line.strip() and not next_line.startswith(' ' * (indent_level + 4)):
                current_indent = len(next_line) - len(next_line.lstrip())
                if current_indent == indent_level:
                    # Need to indent this line
                    fixed_lines.append(' ' * (indent_level + 4) + next_line.strip())
                else:
                    fixed_lines.append(next_line)
            else:
                fixed_lines.append(next_line)

            i += 1

        in_async_with = False
        continue

    fixed_lines.append(line)
    i += 1

with open(file_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(fixed_lines))

print("✅ Fixed indentation in templates.py")
