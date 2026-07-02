from app.renderer import compose_poster
from app.schemas import GeneratePosterRequest, PosterBrief


def test_compose_mock_poster_size():
    request = GeneratePosterRequest(
        brief=PosterBrief(
            theme="端午节啤酒促销",
            background="清爽绿色背景",
            special_elements=["粽子", "麦芽"],
            main_title="端午清爽开饮",
            subtitle="限时组合优惠",
            selling_points=["精选麦芽", "冰镇畅饮", "扫码预约"],
        ),
        size="1080x1440",
        overlay_text=True,
    )
    poster = compose_poster(None, request)
    assert poster.size == (1080, 1440)
    assert poster.mode == "RGB"
