# -*- coding: utf-8 -*-
"""
Multi-Format Output v1.0
朱雀·任务飞轮 — 多格式输出引擎

同一内容自动转换为HTML/Markdown/JSON/Plain格式
"""
import json, os
from datetime import datetime

class MultiFormatOutput:
    def __init__(self):
        self.formats = ["html", "markdown", "json", "plain"]
    
    def convert(self, content, title, metadata=None):
        """将结构化内容转换为多种格式"""
        results = {}
        
        # HTML
        sections_html = ""
        for section in content.get("sections", []):
            items = "".join(f"<li>{item}</li>" for item in section.get("items", []))
            sections_html += f"<h2>{section['title']}</h2><ul>{items}</ul>"
        results["html"] = f"<html><head><title>{title}</title></head><body><h1>{title}</h1>{sections_html}</body></html>"
        
        # Markdown
        sections_md = ""
        for section in content.get("sections", []):
            sections_md += f"\n## {section['title']}\n"
            for item in section.get("items", []):
                sections_md += f"- {item}\n"
        results["markdown"] = f"# {title}\n{sections_md}"
        
        # JSON
        results["json"] = json.dumps({
            "title": title, "content": content,
            "metadata": metadata or {}, "generated": datetime.now().isoformat()
        }, ensure_ascii=False, indent=2)
        
        # Plain text
        sections_txt = ""
        for section in content.get("sections", []):
            sections_txt += f"\n{section['title']}:\n"
            for item in section.get("items", []):
                sections_txt += f"  * {item}\n"
        results["plain"] = f"{title}\n{'='*len(title)}\n{sections_txt}"
        
        return results
    
    def batch_convert(self, items):
        """批量转换"""
        all_results = []
        for item in items:
            result = self.convert(item["content"], item["title"], item.get("metadata"))
            all_results.append({"title": item["title"], "formats": result})
        return all_results


def main():
    engine = MultiFormatOutput()
    
    content = {
        "sections": [
            {"title": "Core Engines", "items": ["seed_competition.py", "auto_incubation.py", "task_auto_assigner.py"]},
            {"title": "Progress", "items": ["青龙 88%", "朱雀 88%", "玄武 87%", "白虎 85%"]},
            {"title": "Key Metrics", "items": ["41 engines", "94+ pages", "avg 87%"]},
        ]
    }
    
    results = engine.convert(content, "四象飞轮 R18 Report")
    
    print("=== Multi-Format Output v1.0 ===")
    for fmt, text in results.items():
        preview = text[:80].replace('\n', ' ')
        print(f"  {fmt:10s} {len(text):5d}B | {preview}...")
    
    # Batch test
    batch = engine.batch_convert([
        {"title": "Report A", "content": {"sections": [{"title": "S1", "items": ["a","b"]}]}},
        {"title": "Report B", "content": {"sections": [{"title": "S2", "items": ["c","d"]}]}},
    ])
    print(f"\n  Batch: {len(batch)} items converted to {len(engine.formats)} formats each")

if __name__ == "__main__":
    main()
