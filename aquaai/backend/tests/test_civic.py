from civic import WASTE_CATEGORIES, build_civic_report


def test_known_category_produces_matching_report():
    result = build_civic_report("fountain", lat=37.3, lon=-121.9)
    assert result["category"]["label"] == WASTE_CATEGORIES["fountain"]["label"]
    assert "37.3" in result["email_draft"]
    assert result["open311_payload"]["service_code"] == "water_waste"


def test_unknown_category_falls_back_gracefully():
    result = build_civic_report("not_a_real_category", lat=1, lon=2)
    assert result["category"]["severity"] == "medium"
    assert result["report_id"].startswith("AQ-")


def test_report_ids_are_unique():
    ids = {build_civic_report("hose", 1, 2)["report_id"] for _ in range(20)}
    assert len(ids) == 20
