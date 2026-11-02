#!/usr/bin/env python3
"""
iOS App Scaffolding Tool with xtool
Quickly generate a production-ready SwiftUI iOS project structured for xtool.
"""

import sys
import argparse
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def create_ios_app(app_name: str, bundle_id: str = None, output_dir: str = "."):
    if not bundle_id:
        bundle_id = f"com.example.{app_name}"

    root = Path(output_dir) / app_name
    root.mkdir(parents=True, exist_ok=True)

    sources_dir = root / "Sources" / app_name
    sources_dir.mkdir(parents=True, exist_ok=True)
    bsp_dir = root / ".bsp"
    bsp_dir.mkdir(parents=True, exist_ok=True)

    # 1. Package.swift
    package_swift = f"""// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "{app_name}",
    platforms: [
        .iOS(.v17),
        .macOS(.v14)
    ],
    products: [
        .library(
            name: "{app_name}",
            targets: ["{app_name}"]
        )
    ],
    dependencies: [],
    targets: [
        .target(
            name: "{app_name}",
            dependencies: []
        )
    ]
)
"""
    (root / "Package.swift").write_text(package_swift.strip() + "\n", encoding="utf-8")

    # 2. xtool.yml
    xtool_yml = f"""version: 1
bundleID: {bundle_id}
displayName: "{app_name}"
"""
    (root / "xtool.yml").write_text(xtool_yml.strip() + "\n", encoding="utf-8")

    # 3. .bsp/xtool.json
    bsp_json = """{
  "name": "xtool",
  "version": "1.0",
  "bspVersion": "2.0",
  "languages": ["swift"],
  "argv": ["xtool", "bsp"]
}
"""
    (bsp_dir / "xtool.json").write_text(bsp_json.strip() + "\n", encoding="utf-8")

    # 4. App entry point
    app_swift = f"""import SwiftUI

@main
struct {app_name}App: App {{
    var body: some Scene {{
        WindowGroup {{
            ContentView()
        }}
    }}
}}
"""
    (sources_dir / f"{app_name}App.swift").write_text(app_swift.strip() + "\n", encoding="utf-8")

    # 5. ContentView.swift
    content_view = f"""import SwiftUI

struct ContentView: View {{
    @State private var count: Int = 0

    var body: some View {{
        NavigationStack {{
            VStack(spacing: 24) {{
                Image(systemName: "app.fill")
                    .font(.system(size: 72))
                    .foregroundStyle(.blue)

                Text("{app_name}")
                    .font(.largeTitle.bold())

                Text("Built with Swift & xtool on Windows")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)

                Button(action: {{ count += 1 }}) {{
                    Label("Tương tác: \\(count)", systemImage: "hand.tap.fill")
                        .font(.headline)
                        .padding()
                        .frame(maxWidth: .infinity)
                        .background(Color.blue)
                        .foregroundStyle(.white)
                        .clipShape(RoundedRectangle(cornerRadius: 14))
                }}
                .padding(.horizontal, 32)
            }}
            .navigationTitle("Trang Chủ")
        }}
    }}
}}

#Preview {{
    ContentView()
}}
"""
    (sources_dir / "ContentView.swift").write_text(content_view.strip() + "\n", encoding="utf-8")

    # 6. README.md
    readme = f"""# {app_name}

Native iOS application built cross-platform with **xtool** and SwiftUI.

## Getting Started

1. Ensure `xtool` and Swift are installed.
2. Run development build & install directly to iPhone via USB:
   ```bash
   xtool dev
   ```
3. To package an IPA file:
   ```bash
   xtool build
   ```
"""
    (root / "README.md").write_text(readme.strip() + "\n", encoding="utf-8")

    print(f"[✓] Đã tạo thành công dự án iOS '{app_name}' tại: {root.resolve()}")
    print(f"    • Bundle ID: {bundle_id}")
    print(f"    • Để biên dịch & cài đặt lên thiết bị: cd {app_name} && xtool dev")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tạo dự án ứng dụng iOS native sử dụng xtool")
    parser.add_argument("--name", "-n", required=True, help="Tên ứng dụng (VD: ChatBotApp)")
    parser.add_argument("--bundle-id", "-b", help="Bundle ID (VD: com.mycompany.chatbot)")
    parser.add_argument("--out", "-o", default=".", help="Thư mục xuất dự án")

    args = parser.parse_args()
    create_ios_app(args.name, args.bundle_id, args.out)
