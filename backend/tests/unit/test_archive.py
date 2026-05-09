"""Tests for project archive extraction schema and distribution logic."""
from backend.core.agents.schemas import ArchiveExtraction, ResourcePerformance


def test_archive_extraction_defaults():
    a = ArchiveExtraction()
    assert a.project_summary == ""
    assert a.strategy_learnings == []
    assert a.audience_insights == []
    assert a.resource_performances == []
    assert a.content_insights == []
    assert a.campaign_category == ""
    assert a.channels_used == []


def test_archive_extraction_full():
    a = ArchiveExtraction(
        project_summary="美妆新品小红书种草campaign",
        strategy_learnings=["头部KOL带动长尾效应", "短视频比图文转化率高3倍"],
        audience_insights=["Z世代对成分党内容敏感", "晚间8-10点互动率最高"],
        resource_performances=[
            ResourcePerformance(
                name="李佳琦",
                type="kol",
                performance_summary="CPE 1.2, 超预期",
                metrics={"cpe": "1.2", "engagement_rate": "4.5%", "gmv": "200万"},
                recommendation="recommend",
            ),
            ResourcePerformance(
                name="某MCN",
                type="vendor",
                performance_summary="执行效率一般",
                metrics={},
                recommendation="neutral",
            ),
        ],
        content_insights=["开箱视频表现优于测评", "BGM选择影响完播率"],
        campaign_category="美妆新品上市",
        channels_used=["小红书", "抖音", "微信朋友圈"],
    )
    assert len(a.resource_performances) == 2
    assert a.resource_performances[0].name == "李佳琦"
    assert a.resource_performances[0].metrics["cpe"] == "1.2"
    assert a.resource_performances[1].recommendation == "neutral"
    assert a.campaign_category == "美妆新品上市"


def test_archive_extraction_serialization():
    a = ArchiveExtraction(
        project_summary="Tech launch",
        strategy_learnings=["LinkedIn outperformed expectations"],
        resource_performances=[
            ResourcePerformance(name="TechCrunch", type="media", recommendation="recommend")
        ],
    )
    data = a.model_dump()
    assert data["project_summary"] == "Tech launch"
    assert data["resource_performances"][0]["name"] == "TechCrunch"
    assert data["resource_performances"][0]["type"] == "media"


def test_resource_performance_defaults():
    rp = ResourcePerformance(name="TestKOL")
    assert rp.type == "kol"
    assert rp.performance_summary == ""
    assert rp.metrics == {}
    assert rp.recommendation == ""


def test_resource_performance_with_metrics():
    rp = ResourcePerformance(
        name="达人A",
        type="koc",
        metrics={"cpe": "3.5", "views": "10万"},
        recommendation="recommend",
    )
    assert rp.metrics["cpe"] == "3.5"
    assert rp.recommendation == "recommend"
