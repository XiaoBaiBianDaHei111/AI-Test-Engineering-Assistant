"""Requirements-analysis API tests (P2-007/009; P013 real mode)."""

import pytest


def _analyze(client, project_id, prd_text="一个带登录功能的任务管理系统 PRD"):
    return client.post(
        "/api/ai/analyze-requirement", json={"project_id": project_id, "prd_text": prd_text}
    )


@pytest.mark.real
def test_analyze_success(require_llm_key, sample_project, client):
    response = _analyze(client, sample_project["id"])
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in ("success", "partial")
    assert len(body["requirements"]) >= 1
    for req in body["requirements"]:
        assert req["status"] == "parsed"
        assert req["source"] == "ai"
        assert len(req["acceptance_criteria"]) >= 1
        assert req["doc_ref"].startswith("ai://analyze/")


def test_analyze_project_not_found(client):
    assert _analyze(client, 999).status_code == 404


def test_analyze_blank_prd(sample_project, client):
    response = client.post(
        "/api/ai/analyze-requirement", json={"project_id": sample_project["id"], "prd_text": "   "}
    )
    assert response.status_code == 422


@pytest.mark.real
def test_analyze_rerun_skips_existing(require_llm_key, sample_project, client):
    first = _analyze(client, sample_project["id"]).json()
    assert len(first["requirements"]) >= 1
    second = _analyze(client, sample_project["id"])
    assert second.status_code == 200
    body = second.json()
    assert body["status"] in ("success", "partial")
    assert len(body["warnings"]) >= 1


@pytest.mark.real
def test_analyze_long_text_segments_and_merges(require_llm_key, sample_project, client):
    long_prd = "# 章节一\n" + ("登录功能描述。 " * 1500) + "\n\n# 章节二\n" + ("任务管理描述。 " * 1500)
    response = _analyze(client, sample_project["id"], long_prd)
    assert response.status_code == 200
    body = response.json()
    titles = [r["title"] for r in body["requirements"]]
    assert len(titles) == len(set(titles))  # merged without duplicates
