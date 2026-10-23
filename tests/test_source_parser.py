"""
测试 Google 官方来源的 Feed、Sitemap、页面元数据、稳定正文和候选分类解析。
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))

from source_parser import (  # noqa: E402
    classify_candidate,
    parse_feed,
    parse_page_metadata,
    parse_release_notes,
    parse_sitemap,
    stable_page_text,
)


class SourceParserTests(unittest.TestCase):
    """验证解析器只提取可审计的官方页面事实。"""

    def test_parse_atom_uses_published_date_and_official_link(self) -> None:
        atom = """<feed xmlns="http://www.w3.org/2005/Atom"><entry>
          <title>Gemini model update</title>
          <link href="https://blog.google/products/gemini/example/"/>
          <published>2026-10-20T01:00:00Z</published>
          <summary>Official Gemini update.</summary>
        </entry></feed>"""
        item = parse_feed(atom)[0]
        self.assertEqual(item["date"], "2026-10-20")
        self.assertEqual(item["url"], "https://blog.google/products/gemini/example")
        self.assertEqual(item["title"], "Gemini model update")

    def test_parse_rss_accepts_rfc_2822_dates(self) -> None:
        rss = """<rss version="2.0"><channel><item>
          <title>Gemini API release</title>
          <link>https://developers.googleblog.com/gemini-api-release/</link>
          <pubDate>Tue, 20 Oct 2026 01:00:00 GMT</pubDate>
          <description>Developer update.</description>
        </item></channel></rss>"""
        item = parse_feed(rss)[0]
        self.assertEqual(item["date"], "2026-10-20")
        self.assertEqual(item["url"], "https://developers.googleblog.com/gemini-api-release")

    def test_sitemap_lastmod_is_not_publish_date(self) -> None:
        xml = """<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://deepmind.google/models/gemini/example/</loc>
          <lastmod>2026-10-20</lastmod></url></urlset>"""
        item = parse_sitemap(xml)[0]
        self.assertEqual(item["lastmod"], "2026-10-20")
        self.assertNotIn("date", item)

    def test_page_metadata_prefers_json_ld_date_published(self) -> None:
        html = """<html><head>
          <title>Fallback title</title>
          <meta property="og:title" content="Gemini 4 update">
          <meta property="og:description" content="Official model details.">
          <meta property="article:published_time" content="2026-10-21T12:00:00Z">
          <script type="application/ld+json">{
            "@type":"NewsArticle", "headline":"Gemini 4 launch",
            "datePublished":"2026-10-20T08:00:00+00:00"
          }</script>
        </head><body><main>Gemini model details</main></body></html>"""
        metadata = parse_page_metadata(
            html, "https://blog.google/products/gemini/gemini-4/"
        )
        self.assertEqual(metadata["date"], "2026-10-20")
        self.assertEqual(metadata["title"], "Gemini 4 launch")
        self.assertEqual(metadata["description"], "Official model details.")

    def test_page_metadata_uses_open_graph_then_time(self) -> None:
        html = """<html><head>
          <meta property="og:title" content="NotebookLM update">
          <meta property="og:description" content="Audio overview update">
        </head><body><main><time datetime="2026-09-30">September 30</time>
          NotebookLM adds a new experience.</main></body></html>"""
        metadata = parse_page_metadata(
            html, "https://blog.google/technology/ai/notebooklm-update/"
        )
        self.assertEqual(metadata["date"], "2026-09-30")
        self.assertEqual(metadata["title"], "NotebookLM update")

    def test_page_without_publish_date_does_not_invent_one(self) -> None:
        metadata = parse_page_metadata(
            "<html><head><title>Gemini models</title></head><body>Current list</body></html>",
            "https://ai.google.dev/gemini-api/docs/models",
        )
        self.assertNotIn("date", metadata)

    def test_page_metadata_rejects_non_official_url(self) -> None:
        with self.assertRaisesRegex(ValueError, "非允许的 Google 官方来源"):
            parse_page_metadata("<title>Gemini</title>", "https://example.com/gemini")

    def test_redirected_google_cloud_docs_host_is_official(self) -> None:
        metadata = parse_page_metadata(
            "<title>Vertex AI release notes</title>",
            "https://docs.cloud.google.com/vertex-ai/generative-ai/docs/release-notes",
        )
        self.assertEqual(
            metadata["url"],
            "https://docs.cloud.google.com/vertex-ai/generative-ai/docs/release-notes",
        )

    def test_source_config_uses_required_fields_and_unique_names(self) -> None:
        config = json.loads((ROOT / "work" / "source-config.json").read_text(encoding="utf-8"))
        required = {
            "name", "label", "type", "url", "required", "grade",
            "path_prefixes", "required_keywords",
        }
        names = []
        for source in config["sources"]:
            self.assertTrue(required.issubset(source))
            names.append(source["name"])
        self.assertEqual(len(names), len(set(names)))
        self.assertGreaterEqual(sum(source["required"] for source in config["sources"]), 2)

    def test_stable_page_text_ignores_meta_without_identifier(self) -> None:
        html = '<html><head><meta charset="utf-8"><meta content="x"></head><body><main>Gemini update</main></body></html>'
        self.assertEqual(stable_page_text(html), "Gemini update")

    def test_stable_page_text_removes_dynamic_long_numeric_token(self) -> None:
        html = "<main><p>Gemini help</p><div>18343420303723979727</div><p>Stable guidance</p></main>"
        text = stable_page_text(html)
        self.assertIn("Gemini help", text)
        self.assertIn("Stable guidance", text)
        self.assertNotIn("18343420303723979727", text)

    def test_stable_page_text_survives_void_tags_before_skipped_script(self) -> None:
        html = """<html><head><meta charset="utf-8"><link rel="canonical" href="x">
          <script>window.runtime = true;</script></head><body><main>
          <h2 data-text="October 13, 2026">October 13, 2026</h2>
          <p>Gemini API release note.</p></main></body></html>"""
        text = stable_page_text(html)
        self.assertIn("October 13, 2026", text)
        self.assertIn("Gemini API release note", text)
        self.assertNotIn("window.runtime", text)

    def test_stable_page_text_recovers_devsite_content_after_void_tags_in_navigation(self) -> None:
        html = """<body>
          <devsite-header>
            <nav><input type="search"><img src="logo.svg">Navigation</nav>
          </devsite-header>
          <devsite-book-nav>
            <nav><link rel="preload" href="menu.css"><br>Book navigation</nav>
          </devsite-book-nav>
          <section><main><devsite-content><article>
            <h2 data-text="October 13, 2026">October 13, 2026</h2>
            <p>Gemini API update.</p>
          </article></devsite-content></main></section>
        </body>"""
        text = stable_page_text(html)
        self.assertIn("October 13, 2026", text)
        self.assertIn("Gemini API update", text)
        self.assertNotIn("Navigation", text)
        self.assertNotIn("Book navigation", text)

    def test_stable_page_text_removes_navigation_and_cookie_noise(self) -> None:
        html = """<body>
          <nav>Products About Sign in</nav>
          <div class="cookie-banner">Accept cookies</div>
          <main><h1>Gemini API update</h1><p>New stable model is available.</p></main>
          <footer>Privacy Terms</footer><script>volatile()</script>
        </body>"""
        text = stable_page_text(html)
        self.assertIn("Gemini API update", text)
        self.assertIn("New stable model is available", text)
        self.assertNotIn("Accept cookies", text)
        self.assertNotIn("Privacy Terms", text)
        self.assertNotIn("volatile", text)

    def test_release_notes_extract_dated_sections(self) -> None:
        html = """<main>
          <h2>October 20, 2026</h2><h3>Gemini API</h3><p>Gemini 4 is generally available.</p>
          <h2>2026-10-18</h2><p>Gemini 3 preview was deprecated.</p>
        </main>"""
        items = parse_release_notes(
            html, "https://ai.google.dev/gemini-api/docs/changelog"
        )
        self.assertEqual([item["date"] for item in items], ["2026-10-20", "2026-10-18"])
        self.assertIn("Gemini 4", items[0]["summary"])

    def test_classification_covers_primary_product_lines(self) -> None:
        cases = (
            ("Gemini 4 model is now generally available", "模型", "Gemini"),
            ("Gemma open model for on-device use", "模型", "Gemma"),
            ("Bard is now available to more users", "产品", "Bard"),
            ("NotebookLM adds Audio Overviews", "产品", "NotebookLM"),
            ("Gemini API and Google AI Studio developer update", "开发者平台", "Google AI Studio"),
            ("Gemini Code Assist and Jules coding agents", "开发者平台", "Jules"),
            ("Google AI Ultra subscription plan benefits", "订阅计划", "Google AI Ultra"),
            ("Gemini 2.0 model is deprecated and will shut down", "生命周期", "Gemini"),
        )
        for text, category, family in cases:
            with self.subTest(text=text):
                result = classify_candidate(text)
                self.assertEqual(result["category"], category)
                self.assertIn(family, result["families"])
                self.assertIn(result["confidence"], {"high", "medium"})

    def test_classification_is_low_without_gemini_relationship(self) -> None:
        result = classify_candidate("A general Google Search interface update")
        self.assertEqual(result["confidence"], "low")
        self.assertEqual(result["matched_keywords"], [])


if __name__ == "__main__":
    unittest.main()
