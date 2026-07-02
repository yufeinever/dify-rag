from __future__ import annotations

from .schemas import GeneratePosterRequest, PosterAsset


_BEAR_EXCLUSION_KEYWORDS = (
    "不要小熊",
    "不用小熊",
    "不需要小熊",
    "去掉小熊",
    "不要ip",
    "不用ip",
    "不需要ip",
    "不要 IP",
    "不用 IP",
    "不要卡通",
    "不用卡通",
    "不要吉祥物",
    "不用吉祥物",
    "纯产品图",
    "纯背景图",
    "纯商务风",
)


def should_use_default_bear(request: GeneratePosterRequest) -> bool:
    text_parts = [
        request.user_query or "",
        request.optimized_prompt or "",
        request.brief.theme,
        request.brief.background or "",
        request.brief.brand_constraints or "",
        request.brief.main_title or "",
        request.brief.subtitle or "",
        " ".join(request.brief.special_elements),
        " ".join(request.brief.selling_points),
    ]
    normalized = " ".join(text_parts).lower()
    return not any(keyword.lower() in normalized for keyword in _BEAR_EXCLUSION_KEYWORDS)


def build_prompt(request: GeneratePosterRequest, llm_model: str) -> str:
    brief = request.brief
    asset_lines = [_format_asset(asset, index) for index, asset in enumerate(request.assets[:8], start=1)]
    copy_policy = (
        "Leave clean negative space for deterministic Chinese text overlays. "
        "Do not render readable Chinese or English words inside the image."
        if request.overlay_text
        else "Render the poster as a complete visual composition."
    )
    elements = ", ".join(brief.special_elements) if brief.special_elements else "none specified"
    selling_points = "; ".join(brief.selling_points) if brief.selling_points else "none specified"
    assets = "\n".join(asset_lines) if asset_lines else "No retrieved production assets were provided."
    bear_policy = (
        "Default MMB bear IP rule: include the MMB bear unless the user explicitly asks for no bear/IP/cartoon/mascot, "
        "or asks for a pure product image, pure background image, or pure business style. "
        "Use the attached MMB bear reference image as the identity anchor: orange plush bear, rounded big eyes, black nose, "
        "light belly, friendly MMB mascot proportions. The bear may adapt its pose to the campaign, such as waving or "
        "holding a sign for promotions, raising a cup for beer, celebrating festivals, or pointing to a product or reservation entry. "
        "Keep it naturally integrated at a corner, foreground side, or interaction area, and do not let it dominate the main visual."
        if should_use_default_bear(request)
        else "Default MMB bear IP rule: do not include the MMB bear, IP mascot, or cartoon character because the user excluded it."
    )
    return (
        f"Use {llm_model} planning assumptions to create a vertical marketing poster background.\n"
        f"Theme: {brief.theme}\n"
        f"Audience: {brief.audience or 'general business audience'}\n"
        f"Background style: {brief.background or 'polished commercial visual, premium, clean'}\n"
        f"Special elements: {elements}\n"
        f"Main title to reserve space for: {brief.main_title or brief.theme}\n"
        f"Subtitle to reserve space for: {brief.subtitle or 'none specified'}\n"
        f"Selling points to reserve space for: {selling_points}\n"
        f"Brand constraints: {brief.brand_constraints or 'keep it professional, no trademark distortion'}\n"
        f"Production asset references:\n{assets}\n"
        f"{bear_policy}\n"
        "Composition requirements: vertical poster, strong focal point, high contrast, mobile-feed readability, "
        "safe top and lower text zones, no clutter behind future text. "
        f"Text policy: {copy_policy}"
    )


def _format_asset(asset: PosterAsset, index: int) -> str:
    tags = ", ".join(asset.tags) if asset.tags else "no tags"
    return f"{index}. {asset.title or 'Untitled asset'}; tags: {tags}; description: {asset.description or 'none'}; url: {asset.url or 'none'}"
