#!/usr/bin/env python
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Write a local diagnostic report when no uploaded paper is found.")
    parser.add_argument("--workspace", required=True, help="Workspace directory.")
    parser.add_argument("--output-dir", required=True, help="Output directory.")
    parser.add_argument("--reason", default="No uploaded paper was detected in the current workspace.")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "status": "missing_upload",
        "reason": args.reason,
        "workspace": str(workspace),
        "recommended_reply": "The paper file did not land in the current FastClaw workspace. Re-upload it through the file picker or Open files for this chat, then run the slide workflow again.",
        "next_actions": [
            "Re-upload the paper through the FastClaw file picker for this chat.",
            "If the attachment bubble appears but the file is still missing, open a new chat session and upload again.",
            "After the file lands in the workspace, rerun the same prompt.",
        ],
        "diagnostic_files": [
            str(output_dir / "workspace-inputs.json"),
            str(output_dir / "missing-upload-report.json"),
            str(output_dir / "missing-upload-report.md"),
        ],
    }

    report_json = output_dir / "missing-upload-report.json"
    report_md = output_dir / "missing-upload-report.md"
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_md.write_text(
        "\n".join(
            [
                "# Missing Upload Report",
                "",
                report["reason"],
                "",
                "## What to do",
                "",
                "- Re-upload the paper through the FastClaw file picker for this chat.",
                "- If the attachment bubble appears but the file is still missing, open a new chat session and upload again.",
                "- After the file lands in the workspace, rerun the same prompt.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(str(report_json))


if __name__ == "__main__":
    main()
