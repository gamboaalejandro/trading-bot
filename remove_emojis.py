"""
Script to remove ALL Unicode emojis from the entire project
"""
import re
import os
from pathlib import Path

# Emoji regex pattern - covers all Unicode emoji ranges
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002700-\U000027BF"  # dingbats
    "\U0001F900-\U0001F9FF"  # supplemental symbols
    "\U00002600-\U000026FF"  # misc symbols
    "\U0001FA00-\U0001FA6F"  # extended symbols
    "\u2713"  # checkmark
    "\u2714"  # heavy checkmark
    "\u2717"  # ballot X
    "\u2718"  # heavy ballot X
    "]+", 
    flags=re.UNICODE
)

def remove_emojis_from_file(filepath):
    """Remove all emojis from a file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Count emojis before
        emoji_matches = EMOJI_PATTERN.findall(content)
        if not emoji_matches:
            return 0
        
        # Remove emojis
        cleaned = EMOJI_PATTERN.sub('', content)
        
        # Write back
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(cleaned)
        
        return len(emoji_matches)
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return 0

def main():
    project_root = Path(__file__).parent
    total_removed = 0
    files_modified = 0
    
    # Extensions to process
    extensions = ['.py', '.md', '.txt', '.sh']
    
    print("Scanning project for emojis...")
    print("=" * 60)
    
    for ext in extensions:
        for filepath in project_root.rglob(f'*{ext}'):
            # Skip virtual environment and git
            if 'venv' in str(filepath) or '.git' in str(filepath):
                continue
            
            count = remove_emojis_from_file(filepath)
            if count > 0:
                total_removed += count
                files_modified += 1
                print(f"[OK] {filepath.relative_to(project_root)}: {count} emojis removed")
    
    print("=" * 60)
    print(f"Total: {total_removed} emojis removed from {files_modified} files")

if __name__ == "__main__":
    main()
