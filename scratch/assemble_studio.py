import os
import shutil
import sys
from pathlib import Path

TEMP = Path(r"C:\Users\vuong\.gemini\antigravity\temp_repos")
TARGET = Path(r"C:\Users\vuong\.gemini\config\skills\omni-video-studio")

modules_dir = TARGET / "modules"
modules_dir.mkdir(parents=True, exist_ok=True)

def safe_copy_tree(src: Path, dst: Path, ignore_patterns=None):
    if not src.exists():
        print(f"Warning: {src} does not exist!")
        return
    dst.mkdir(parents=True, exist_ok=True)
    for root, dirs, files in os.walk(src):
        # Ignore git
        if ".git" in dirs:
            dirs.remove(".git")
        rel = Path(root).relative_to(src)
        target_sub = dst / rel
        target_sub.mkdir(parents=True, exist_ok=True)
        for f in files:
            # Skip huge videos/archives > 15MB
            sf = Path(root) / f
            try:
                sz = sf.stat().st_size
                if sz > 15 * 1024 * 1024:
                    print(f"Skipping large file ({sz/(1024*1024):.1f}MB): {f}")
                    continue
                df = target_sub / f
                if not df.exists():
                    shutil.copy2(sf, df)
            except Exception as e:
                pass

print("=== 1. Copying anything2video ===")
a2v_src = TEMP / "anything2video" / "anything2video-main"
if not a2v_src.exists():
    a2v_src = TEMP / "anything2video"
safe_copy_tree(a2v_src, modules_dir / "01_anything2video")

print("=== 2. Copying video-shotcraft ===")
shotcraft_src = TEMP / "video-shotcraft"
safe_copy_tree(shotcraft_src, modules_dir / "02_video_shotcraft")

print("=== 3. Copying mg-styles-15 ===")
mg_src = TEMP / "mg-styles-15"
safe_copy_tree(mg_src, modules_dir / "03_mg_styles_15")

print("=== 4. Copying wtt-code-animation-studio ===")
wtt_src = TEMP / "Wattter_openSkills" / "wattter_skills" / "wtt-code-animation-studio"
safe_copy_tree(wtt_src, modules_dir / "04_code_animation_studio")

print("=== 5. Copying dashi-animationstyle ===")
dashi_src = TEMP / "dashi-animationstyle"
safe_copy_tree(dashi_src, modules_dir / "05_dashi_animation_style")

print("=== 6. Copying huashu-art-motion ===")
huashu_src = TEMP / "huashu-art-motion"
safe_copy_tree(huashu_src, modules_dir / "06_huashu_art_motion")

print("=== 7. Copying baoyu-design ===")
baoyu_src = TEMP / "baoyu-design" / "baoyu-design-main"
if not baoyu_src.exists():
    baoyu_src = TEMP / "baoyu-design"
safe_copy_tree(baoyu_src, modules_dir / "07_baoyu_design")

print("=== 8. Copying xilo-opus-video & lemo-opuscar ===")
xilo_src = TEMP / "xilo-opus-video"
safe_copy_tree(xilo_src, modules_dir / "08_opus_cinematic" / "xilo")

lemo_src = TEMP / "lemo-opuscar"
safe_copy_tree(lemo_src, modules_dir / "08_opus_cinematic" / "lemo")

print("All modules assembled successfully into:", TARGET)
