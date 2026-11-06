"""Pure-helper tests for lecture/capstone bundling (no network)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "axiom-learning-os" / "scripts"))

from tsai_skills.chat import ist  # noqa: E402
from tsai_skills.client import ApiError  # noqa: E402
from tsai_skills.peers import name_to_logins, parse_gallery, repos_for_session  # noqa: E402
from tsai_skills.lecture import (  # noqa: E402
    assignments_for,
    doc_ids,
    find_plan_sheet,
    is_capstone,
    my_teams,
    parse_time,
    resolve_session,
    session_videos,
    srt_to_text,
    widget_data,
    widget_paths,
)

SESSIONS = [
    {"id": "a16", "title": "Session 16 - Scaling Laws", "order": 21},
    {"id": "a1", "title": "Session 1: From Neural Networks", "order": 3},
    {"id": "a12", "title": "Assignment Summary: Session 7", "order": 12},
    {"id": "c1", "title": "CAP - Capstone Lab 1", "order": 90},
    {"id": "c2", "title": "Capstone Lab 2", "order": 91},
]


class SessionMatching(unittest.TestCase):
    def test_number_id_and_fragment(self) -> None:
        self.assertEqual(resolve_session(SESSIONS, "16")["id"], "a16")
        self.assertEqual(resolve_session(SESSIONS, "S1")["id"], "a1")  # not S16, not 'Session 7' summary
        self.assertEqual(resolve_session(SESSIONS, "c2")["id"], "c2")
        self.assertEqual(resolve_session(SESSIONS, "lab 2")["id"], "c2")

    def test_ambiguous_or_missing_raises(self) -> None:
        with self.assertRaises(ApiError):
            resolve_session(SESSIONS, "capstone")  # matches both labs
        with self.assertRaises(ApiError):
            resolve_session(SESSIONS, "99")

    def test_assignments_link_by_session_id(self) -> None:
        rows = [{"id": "x", "sessionId": "a16"}, {"id": "y", "sessionId": "a1"}]
        self.assertEqual([a["id"] for a in assignments_for(SESSIONS[0], rows)], ["x"])


class CapstoneDetection(unittest.TestCase):
    def test_only_capstone_titled_or_order_90_plus(self) -> None:
        self.assertTrue(is_capstone({"title": "CAP - Capstone Lab 1", "order": 90}))
        self.assertTrue(is_capstone({"title": "Capstone Lab 2", "order": 91}))
        # S15 mentions the capstone in its title but is a regular lecture
        self.assertFalse(is_capstone({"title": "Session 15 - Stability, Debugging and Capstone", "order": 20}))


class LessonContent(unittest.TestCase):
    MD = (
        '<iframe src="/widgets/s16_fig_1.html" width="1"></iframe> text '
        '<iframe src="/widgets/s16_fig_1.html"></iframe><iframe src="/widgets/b.html"></iframe>\n'
        "[Transcript](https://docs.google.com/document/d/1j-b52_H5w/edit?usp=sharing)"
    )

    def test_widgets_deduped_in_order(self) -> None:
        self.assertEqual(widget_paths(self.MD), ["/widgets/s16_fig_1.html", "/widgets/b.html"])

    def test_doc_id(self) -> None:
        self.assertEqual(doc_ids(self.MD), ["1j-b52_H5w"])

    def test_videos_label_studio_vs_gmeet(self) -> None:
        s = {
            "studioVideoHtml": '<iframe src="https://www.youtube.com/embed/AAAAAAAAAAA?si=x">',
            "gmeetVideoHtml": '<iframe src="https://www.youtube.com/embed/BBBBBBBBBBB">',
            "lessons": [{"markdownContent": "https://youtu.be/AAAAAAAAAAA"}],
        }
        self.assertEqual([(v["role"], v["id"]) for v in session_videos(s)], [("studio", "AAAAAAAAAAA"), ("gmeet", "BBBBBBBBBBB")])


class WidgetData(unittest.TestCase):
    def test_json_literals_kept_js_literals_skipped(self) -> None:
        html = 'const DATA = {"teams":[1,2],"x":"a;b"};\nconst T = [{n:1}];\nlet K = [3,4];\nconst f = 3;'
        self.assertEqual(widget_data(html), {"DATA": {"teams": [1, 2], "x": "a;b"}, "K": [3, 4]})


class Time(unittest.TestCase):
    def test_parse_time(self) -> None:
        self.assertEqual(parse_time("5100"), 5100.0)
        self.assertEqual(parse_time("84:05"), 84 * 60 + 5)
        self.assertEqual(parse_time("1:24:05"), 5045.0)
        self.assertEqual(parse_time("1h24m5s"), 5045.0)

    def test_ist(self) -> None:
        self.assertEqual(ist("2026-10-31T03:00:00.000Z"), "Sat 31 Oct 2026, 08:30 IST")

    def test_srt_dedupes_rolling_captions(self) -> None:
        srt = (
            "1\n00:01:02,000 --> 00:01:04,000\nhello\n\n"
            "2\n00:01:04,000 --> 00:01:06,000\nhello\nworld\n\n"
            "3\n00:02:01,000 --> 00:02:03,000\nnext\n"
        )
        self.assertEqual(srt_to_text(srt), "[00:01] hello world\n[00:02] next\n")


class PlanSheet(unittest.TestCase):
    PLAN = {
        "teams": [{"id": 5, "name": "Architecture", "weeks": [], "mission": "m"}, {"id": 1, "name": "Data A"}],
        "packs": [{"student": "Revant Gupta", "coreId": 5, "w2Id": 1, "w3Id": 6, "pack": "p", "url": "https://signed"}],
        "leads": {"5": "Lead Five", "1": "Lead One"},
        "roster": {"5": ["Revant Gupta"]},
        "rotIn": {"1": {"w2": ["Revant Gupta"]}},
    }

    def test_find_plan_sheet(self) -> None:
        self.assertIs(find_plan_sheet({"w": {"DATA": self.PLAN, "K": [1]}}), self.PLAN)
        self.assertIsNone(find_plan_sheet({"w": {"K": [1]}}))

    def test_my_teams_strips_signed_url_and_skips_unknown_team(self) -> None:
        r = my_teams(self.PLAN, "revant gupta")
        self.assertNotIn("url", r["row"])
        self.assertEqual(r["teams"]["core"]["lead"], "Lead Five")
        self.assertEqual(r["teams"]["week2"]["rotationIn"], {"w2": ["Revant Gupta"]})
        self.assertNotIn("week3", r["teams"])  # team 6 is not in the sheet

    def test_unknown_student(self) -> None:
        self.assertIsNone(my_teams(self.PLAN, "Nobody")["row"])


class Peers(unittest.TestCase):
    GALLERY = (
        '<article class="card"><div class="thumb" style="background-image: url(\'/up/s3-001.png\');"></div>'
        '<div class="content"><div class="title"><a href="https://a.netlify.app/" target="_blank">gaurav khare</a></div>'
        '<div class="desc">S3 &amp; more</div></div></article>'
        '<article class="card"><div class="content"><div class="title"><a href="https://b.app">Ramesh</a></div></div></article>'
    )

    def test_gallery_cards(self) -> None:
        rows = parse_gallery(self.GALLERY)
        self.assertEqual([r["student"] for r in rows], ["gaurav khare", "Ramesh"])
        self.assertEqual(rows[0]["url"], "https://a.netlify.app/")
        self.assertEqual(rows[0]["description"], "S3 & more")
        self.assertEqual(rows[1]["description"], "")

    def test_name_to_logins_uses_pr_name_line(self) -> None:
        prs = [
            {"author": {"login": "revantg"}, "body": "Name: Revant Gupta\nPack: x"},
            {"author": {"login": "revantgupta"}, "body": "intro\nname:  revant gupta "},
            {"author": {"login": "bot"}, "body": "no header"},
        ]
        self.assertEqual(name_to_logins(prs), {"revant gupta": ["revantg", "revantgupta"]})

    def test_repos_for_session_skips_forks_and_matches_token_not_substring(self) -> None:
        repos = [
            {"name": "erav5-loss-harness", "description": "ERA Session 9 - the loss harness", "isFork": False},
            {"name": "s9-notes", "description": "", "isFork": False},
            {"name": "erav5-s10-loop", "description": "Session 10", "isFork": False},
            {"name": "x", "description": "Session 9 fork", "isFork": True},
            {"name": "s99-misc", "description": "Session 90", "isFork": False},
        ]
        self.assertEqual([r["name"] for r in repos_for_session(repos, 9)], ["erav5-loss-harness", "s9-notes"])


if __name__ == "__main__":
    unittest.main()
