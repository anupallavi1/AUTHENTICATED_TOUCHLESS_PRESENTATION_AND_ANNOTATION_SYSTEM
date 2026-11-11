"""
PPT Summarizer
Reads a PowerPoint file, summarizes it and saves a report (HTML + Markdown).

- Summary is written by Gemini when it is reachable (needs internet + API key).
- If Gemini fails, an offline summary is built from the slide text itself
  (keyword-based sentence ranking).

"""

import os
import re
import sys
import json
import html
import webbrowser
import concurrent.futures
from datetime import datetime
from collections import Counter

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

# Gemini key: GEMINI_API_KEY env var if set, otherwise the project key
api_key = os.environ.get("GEMINI_API_KEY") or "AQ.Ab8RN6LeKiE8w78eCL5jK8eQ9TR42YuD1voaK444aZwKiUYkVQ"

GEMINI_MODEL = "gemini-flash-lite-latest"   # fast; the non-lite model can take 30+ s
GEMINI_TIMEOUT = 90
MAX_PROMPT_CHARS = 200000
SUMMARY_FOLDER = "summaries"

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
    "by", "is", "are", "was", "were", "be", "been", "being", "this", "that", "these",
    "those", "it", "its", "as", "we", "you", "our", "your", "they", "their", "he", "she",
    "his", "her", "i", "me", "my", "will", "can", "could", "should", "would", "may",
    "might", "have", "has", "had", "do", "does", "did", "not", "no", "so", "if", "then",
    "than", "from", "into", "about", "also", "more", "most", "some", "any", "all", "each",
    "which", "who", "what", "when", "where", "how", "there", "here", "such", "very",
    "just", "only", "other", "using", "use", "used", "one", "two", "like", "get", "cont",
    "contd", "etc", "able", "need", "make", "many", "much", "well", "way", "new",
}


# -----------------------------
# 1. Extract slide content
# -----------------------------
def clean_text(text):
    """Collapse tabs / odd spaces and trim."""
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def base_title(title):
    """'Python Features Cont...' -> 'Python Features' (to group continuation slides)."""
    return re.sub(r"\s*[\(\-–:]?\s*\b(cont(d|inued)?)\b.*$|\s*(…|\.\.\.|\ufffd)+$", "",
                  title, flags=re.I).strip()


AGENDA_TITLES = {"content", "contents", "agenda", "outline", "index", "overview",
                 "table of contents", "topics"}


def is_agenda(title):
    return base_title(title).lower().strip(" :") in AGENDA_TITLES


def iter_shapes(shapes):
    """All shapes on a slide, including the ones inside groups."""
    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from iter_shapes(shape.shapes)
        else:
            yield shape


def extract_slides(ppt_path):
    """Return a list of dicts: number, title, points [(level, text)], tables, notes, images, charts."""
    prs = Presentation(ppt_path)
    slides = []
    for number, slide in enumerate(prs.slides, start=1):
        info = {"number": number, "title": "", "points": [], "tables": [],
                "notes": "", "images": 0, "charts": []}

        title_shape = slide.shapes.title
        if title_shape is not None and title_shape.has_text_frame:
            info["title"] = clean_text(title_shape.text_frame.text)

        for shape in iter_shapes(slide.shapes):
            if title_shape is not None and shape.shape_id == title_shape.shape_id:
                continue
            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                info["images"] += 1
            if getattr(shape, "has_chart", False) and shape.has_chart:
                chart = shape.chart
                name = clean_text(chart.chart_title.text_frame.text) if chart.has_title else "Chart"
                info["charts"].append(name)
            if getattr(shape, "has_table", False) and shape.has_table:
                rows = [[clean_text(cell.text) for cell in row.cells] for row in shape.table.rows]
                info["tables"].append(rows)
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    text = clean_text("".join(run.text for run in paragraph.runs))
                    if text:
                        info["points"].append((paragraph.level, text))

        if slide.has_notes_slide and slide.notes_slide.notes_text_frame is not None:
            info["notes"] = clean_text(slide.notes_slide.notes_text_frame.text)

        # No title placeholder: use the first line of text
        if not info["title"] and info["points"]:
            info["title"] = info["points"].pop(0)[1]
        slides.append(info)
    return slides


def slides_to_text(slides):
    """Plain-text version of the deck for the AI prompt."""
    parts = []
    for s in slides:
        block = [f"--- Slide {s['number']}: {s['title'] or '(no title)'} ---"]
        for level, text in s["points"]:
            block.append("  " * level + "- " + text)
        for rows in s["tables"]:
            block.append("Table:")
            block.extend("  | " + " | ".join(r) + " |" for r in rows)
        for chart in s["charts"]:
            block.append(f"[Chart: {chart}]")
        if s["images"]:
            block.append(f"[{s['images']} image(s)]")
        if s["notes"]:
            block.append(f"Speaker notes: {s['notes']}")
        parts.append("\n".join(block))
    return "\n\n".join(parts)


def deck_stats(slides):
    all_text = " ".join(t for s in slides for _, t in s["points"]) + " " + \
               " ".join(s["title"] for s in slides)
    return {
        "slides": len(slides),
        "words": len(all_text.split()),
        "images": sum(s["images"] for s in slides),
        "tables": sum(len(s["tables"]) for s in slides),
        "charts": sum(len(s["charts"]) for s in slides),
    }


def top_keywords(text, n=10):
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9+#]{2,}", text.lower())
    return [w for w, _ in Counter(w for w in words if w not in STOPWORDS).most_common(n)]


# -----------------------------
# 2a. Summary with Gemini
# -----------------------------
GEMINI_PROMPT = """You are summarizing a PowerPoint presentation for a student audience.
Read the slide content below and reply with ONLY a JSON object (no code fences) in this exact form:
{
  "title": "short title of the presentation",
  "overview": "3-5 sentence summary of the whole presentation",
  "key_points": ["6-10 most important points, one sentence each"],
  "slides": [{"number": 1, "summary": "one sentence about this slide"}],
  "conclusion": "2-3 sentence conclusion / main takeaway",
  "keywords": ["8-12 important terms"]
}
Include every slide number in "slides". Only use facts that are in the presentation.

Presentation content:
\"\"\"
%s
\"\"\"
"""


def parse_json_reply(text):
    """Pull the JSON object out of the model reply (tolerates ```json fences)."""
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError("Gemini did not return JSON")
    data = json.loads(match.group(0))
    for key in ("overview", "key_points", "slides", "conclusion"):
        if key not in data:
            raise ValueError(f"Gemini reply is missing '{key}'")
    return data


def gemini_summary(slides):
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(GEMINI_MODEL)
    prompt = GEMINI_PROMPT % slides_to_text(slides)[:MAX_PROMPT_CHARS]
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        request = pool.submit(model.generate_content, prompt,
                              generation_config={"temperature": 0.2, "max_output_tokens": 8192})
        response = request.result(timeout=GEMINI_TIMEOUT)
    return parse_json_reply(response.text)


# -----------------------------
# 2b. Offline summary (no internet needed)
# -----------------------------
def split_sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 3]


def score_sentences(sentences, word_freq):
    """Average importance of the content words in each sentence."""
    scored = []
    for s in sentences:
        words = [w for w in re.findall(r"[a-z][a-z0-9+#]{2,}", s.lower()) if w not in STOPWORDS]
        if words:
            scored.append((sum(word_freq[w] for w in words) / len(words) ** 0.7, s))
    return scored


def shorten(text, limit=180):
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "..."


def offline_summary(slides):
    all_points = [t for s in slides for _, t in s["points"]] + [s["notes"] for s in slides if s["notes"]]
    all_text = " ".join(all_points + [s["title"] for s in slides])
    content_words = [w for w in re.findall(r"[a-z][a-z0-9+#]{2,}", all_text.lower()) if w not in STOPWORDS]
    word_freq = Counter(content_words)
    if word_freq:
        top = word_freq.most_common(1)[0][1]
        word_freq = Counter({w: c / top for w, c in word_freq.items()})

    # Key points: best-scoring full sentences across the deck (not headings / agenda items),
    # kept in slide order, no duplicates
    titles = {s["title"].lower() for s in slides}
    sentences = []
    for s in slides:
        if is_agenda(s["title"]):
            continue
        for _, text in s["points"]:
            sentences.extend(x for x in split_sentences(text)
                             if len(x.split()) >= 6 and x.lower() not in titles)
    scored = score_sentences(list(dict.fromkeys(sentences)), word_freq)
    best = sorted(scored, reverse=True)[:8]
    order = {s: i for i, s in enumerate(sentences)}
    key_points = [shorten(s) for _, s in sorted(best, key=lambda x: order[x[1]])]

    # One line per slide: its title plus its most important point
    slide_lines = []
    for s in slides:
        best_point = max(score_sentences([t for _, t in s["points"]], word_freq), default=None)
        title = base_title(s["title"]) or "Untitled slide"
        summary = title + (" (continued)" if title != s["title"] and s["title"] else "")
        if is_agenda(s["title"]) and s["points"]:
            summary += ": " + shorten(", ".join(t for _, t in s["points"]), 140)
        elif best_point:
            summary += ": " + shorten(best_point[1], 140)
        elif s["images"]:
            summary += f" (visual slide with {s['images']} image(s))"
        slide_lines.append({"number": s["number"], "summary": summary})

    # Main topics = distinct slide titles (continuation slides merged)
    title = slides[0]["title"] if slides and slides[0]["title"] else "Presentation"
    topics = list(dict.fromkeys(base_title(s["title"]) for s in slides[1:]
                                if s["title"] and not is_agenda(s["title"])))
    topic_list = ", ".join(topics[:-1]) + " and " + topics[-1] if len(topics) > 1 else "".join(topics)
    overview = (f"This presentation, \"{title}\", has {len(slides)} slides"
                + (f" covering {topic_list}" if topics else "") + ". ")
    overview += " ".join(key_points[:2])

    conclusion = (f"The presentation walks through {topic_list}. " if topics else "")
    if key_points:
        conclusion += "Key takeaway: " + key_points[-1]
    return {"title": title, "overview": overview, "key_points": key_points,
            "slides": slide_lines, "conclusion": conclusion,
            "keywords": top_keywords(all_text, 10)}


# -----------------------------
# 3. Build the report
# -----------------------------
def summarize_ppt(ppt_path):
    """Extract + summarize. Returns a dict with the summary, stats and engine used."""
    slides = extract_slides(ppt_path)
    if not slides:
        raise ValueError("The presentation has no slides")
    try:
        summary = gemini_summary(slides)
        engine = "Gemini AI"
    except Exception as e:
        print("Gemini unavailable, using offline summary:", e)
        summary = offline_summary(slides)
        engine = "Offline (keyword based)"
    if not summary.get("keywords"):
        summary["keywords"] = top_keywords(slides_to_text(slides), 10)
    return {"file": os.path.basename(ppt_path), "summary": summary,
            "stats": deck_stats(slides), "engine": engine,
            "generated": datetime.now().strftime("%Y-%m-%d %H:%M")}


def report_markdown(result):
    s, st = result["summary"], result["stats"]
    lines = [f"# {s.get('title') or result['file']}",
             f"*Summary of {result['file']} - generated {result['generated']}*", "",
             "## Overview", s["overview"], "",
             "## Key Points"] + [f"- {p}" for p in s["key_points"]] + [
             "", "## Slide by Slide"] + [f"{x['number']}. {x['summary']}" for x in s["slides"]] + [
             "", "## Conclusion", s["conclusion"], "",
             "## Keywords", ", ".join(s.get("keywords", [])), "",
             "## Statistics",
             f"- Slides: {st['slides']}", f"- Words: {st['words']}", f"- Images: {st['images']}",
             f"- Tables: {st['tables']}", f"- Charts: {st['charts']}"]
    return "\n".join(lines) + "\n"


def report_html(result):
    s, st = result["summary"], result["stats"]
    e = html.escape
    key_points = "".join(f"<li>{e(p)}</li>" for p in s["key_points"])
    slide_rows = "".join(f"<li><span class='num'>{x['number']}</span>{e(str(x['summary']))}</li>"
                         for x in s["slides"])
    keywords = "".join(f"<span class='tag'>{e(k)}</span>" for k in s.get("keywords", []))
    stats = "".join(f"<div class='stat'><b>{v}</b>{e(k.title())}</div>" for k, v in st.items())
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(s.get('title') or result['file'])} - Summary</title>
<style>
  body {{ margin:0; background:#f4f6fb; color:#1d2433; font-family:'Segoe UI',system-ui,sans-serif; line-height:1.6; }}
  .page {{ max-width:860px; margin:32px auto; background:#fff; border-radius:16px; padding:40px 48px;
           box-shadow:0 10px 30px rgba(20,30,60,.08); }}
  h1 {{ margin:0 0 4px; font-size:30px; }}
  .meta {{ color:#6b7488; font-size:14px; margin-bottom:24px; }}
  h2 {{ font-size:19px; margin:30px 0 10px; color:#2457d6; border-bottom:2px solid #e6ecfa; padding-bottom:6px; }}
  .stats {{ display:flex; flex-wrap:wrap; gap:12px; }}
  .stat {{ flex:1 1 100px; background:#f0f4ff; border-radius:10px; padding:10px 14px; font-size:13px; color:#55607a; }}
  .stat b {{ display:block; font-size:22px; color:#1d2433; }}
  ul.points li {{ margin-bottom:6px; }}
  ol.slides {{ list-style:none; padding:0; }}
  ol.slides li {{ display:flex; gap:12px; padding:8px 0; border-bottom:1px solid #eef1f6; }}
  .num {{ flex:0 0 28px; height:28px; border-radius:50%; background:#2457d6; color:#fff;
          font-size:13px; display:flex; align-items:center; justify-content:center; }}
  .tag {{ display:inline-block; background:#e9f7ef; color:#1d7a46; border-radius:999px;
          padding:3px 12px; margin:0 6px 6px 0; font-size:13px; }}
  @media (max-width:600px) {{ .page {{ margin:0; border-radius:0; padding:24px 16px; }} }}
  @media print {{ body {{ background:#fff; }} .page {{ box-shadow:none; margin:0; }} }}
</style></head>
<body><div class="page">
  <h1>{e(s.get('title') or result['file'])}</h1>
  <div class="meta">Summary of <b>{e(result['file'])}</b> &middot; {e(result['generated'])}</div>
  <div class="stats">{stats}</div>
  <h2>Overview</h2><p>{e(s['overview'])}</p>
  <h2>Key Points</h2><ul class="points">{key_points}</ul>
  <h2>Slide by Slide</h2><ol class="slides">{slide_rows}</ol>
  <h2>Conclusion</h2><p>{e(s['conclusion'])}</p>
  <h2>Keywords</h2><div>{keywords}</div>
</div></body></html>
"""


def generate_full_report(ppt_path, output_path=None, open_report=True):
    """Summarize a PPT and save it as HTML (+ a Markdown copy next to it).
    Returns the path of the HTML report."""
    result = summarize_ppt(ppt_path)

    if output_path is None:
        name = os.path.splitext(os.path.basename(ppt_path))[0]
        output_path = os.path.join(SUMMARY_FOLDER, f"{name}_summary.html")
    output_path = os.path.splitext(output_path)[0] + ".html"
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_html(result))
    with open(os.path.splitext(output_path)[0] + ".md", "w", encoding="utf-8") as f:
        f.write(report_markdown(result))

    print(f"Summary saved to: {output_path}")
    if open_report:
        webbrowser.open("file:///" + os.path.abspath(output_path).replace("\\", "/"))
    return output_path


# if __name__ == "__main__":
#     if len(sys.argv) < 2:
#         print("Usage: python ppt_summarizer.py <presentation.pptx> [output.html]")
#     else:
#         generate_full_report(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
