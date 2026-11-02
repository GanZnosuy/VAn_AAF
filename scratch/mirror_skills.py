import os
import shutil
from pathlib import Path

SOURCE = Path(r"C:\Users\vuong\.gemini\config\skills\omni-video-studio")
USERPROFILE = Path(os.environ["USERPROFILE"])

# 1. Workspace .agents/skills
ws_dest = Path(r"c:\Users\vuong\OneDrive\Desktop\CAIDATHETTHONG\.agents\skills\omni-video-studio")
ws_dest.parent.mkdir(parents=True, exist_ok=True)
if not ws_dest.exists():
    shutil.copytree(SOURCE, ws_dest, dirs_exist_ok=True)
    print("Copied to workspace .agents/skills/omni-video-studio")

# 2. ~/.codex/skills
codex_dir = USERPROFILE / ".codex" / "skills"
codex_dir.mkdir(parents=True, exist_ok=True)
shutil.copytree(SOURCE, codex_dir / "omni-video-studio", dirs_exist_ok=True)
# Also wtt-code-animation-studio directly in .codex/skills
wtt_src = SOURCE / "modules" / "04_code_animation_studio"
if wtt_src.exists():
    shutil.copytree(wtt_src, codex_dir / "wtt-code-animation-studio", dirs_exist_ok=True)
print("Copied to ~/.codex/skills")

# 3. ~/.claude/skills
claude_dir = USERPROFILE / ".claude" / "skills"
claude_dir.mkdir(parents=True, exist_ok=True)
shutil.copytree(SOURCE, claude_dir / "omni-video-studio", dirs_exist_ok=True)
# Also anything2video directly in .claude/skills
a2v_src = SOURCE / "modules" / "01_anything2video"
if a2v_src.exists():
    shutil.copytree(a2v_src, claude_dir / "anything2video", dirs_exist_ok=True)
print("Copied to ~/.claude/skills")
