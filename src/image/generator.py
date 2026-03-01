"""
Meme Image Generator
Supports: DALL-E 3 (OpenAI), Stable Diffusion (local/API), and Pillow fallback.
"""
from __future__ import annotations

import base64
import io
import logging
import random
from pathlib import Path
from typing import Literal, Optional

import httpx
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

GeneratorBackend = Literal["dalle", "stable_diffusion", "pillow"]

# Meme-style color palettes
MEME_PALETTES = [
    [(255, 193, 7), (33, 33, 33)],    # Degen gold
    [(0, 200, 83), (0, 0, 0)],         # Moon green
    [(229, 57, 53), (255, 255, 255)],  # Rug red
    [(63, 81, 181), (255, 255, 255)],  # BSC blue
    [(156, 39, 176), (255, 255, 255)], # Degen purple
]


class MemeImageGenerator:
    """
    Generates token logos via multiple backends with fallback chain:
    DALL-E → Stable Diffusion → Pillow procedural
    """

    def __init__(
        self,
        openai_api_base: str = "https://api.openai.com/v1",
        openai_api_key: str = "",
        sd_api_url: str = "http://localhost:7860",
        output_dir: str = "generated_images",
        backend: GeneratorBackend = "dalle",
    ) -> None:
        self.openai_api_base = openai_api_base.rstrip("/")
        self.openai_api_key = openai_api_key
        self.sd_api_url = sd_api_url.rstrip("/")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.backend = backend
        self._http = httpx.AsyncClient(timeout=120)

    async def generate(
        self,
        prompt: str,
        symbol: str,
        backend: Optional[GeneratorBackend] = None,
    ) -> Path:
        """
        Generate a meme image for the given prompt.
        Returns path to the saved PNG file.
        """
        backend = backend or self.backend
        output_path = self.output_dir / f"{symbol.lower()}_{random.randint(1000, 9999)}.png"

        if backend == "dalle":
            try:
                return await self._generate_dalle(prompt, symbol, output_path)
            except Exception as e:
                logger.warning("DALL-E failed: %s — falling back to Pillow", e)

        if backend in ("dalle", "stable_diffusion"):
            try:
                return await self._generate_sd(prompt, symbol, output_path)
            except Exception as e:
                logger.warning("SD failed: %s — falling back to Pillow", e)

        return self._generate_pillow(symbol, output_path)

    async def _generate_dalle(self, prompt: str, symbol: str, output_path: Path) -> Path:
        enhanced_prompt = (
            f"Meme token logo for cryptocurrency '{symbol}'. "
            f"{prompt}. "
            "Style: bold, vibrant, crypto meme art. "
            "Square format, high contrast, no text in image."
        )
        resp = await self._http.post(
            f"{self.openai_api_base}/images/generations",
            headers={"Authorization": f"Bearer {self.openai_api_key}"},
            json={
                "model": "dall-e-3",
                "prompt": enhanced_prompt,
                "n": 1,
                "size": "1024x1024",
                "response_format": "b64_json",
            },
        )
        resp.raise_for_status()
        b64 = resp.json()["data"][0]["b64_json"]
        img_data = base64.b64decode(b64)
        img = Image.open(io.BytesIO(img_data)).convert("RGBA")
        img = img.resize((512, 512), Image.LANCZOS)
        img.save(output_path, "PNG")
        logger.info("DALL-E image saved: %s", output_path)
        return output_path

    async def _generate_sd(self, prompt: str, symbol: str, output_path: Path) -> Path:
        enhanced = (
            f"meme token logo, {prompt}, "
            "crypto art, bold colors, square logo, high quality, "
            "professional design, no text"
        )
        resp = await self._http.post(
            f"{self.sd_api_url}/sdapi/v1/txt2img",
            json={
                "prompt": enhanced,
                "negative_prompt": "text, watermark, low quality, blurry",
                "steps": 25,
                "width": 512,
                "height": 512,
                "cfg_scale": 7.5,
                "sampler_name": "DPM++ 2M Karras",
            },
        )
        resp.raise_for_status()
        b64 = resp.json()["images"][0]
        img_data = base64.b64decode(b64)
        img = Image.open(io.BytesIO(img_data)).convert("RGBA")
        img.save(output_path, "PNG")
        logger.info("SD image saved: %s", output_path)
        return output_path

    def _generate_pillow(self, symbol: str, output_path: Path) -> Path:
        """Procedural fallback: generates a bold gradient logo with symbol text."""
        size = 512
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Background gradient
        palette = random.choice(MEME_PALETTES)
        bg_color = palette[0]
        text_color = palette[1]

        # Draw circle background
        margin = 20
        draw.ellipse(
            [margin, margin, size - margin, size - margin],
            fill=bg_color,
            outline=(255, 255, 255, 200),
            width=8,
        )

        # Draw symbol text
        text = symbol[:6].upper()
        font_size = 120 if len(text) <= 4 else 80
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = (size - text_w) // 2
        y = (size - text_h) // 2

        # Shadow
        draw.text((x + 4, y + 4), text, fill=(0, 0, 0, 128), font=font)
        draw.text((x, y), text, fill=text_color, font=font)

        img.save(output_path, "PNG")
        logger.info("Pillow fallback image saved: %s", output_path)
        return output_path

    async def close(self) -> None:
        await self._http.aclose()
