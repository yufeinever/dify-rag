import asyncio
import base64
import io
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from app.openai_client import OpenAIImageClient
from app.prompting import should_use_default_bear
from app.schemas import GeneratePosterRequest, PosterAsset, PosterBrief


def _png_data_url(color: str) -> str:
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), color).save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode(
        "ascii"
    )


def _settings(default_bear_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        default_bear_reference_enabled=True,
        default_bear_reference_path=default_bear_path,
        reference_image_max_bytes=1024 * 1024,
        reference_image_timeout=1.0,
        reference_base_url="https://ai.example.test",
        image_request_timeout=1.0,
        image_mode="responses",
        llm_model="test-model",
        openai_api_key="test-key",
        openai_base_url="https://example.invalid",
        allow_mock_openai=False,
    )


def _request(assets: list[PosterAsset]) -> GeneratePosterRequest:
    return GeneratePosterRequest(
        brief=PosterBrief(theme="video first frame"), assets=assets, overlay_text=False
    )


def test_reference_images_are_ordered_by_priority_and_sent_as_real_images(tmp_path):
    scene = _png_data_url("blue")
    character = _png_data_url("red")
    other = _png_data_url("green")
    client = OpenAIImageClient(_settings(tmp_path / "missing.png"))
    request = _request(
        [
            PosterAsset(kind="scene", source="user_scene", url=scene),
            PosterAsset(kind="other", source="user_other", url=other),
            PosterAsset(kind="character", source="user_character", url=character),
        ]
    )
    captured = {}

    async def fake_post_json(url, payload):
        captured["payload"] = payload
        return {
            "output": [
                {
                    "type": "image_generation_call",
                    "result": base64.b64encode(b"image").decode(),
                }
            ]
        }

    client._post_json = fake_post_json
    _, stats = asyncio.run(client._generate_with_responses(request, "prompt"))

    content = captured["payload"]["input"][0]["content"]
    assert [item["image_url"] for item in content[1:]] == [character, scene, other]
    assert stats == {
        "requested": 3,
        "loaded": 3,
        "character": 1,
        "scene": 1,
        "other": 1,
        "default_bear": 0,
        "generated_character": 0,
    }


def test_user_character_disables_default_bear(tmp_path):
    bear_path = tmp_path / "bear.png"
    bear_path.write_bytes(base64.b64decode(_png_data_url("orange").split(",", 1)[1]))
    request = _request([PosterAsset(kind="character", url=_png_data_url("red"))])
    client = OpenAIImageClient(_settings(bear_path))

    references, stats = asyncio.run(client._prepare_reference_images(request))

    assert len(references) == 1
    assert stats["default_bear"] == 0
    assert should_use_default_bear(request) is False


def test_default_bear_is_used_when_no_character_reference_exists(tmp_path):
    bear_path = tmp_path / "bear.png"
    bear_path.write_bytes(base64.b64decode(_png_data_url("orange").split(",", 1)[1]))
    request = _request([])
    client = OpenAIImageClient(_settings(bear_path))

    references, stats = asyncio.run(client._prepare_reference_images(request))

    assert [kind for kind, _ in references] == ["character"]
    assert stats["requested"] == 0
    assert stats["loaded"] == 1
    assert stats["default_bear"] == 1


def test_legacy_default_bear_asset_is_treated_as_character(tmp_path):
    bear_path = tmp_path / "bear.png"
    bear_path.write_bytes(base64.b64decode(_png_data_url("orange").split(",", 1)[1]))
    request = _request(
        [
            PosterAsset(
                url="/files/expired/image-preview",
                source="default_mmb_bear",
                tags=["默认参考图"],
            )
        ]
    )
    client = OpenAIImageClient(_settings(bear_path))

    references, stats = asyncio.run(client._prepare_reference_images(request))

    assert [kind for kind, _ in references] == ["character"]
    assert stats["character"] == 1
    assert stats["default_bear"] == 1


def test_legacy_prompt_only_asset_is_not_downloaded(tmp_path):
    client = OpenAIImageClient(_settings(tmp_path / "missing.png"))
    request = _request(
        [PosterAsset(url="/files/legacy/image-preview", title="legacy knowledge asset")]
    )

    references, stats = asyncio.run(client._prepare_reference_images(request))

    assert references == []
    assert stats["requested"] == 1
    assert stats["loaded"] == 0


def test_relative_reference_url_uses_configured_base_url(tmp_path):
    client = OpenAIImageClient(_settings(tmp_path / "missing.png"))
    captured = {}

    async def fake_download(url):
        captured["url"] = url
        return _png_data_url("blue")

    client._download_reference_image = fake_download
    asyncio.run(client._load_reference_image("/files/example/image-preview"))

    assert captured["url"] == "https://ai.example.test/files/example/image-preview"


def test_missing_reference_url_fails_instead_of_falling_back_to_text(tmp_path):
    client = OpenAIImageClient(_settings(tmp_path / "missing.png"))
    request = _request([PosterAsset(kind="scene", url=None)])

    with pytest.raises(ValueError, match="missing a URL"):
        asyncio.run(client._prepare_reference_images(request))


def test_invalid_reference_payload_fails(tmp_path):
    client = OpenAIImageClient(_settings(tmp_path / "missing.png"))
    invalid = "data:image/png;base64," + base64.b64encode(b"not an image").decode(
        "ascii"
    )

    with pytest.raises(ValueError, match="not a valid image"):
        asyncio.run(client._load_reference_image(invalid))


def test_reference_kind_limit_is_enforced(tmp_path):
    client = OpenAIImageClient(_settings(tmp_path / "missing.png"))
    request = _request(
        [PosterAsset(kind="character", url=_png_data_url("red")) for _ in range(4)]
    )

    with pytest.raises(ValueError, match="maximum is 3"):
        asyncio.run(client._prepare_reference_images(request))


def test_explicit_default_bear_flag_is_honored(tmp_path):
    bear_path = tmp_path / "bear.png"
    bear_path.write_bytes(base64.b64decode(_png_data_url("orange").split(",", 1)[1]))
    request = _request([])
    request.use_default_bear = False
    client = OpenAIImageClient(_settings(bear_path))

    references, stats = asyncio.run(client._prepare_reference_images(request))

    assert references == []
    assert stats["default_bear"] == 0


def test_generated_character_does_not_consume_user_character_limit(tmp_path):
    assets = [PosterAsset(kind="character", url=_png_data_url("red")) for _ in range(3)]
    assets.append(
        PosterAsset(
            kind="character", source="generated_character", url=_png_data_url("orange")
        )
    )
    client = OpenAIImageClient(_settings(tmp_path / "missing.png"))

    references, stats = asyncio.run(client._prepare_reference_images(_request(assets)))

    assert len(references) == 4
    assert stats["generated_character"] == 1
