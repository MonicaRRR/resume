from resume_mvp.text_tidy import tidy_paste_artifacts, tidy_value_tree


def test_tidy_percent_slash_artifacts():
    assert tidy_paste_artifacts("提升 90/%") == "提升 90%"
    assert tidy_paste_artifacts(r"提升 90\%") == "提升 90%"
    assert tidy_paste_artifacts("普通 90% 保持") == "普通 90% 保持"


def test_tidy_strips_leaked_fact_uuids_from_text_only():
    uid = "f883cc34-59f3-42af-822b-994451866ef4"
    assert tidy_paste_artifacts(f"提升吞吐（{uid}）") == "提升吞吐"
    payload = {
        "value": f"完成迁移 {uid}",
        "source_fact_ids": [uid],
        "id": uid,
        "origin": "ai_rewrite",
    }
    cleaned = tidy_value_tree(payload)
    assert cleaned["value"] == "完成迁移"
    assert cleaned["source_fact_ids"] == [uid]
    assert cleaned["id"] == uid


def test_tidy_value_tree_nested():
    payload = {"value": r"吞吐提升 30/%，并完成 \item 迁移"}
    assert tidy_value_tree(payload)["value"] == "吞吐提升 30%，并完成 迁移"
