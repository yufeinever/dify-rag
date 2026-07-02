from __future__ import annotations

from .schemas import GeneratePosterRequest, PosterAsset


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
        "Composition requirements: vertical poster, strong focal point, high contrast, mobile-feed readability, "
        "safe top and lower text zones, no clutter behind future text. "
        f"Text policy: {copy_policy}"
    )


def _format_asset(asset: PosterAsset, index: int) -> str:
    tags = ", ".join(asset.tags) if asset.tags else "no tags"
    return f"{index}. {asset.title or 'Untitled asset'}; tags: {tags}; description: {asset.description or 'none'}; url: {asset.url or 'none'}"
