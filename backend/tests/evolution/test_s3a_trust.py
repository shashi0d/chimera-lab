"""S3a trust layer (mock mode): the plan-blind critic protocol (part 2), citation verification (part 4) and the
R10 research cards (part 5)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from app.evolution import critic as C
from app.evolution.citecheck import CitationVerifier, classify, norm, quote_found
from app.evolution.data import cards
from app.evolution.genome import validate_plan
from app.evolution.inspect import inspect
from app.evolution.live import (
    build_ask_request,
    build_describe_request,
    parse_ask_response,
    parse_describe_response,
)
from app.evolution.resolve import subject_terms
from tests.evolution.conftest import plan_for

REPO = Path(__file__).resolve().parents[3]
FIX = Path(__file__).resolve().parents[1] / "fixtures" / "recorded" / "s2"


class Meter:
    def __init__(self) -> None:
        self.events: list[str] = []

    async def call(self, kind, purpose, aw):
        self.events.append(purpose)
        return await aw


class NoSeg:
    model_id = "no-sam"

    async def segment(self, image: bytes, label: str) -> bytes:
        import io

        from PIL import Image

        out = io.BytesIO()
        Image.new("L", (32, 32), 0).save(out, "PNG")
        return out.getvalue()


@pytest.fixture
def e4_engine(tmp_path: Path):
    from app.evolution.engine import EvoEngine
    from app.services import build_services
    from tests.conftest import make_settings

    store = tmp_path / "learned.json"
    shutil.copy(FIX / "learned_beetle_e4.json", store)
    return EvoEngine(build_services(make_settings(tmp_path, evo_learned_path=str(store))))


async def _beetle_bear(e4_engine):
    s = (await e4_engine.resolve("rhinoceros beetle")).animal
    d = (await e4_engine.resolve("brown bear")).animal
    g, r = e4_engine.seed_plan(s, d, host_pick="dam", design_mode="speculative")
    return e4_engine.finish(g, r), r


class Critic:
    """A scripted plan-blind critic: a description and checklist answers keyed by question id."""

    def __init__(self, describe: dict[str, Any], answers: dict[str, str] | None = None, qs=None) -> None:
        self.d, self.a, self.qs = describe, answers or {}, qs
        self.seen_texts: list[list[str]] = []

    async def describe(self, image: bytes) -> dict[str, Any]:
        return self.d

    async def ask(self, image: bytes, texts: list[str]) -> dict[str, Any]:
        self.seen_texts.append(texts)
        ids = {q.text: q.id for q in self.qs}
        return {"answers": [{"item": t, "answer": self.a.get(ids[t], C.EXPECTED[t])} for t in texts]}


def _clean(**counts) -> dict[str, Any]:
    base = {"description": "A brown bear with a glossy horn on its brow and a domed plated shield on its back.",
            "parts": [{"part": "horn", "looks_like": "curved glossy horn", "where": "brow"},
                      {"part": "plates", "looks_like": "glossy chitin plates", "where": "back"}],
            "attached_objects": [], "animals": ["brown bear", "rhinoceros beetle"], "separate_bodies": 1, "heads": 1,
            "walking_legs": 4, "wings": 0, "extra_limb_pieces": 0}
    return {**base, **counts}


# ------------------------------------------------------------------ part 2: questions


async def test_questions_are_balanced_and_plan_blind(e4_engine):
    g, _ = await _beetle_bear(e4_engine)
    qs = C.questions(g, e4_engine.tax)
    assert sum(q.expect == "no" for q in qs) * 2 >= len(qs)  # at least half expect "no"
    plan_words = ("donor", "patch", "plan", "host", "license", "PATCH", "OVERLAY")
    assert not any(w in q.text for q in qs for w in plan_words)  # visible features only
    ids = {q.id for q in qs}
    assert {"frame", "head", "no_wings", "whole_animal", "insect_legs", "grows_out", "on_top", "continuous",
            "scattered"} <= ids  # S3b: legs and shoulders are inside the exoskeleton extent (RC-R10-16)


async def test_integration_questions_use_the_owner_wording(e4_engine):
    g, _ = await _beetle_bear(e4_engine)
    q = {x.id: x for x in C.questions(g, e4_engine.tax)}
    assert "grow out of the body with a natural transition" in q["grows_out"].text
    assert "fur stopping at a shield's edge" in q["grows_out"].text and q["grows_out"].expect == "yes"
    assert "attached on top of the fur" in q["on_top"].text and q["on_top"].expect == "no"
    assert "one continuous structure" in q["continuous"].text and q["scattered"].expect == "no"
    assert q["grows_out"].fix.startswith("Show the hard, glossy chitin plates")  # worded from the plan, not a symptom


def test_soft_skin_patches_get_no_integration_questions(engine):
    # RC-R10-12 covers protective coverings only (iteration 2): the eagle x octopus skin patches get presence only
    g, _ = plan_for(engine, "eagle", "octopus")
    ids = {q.id for q in C.questions(g, engine.tax)}
    assert "cover_present" in ids and not {"grows_out", "on_top", "continuous"} & ids


def test_hybrids_get_a_mixed_frame_question_and_unplanned_donor_features_are_asked(engine, tax):
    g, _ = plan_for(engine, "donkey", "horse")
    frame = next(q for q in C.questions(g, engine.tax) if q.id == "frame")
    assert "mixing a donkey and a horse" in frame.text  # not "a horse body shape" (iteration 2)
    raw = json.loads((REPO / "docs/evolution/live/e4/b_axolotl_x_pangolin/plan.json").read_text(encoding="utf-8"))
    pangolin = json.loads((REPO / "data/learned_animals.json").read_text(encoding="utf-8"))["animals"]["chinese_pangolin"]
    from app.evolution.resolve import animal_from_entry

    t = tax.copy()
    t.add(animal_from_entry(pangolin), [])
    qs = {q.id: q for q in C.questions(validate_plan(raw), t)}
    gills = [q for q in qs.values() if "gills" in q.text]
    assert gills and all(q.expect == "no" for q in gills)  # the E4 plan dropped no gills flag; the donor has them


def test_expected_counts_follow_the_limb_plan(engine):
    g, _ = plan_for(engine, "lion", "eagle")
    assert C.expected_counts(g, engine.tax) == {"separate_bodies": 1, "heads": 1, "walking_legs": 2, "wings": 2,
                                                "extra_limb_pieces": 0}
    g, _ = plan_for(engine, "eagle", "octopus")
    assert C.expected_counts(g, engine.tax)["extra_limb_pieces"] is None  # a tentacle tail is planned


# ------------------------------------------------------------------ part 2: description matching


def test_negations_and_wing_cases_are_not_sightings():
    assert C.seen_concepts("No wings, tentacles, or additional limbs are visible.") == set()
    assert C.seen_concepts("no distinct spots or stripes beyond shading") == set()
    assert C.seen_concepts("several ridged, wing-cover-like plates on the back") == {"plates"}
    assert "mane" not in C.seen_concepts("mane: a shaggy ruff of longer feathers and fur")
    assert "mane" in C.seen_concepts("a full golden mane around the head")
    assert C.seen_concepts("two small beetles clinging to the shoulder") >= {"whole_body"}
    assert "stripes" not in C.seen_concepts("a thin dark dorsal stripe along the back")  # iteration 3
    assert "stripes" in C.seen_concepts("bold dark stripes across the flanks")


def test_soft_surface_presence_is_informational(engine):
    g, _ = plan_for(engine, "eagle", "octopus")
    q = next(x for x in C.questions(g, engine.tax) if x.id == "cover_present")
    assert q.group == "surface"
    raws = {"a": C.Raw(describe={}, answers={q.text: "no"})}
    res = C.evaluate(raws, g, engine.tax, None)
    row = next(r for r in res["rows"] if r["key"] == "cover_present")
    assert row["status"] == "fail" and row not in res["signals"]  # recorded, never a fail signal


async def test_description_catches_extras_and_omissions(e4_engine):
    g, _ = await _beetle_bear(e4_engine)
    m = C.match_description({"description": "A bear with insect wings and jointed insect legs on its legs.",
                             "parts": [], "attached_objects": []}, g, e4_engine.tax)
    assert {"wings", "insect_legs"} <= set(m["extras"])
    assert set(m["omissions"]) == {"horn", "plates"}
    assert C.match_description(_clean(), g, e4_engine.tax)["extras"] == []


# ------------------------------------------------------------------ part 2: two critics


async def test_a_clean_image_passes_with_two_agreeing_critics(e4_engine):
    g, r = await _beetle_bear(e4_engine)
    qs = C.questions(g, e4_engine.tax)
    a, b = Critic(_clean(), qs=qs), Critic(_clean(), qs=qs)
    res, raws = await C.protocol(b"img", g, e4_engine.tax, {"spark_open": a, "meta_spark": b}, Meter(), r)
    assert res["verdict"] == "pass" and res["signals"] == []
    assert a.seen_texts[0] == [q.text for q in qs]  # the critic gets question texts only, never expected answers


async def test_disagreement_is_uncertain_and_agreement_on_a_miss_fails(e4_engine):
    g, r = await _beetle_bear(e4_engine)
    qs = C.questions(g, e4_engine.tax)
    a = Critic(_clean(), {"on_top": "yes", "scattered": "yes"}, qs)
    b = Critic(_clean(), {"scattered": "yes"}, qs)
    res, _ = await C.protocol(b"img", g, e4_engine.tax, {"a": a, "b": b}, Meter(), r)
    st = {s["key"]: s["status"] for s in res["signals"]}
    assert st == {"on_top": "uncertain", "scattered": "fail"}
    assert res["verdict"] == "fail"  # uncertain is a fail signal


async def test_counts_and_third_animals_from_the_free_description(e4_engine):
    g, r = await _beetle_bear(e4_engine)
    qs = C.questions(g, e4_engine.tax)
    d = _clean(separate_bodies=4, wings=2, animals=["brown bear", "rhinoceros beetle", "zebra"])
    res, _ = await C.protocol(b"img", g, e4_engine.tax, {"a": Critic(d, qs=qs), "b": Critic(d, qs=qs)}, Meter(), r)
    st = {s["key"]: s["status"] for s in res["signals"]}
    assert st["separate_bodies"] == "fail" and st["wings"] == "fail" and st["third_animal"] == "fail"


async def test_a_failed_critic_is_uncertain_not_a_crash(e4_engine):
    g, r = await _beetle_bear(e4_engine)
    qs = C.questions(g, e4_engine.tax)

    class Broken(Critic):
        async def ask(self, image, texts):
            raise ValueError("cut off at the cap")

    broken = Broken(_clean(), qs=qs)
    meter = Meter()
    res, raws = await C.protocol(b"img", g, e4_engine.tax, {"a": broken, "b": Critic(_clean(), qs=qs)}, meter, r)
    assert raws["a"].error and any(s["key"] == "error_a" and s["status"] == "uncertain" for s in res["signals"])
    assert meter.events.count("ask:a") == 2  # one retry before giving up


async def test_inspect_failures_carry_plan_worded_fixes_and_sam_can_confirm_parts(e4_engine):
    g, r = await _beetle_bear(e4_engine)
    qs = C.questions(g, e4_engine.tax)
    no_horn = {"part_european_rhinoceros_beetle_head_horn": "no"}
    crit = {"a": Critic(_clean(), {**no_horn, "on_top": "yes"}, qs), "b": Critic(_clean(), {**no_horn, "on_top": "yes"}, qs)}
    out = await inspect(b"img", g, e4_engine.tax, crit, NoSeg(), Meter(), r)
    keys = {f["key"]: f for f in out["failures"]}
    assert "on_top" in keys and keys["on_top"]["fix"].startswith(
        "Show the hard, glossy chitin plates with fine seams grown in the skin")
    assert "part_european_rhinoceros_beetle_head_horn" in keys  # critics said no and the empty mask cannot rescue it
    assert out["sam_calls"] == 1 and out["protocol"] == "plan-blind (S3a)"


# ------------------------------------------------------------------ part 2: wire format


def test_describe_and_ask_requests_are_plan_blind_and_parse():
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (8, 8)).save(buf, "PNG")
    png = buf.getvalue()
    d = build_describe_request("m", png)
    assert d["messages"][1]["content"][0]["text"] == "Describe this creature, then count."  # the image and nothing else
    a = build_ask_request("m", png, ["Is there a horn?", "Are there wings?"])
    assert "1. Is there a horn?\n2. Are there wings?" in a["messages"][1]["content"][0]["text"]
    assert a["response_format"]["json_schema"]["schema"]["properties"]["answers"]["items"] == {
        "type": "string", "enum": ["yes", "no", "unclear"]}  # no copied text (iteration 2: Spark Open ran away)
    payload = {"choices": [{"message": {"content": json.dumps({"answers": ["yes", "maybe"], "notes": ""})}}]}
    out = parse_ask_response(payload, ["q1", "q2", "q3"])
    assert [x["answer"] for x in out["answers"]] == ["yes", "unclear", "unclear"]
    payload = {"choices": [{"message": {"content": json.dumps({"description": "x", "parts": [], "animals": ["bear"],
                                                               "attached_objects": [], "separate_bodies": "2",
                                                               "heads": 1, "walking_legs": 4, "wings": 0,
                                                               "extra_limb_pieces": 0})}}]}
    assert parse_describe_response(payload)["separate_bodies"] == 2


# ------------------------------------------------------------------ part 4: citation verification


@pytest.mark.parametrize("url,status", [
    ("https://animaldiversity.org/accounts/Manidae/", "tier1"),
    ("https://ucmp.berkeley.edu/mammal/mammoth.html", "tier1"),
    ("https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9975656/", "tier1"),
    ("https://www.rvc.ac.uk/x.pdf", "tier1"),
    ("https://animals.sandiegozoo.org/animals/axolotl", "tier2"),
    ("https://www.nationalgeographic.com/animals/amphibians/facts/axolotl", "tier2"),
    ("https://jacksonvillezoo.org/mammoth", "tier2"),
    ("https://museumstore.hmns.org/mammoth", "rejected"),
    ("https://www.merriam-webster.com/dictionary/spiracle", "rejected"),
    ("https://kids.britannica.com/kids/article/mammoth/275651", "rejected"),
    ("https://en.wikipedia.org/wiki/Oryctes_nasicornis", "rejected"),
    ("https://animalia.bio/chinese-pangolin", "rejected"),
    ("https://monaconatureencyclopedia.com/oryctes-nasicornis/", "unlisted"),
    ("", "no_url"),
])
def test_source_tiers(url, status):
    assert classify(url)["status"] == status


def test_quote_matching_is_normalized_and_handles_ellipses():
    page = "<p>Pangolin bodies are covered in keratinous&nbsp;scales that act as <b>body armor</b>.</p>"
    from app.evolution.citecheck import page_text

    text = page_text(page)
    assert quote_found("Pangolin bodies are covered in keratinous scales that act as body armor.", text)
    assert quote_found("“Pangolin bodies” ... act as body armor", text)
    assert not quote_found("Pangolin bodies are covered in fur", text)
    assert norm("Café ’s") == ["cafe", "s"]


async def test_verifier_statuses():
    pages = {"https://animaldiversity.org/a": "<h1>Chinese pangolin</h1> Pangolins eat ants and termites.",
             "https://animaldiversity.org/whale": "Whales use their lungs to breathe air."}

    async def fetch(url):
        if url not in pages:
            raise OSError("403")
        return pages[url]

    v = CitationVerifier(fetch)
    out = await v.verify({
        "diet": {"url": "https://animaldiversity.org/a", "evidence": "Pangolins eat ants and termites."},
        "habitat": {"url": "https://animaldiversity.org/a", "evidence": "Pangolins live in deserts."},
        "breathing": {"url": "https://animaldiversity.org/whale", "evidence": "use their lungs to breathe air"},
        "movement": {"url": "https://animalia.bio/x", "evidence": "it can climb"},
        "covering": {"url": "https://animaldiversity.org/blocked", "evidence": "keratin scales"},
        "mouthparts": {"url": "https://animaldiversity.org/a", "evidence": ""},
    }, subject_terms({"common_name": "Chinese pangolin", "scientific_name": "Manis pentadactyla"}))
    st = {f: c["status"] for f, c in out.items()}
    assert st == {"diet": "supported", "habitat": "quote_not_found", "breathing": "off_subject",
                  "movement": "rejected_source", "covering": "fetch_failed", "mouthparts": "no_quote"}
    assert out["diet"]["provenance"] == "web-cited"
    assert all(c["provenance"] == "model-estimated" for f, c in out.items() if f != "diet")


async def test_new_animal_citations_pass_through_the_verifier(engine):
    # mock: fixture citations on example.org, a fixture page that names the animal and holds every quote
    await engine.resolve("woolly mammoth")
    entry = engine.resolver.store.lookup("woolly mammoth")[0]
    assert entry["citation_checks"]["diet"]["status"] == "supported"
    assert entry["provenance"]["diet"] == "web-cited"


async def test_a_citation_that_fails_verification_falls_back_to_model_estimated(engine):
    async def bad_page(url):
        return "<p>nothing relevant here about woolly mammoth</p>"

    engine.resolver.verifier.fetch = bad_page
    await engine.resolve("woolly mammoth")
    entry = engine.resolver.store.lookup("woolly mammoth")[0]
    assert entry["provenance"]["diet"].startswith("model-estimated (citation not accepted: the quote does not appear")
    assert "diet" not in entry["citations"] and entry["traits_note"].startswith("0 of 13 fields web-cited")


async def test_reverify_moves_failing_citations_out_of_a_learned_entry(engine):
    await engine.resolve("woolly mammoth")
    store = engine.resolver.store
    aid = store.lookup("woolly mammoth")[0]["id"]
    store.data["animals"][aid]["citations"]["diet"]["url"] = "https://kids.britannica.com/mammoth"
    rep = await engine.resolver.reverify("woolly mammoth")
    entry = store.data["animals"][aid]
    assert rep["checks"]["diet"]["status"] == "rejected_source"
    assert "diet" not in entry["citations"] and entry["rejected_citations"]["diet"]["status"] == "rejected_source"
    assert entry["provenance"]["diet"].startswith("model-estimated (citation not accepted: kids.britannica.com")
    assert entry["provenance"]["habitat"] == "web-cited"  # a passing citation stays


# ------------------------------------------------------------------ part 5: R10 cards


def test_r10_cards_are_in_the_rule_book():
    book = cards()
    for cid, strength, status in (("RC-R10-12", "soft", "VERIFIED"), ("RC-R10-13", "soft", "VERIFIED"),
                                  ("RC-R10-14", "soft", "UNVERIFIED")):
        c = book[cid]
        assert (c.strength, c.status) == (strength, status)
    assert "replaces the host's covering" in book["RC-R10-12"].rule
    assert "two halves meeting at a midline seam" in book["RC-R10-13"].rule


def test_build_rule_cards_reads_two_digit_research_numbers(tmp_path):
    out = tmp_path / "cards.json"
    res = subprocess.run([sys.executable, str(REPO / "scripts/build_rule_cards.py"),
                          str(REPO / "docs/evolution/research"), str(out)], capture_output=True, text=True)
    assert res.returncode == 0, res.stdout + res.stderr
    ids = [c["id"] for c in json.loads(out.read_text(encoding="utf-8"))]
    assert ids[-16:] == [f"RC-R10-{i:02d}" for i in range(1, 17)]  # sorted by doc number, R10 after R9
    assert out.read_text(encoding="utf-8") == (REPO / "data/rule_cards.json").read_text(encoding="utf-8")
