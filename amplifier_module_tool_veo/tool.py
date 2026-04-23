"""Veo video generation tool implementation."""

from __future__ import annotations

import asyncio
import mimetypes
import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from amplifier_core import ModuleCoordinator, ToolResult

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Model aliases & defaults
# ---------------------------------------------------------------------------

_DEFAULT_MODEL = "veo-3.1-generate-preview"

_MODEL_ALIASES: dict[str, str] = {
    # Veo 3.1
    "veo-3.1": "veo-3.1-generate-preview",
    "veo31": "veo-3.1-generate-preview",
    "3.1": "veo-3.1-generate-preview",
    # Veo 3.1 Fast
    "veo-3.1-fast": "veo-3.1-fast-generate-preview",
    "veo31-fast": "veo-3.1-fast-generate-preview",
    "fast": "veo-3.1-fast-generate-preview",
    # Veo 3.1 Lite
    "veo-3.1-lite": "veo-3.1-lite-generate-preview",
    "veo31-lite": "veo-3.1-lite-generate-preview",
    "lite": "veo-3.1-lite-generate-preview",
    # Veo 3
    "veo-3": "veo-3.0-generate-001",
    "veo3": "veo-3.0-generate-001",
    "3.0": "veo-3.0-generate-001",
    # Veo 3 Fast
    "veo-3-fast": "veo-3.0-fast-generate-001",
    "veo3-fast": "veo-3.0-fast-generate-001",
    # Veo 2
    "veo-2": "veo-2.0-generate-001",
    "veo2": "veo-2.0-generate-001",
    "2.0": "veo-2.0-generate-001",
}


def _resolve_model(value: str | None) -> str | None:
    """Resolve a model alias or pass-through a fully-qualified model ID."""
    if not value:
        return None
    stripped = value.strip()
    return _MODEL_ALIASES.get(stripped.lower(), stripped)


# ---------------------------------------------------------------------------
# Tool class
# ---------------------------------------------------------------------------


class VeoTool:
    """Amplifier tool that wraps the Google Veo video generation API."""

    def __init__(self, config: dict[str, Any], coordinator: ModuleCoordinator) -> None:
        self.coordinator = coordinator
        self.working_dir: str | None = config.get("working_dir")
        self.model: str = (
            _resolve_model(config.get("model"))
            or _resolve_model(os.getenv("VEO_MODEL"))
            or _DEFAULT_MODEL
        )
        self.poll_interval: int = int(config.get("poll_interval_seconds", 10))
        # Vertex AI config (required for interpolation / last_frame)
        self.vertexai: bool = bool(config.get("vertexai", False))
        self.project: str | None = config.get("project") or os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location: str = (
            config.get("location") or os.getenv("GOOGLE_CLOUD_LOCATION") or "us-central1"
        )

    # ------------------------------------------------------------------
    # Tool protocol
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "veo"

    @property
    def description(self) -> str:
        return (
            "Generate videos using Google Veo 3.1 via the Gemini API. "
            "Supports four operations:\n"
            "  • 'generate'         – Text-to-video: describe a scene and generate an MP4.\n"
            "  • 'image_to_video'   – Animate a source image (first frame). Optionally provide a "
            "last frame to create an interpolation video between two images.\n"
            "  • 'reference_images' – Guide generation with up to 3 reference images that preserve "
            "the appearance of subjects, characters, or products (Veo 3.1 only).\n"
            "  • 'extend'           – Continue a previously generated Veo video by 7 seconds "
            "(Veo 3.1 / 3.1 Fast only; pass the video_uri from a prior generation).\n"
            "All Veo 3.x videos include natively generated audio. Veo 2 videos are silent.\n"
            "Videos are watermarked with SynthID and stored server-side for 48 hours."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                # --- Core ---
                "operation": {
                    "type": "string",
                    "enum": ["generate", "image_to_video", "reference_images", "extend"],
                    "description": (
                        "Which generation mode to use:\n"
                        "  'generate'         – pure text-to-video\n"
                        "  'image_to_video'   – animate an image; add last_frame_path for interpolation\n"
                        "  'reference_images' – content-guided generation (Veo 3.1 only)\n"
                        "  'extend'           – continue an existing Veo video (Veo 3.1/3.1 Fast only)"
                    ),
                },
                "prompt": {
                    "type": "string",
                    "description": (
                        "Text description of the video. Include subject, action, style, "
                        "camera motion, and audio cues. Use quotes for dialogue: "
                        "\"Hello,\" she said. Required for all operations except 'extend' "
                        "(where it guides the continuation)."
                    ),
                },
                "output_path": {
                    "type": "string",
                    "description": (
                        "Local file path to save the generated video (e.g. 'my_video.mp4'). "
                        "Defaults to a timestamped filename in the working directory. "
                        "When number_of_videos > 1, additional videos are saved with _1, _2 suffixes."
                    ),
                },
                "model": {
                    "type": "string",
                    "description": (
                        "Veo model to use. Full model IDs:\n"
                        "  'veo-3.1-generate-preview'      – Veo 3.1 (default, audio, 4k, interpolation, reference images, extension)\n"
                        "  'veo-3.1-fast-generate-preview' – Veo 3.1 Fast (audio, optimised for speed)\n"
                        "  'veo-3.1-lite-generate-preview' – Veo 3.1 Lite (audio, no 4k, no extension, no reference images)\n"
                        "  'veo-3.0-generate-001'          – Veo 3 (stable, audio)\n"
                        "  'veo-3.0-fast-generate-001'     – Veo 3 Fast (stable, audio)\n"
                        "  'veo-2.0-generate-001'          – Veo 2 (stable, silent, up to 2 videos)\n"
                        "Short aliases: 'veo-3.1', 'fast', 'lite', 'veo-3', 'veo-3-fast', 'veo-2'."
                    ),
                },
                # --- Image inputs ---
                "image_path": {
                    "type": "string",
                    "description": (
                        "Path to the starting/source image for 'image_to_video'. "
                        "Used as the first frame of the generated video. "
                        "Supports JPEG, PNG, WebP, GIF."
                    ),
                },
                "last_frame_path": {
                    "type": "string",
                    "description": (
                        "Path to the ending frame image for interpolation. "
                        "Used alongside image_path in 'image_to_video' to specify both "
                        "the start and end frames; Veo generates the in-between motion. "
                        "Duration is automatically set to 8 seconds when this is provided "
                        "(the minimum required for interpolation)."
                    ),
                },
                # --- Reference images ---
                "reference_image_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 3,
                    "description": (
                        "Paths to 1–3 reference images for the 'reference_images' operation. "
                        "Used to preserve the appearance of a person, character, or product "
                        "in the generated video. Veo 3.1 only."
                    ),
                },
                "reference_type": {
                    "type": "string",
                    "enum": ["asset"],
                    "description": (
                        "Reference type applied to all reference images. "
                        "Currently only 'asset' is supported (preserves subject appearance)."
                    ),
                },
                # --- Video extension ---
                "video_uri": {
                    "type": "string",
                    "description": (
                        "Gemini Files API URI of a Veo-generated video to extend "
                        "(e.g. 'files/abc123def456'). Returned as 'video_uri' in the output "
                        "of a prior generate/image_to_video call. Required for 'extend'."
                    ),
                },
                # --- Generation config ---
                "aspect_ratio": {
                    "type": "string",
                    "enum": ["16:9", "9:16"],
                    "description": (
                        "Output aspect ratio. '16:9' = landscape (default). '9:16' = portrait."
                    ),
                },
                "duration_seconds": {
                    "type": "string",
                    "enum": ["4", "6", "8"],
                    "description": (
                        "Video duration in seconds. Veo 3.x supports '4', '6', '8'. "
                        "Must be '8' when using reference images, extension, 1080p, or 4k resolution. "
                        "Veo 2 supports '5', '6', '8'."
                    ),
                },
                "resolution": {
                    "type": "string",
                    "enum": ["720p", "1080p", "4k"],
                    "description": (
                        "Output resolution. '720p' is the default and works with all operations. "
                        "'1080p' requires duration_seconds='8'. "
                        "'4k' requires Veo 3.1 (not Lite) and duration_seconds='8'. "
                        "Extension ('extend') only supports '720p'."
                    ),
                },
                "person_generation": {
                    "type": "string",
                    "enum": ["allow_all", "allow_adult", "dont_allow"],
                    "description": (
                        "Controls whether people appear in generated videos. "
                        "Veo 3.x text-to-video & extension: only 'allow_all' is accepted. "
                        "Veo 3.x image-to-video, interpolation, reference images: only 'allow_adult'. "
                        "Veo 2 text-to-video: 'allow_all', 'allow_adult', or 'dont_allow'. "
                        "EU/UK/CH/MENA regions are restricted — see API docs. "
                        "Defaults are set automatically per operation."
                    ),
                },
                "number_of_videos": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 2,
                    "description": (
                        "Number of videos to generate per request. "
                        "Veo 3.x always produces 1. Veo 2 supports 1 or 2."
                    ),
                },
                "seed": {
                    "type": "integer",
                    "description": (
                        "Optional integer seed for slight reproducibility improvement "
                        "(Veo 3.x models only). Does not guarantee identical outputs."
                    ),
                },
                "poll_interval_seconds": {
                    "type": "integer",
                    "minimum": 5,
                    "maximum": 60,
                    "description": (
                        "How often (in seconds) to check whether generation has completed "
                        "(default: 10). Generation typically takes 11 seconds to 6 minutes."
                    ),
                },
            },
            "required": ["operation"],
        }

    # ------------------------------------------------------------------
    # Execute dispatch
    # ------------------------------------------------------------------

    async def execute(self, input_data: dict[str, Any]) -> ToolResult:
        operation: str = input_data.get("operation", "")
        if not operation:
            return ToolResult(
                success=False,
                output="'operation' is required.",
                error={"message": "Missing required field: operation"},
            )

        model = _resolve_model(input_data.get("model")) or self.model
        poll_interval = int(input_data.get("poll_interval_seconds", self.poll_interval))
        output_path = self._resolve_output_path(input_data.get("output_path"), operation)

        try:
            from google import genai
            from google.genai import types as genai_types

            client = self._build_client(genai)

            if operation == "generate":
                return await self._generate(
                    client, genai_types, input_data, model, output_path, poll_interval
                )
            elif operation == "image_to_video":
                return await self._image_to_video(
                    client, genai_types, input_data, model, output_path, poll_interval
                )
            elif operation == "reference_images":
                return await self._reference_images(
                    client, genai_types, input_data, model, output_path, poll_interval
                )
            elif operation == "extend":
                return await self._extend_video(
                    client, genai_types, input_data, model, output_path, poll_interval
                )
            else:
                valid = ["generate", "image_to_video", "reference_images", "extend"]
                return ToolResult(
                    success=False,
                    output=f"Unknown operation {operation!r}. Must be one of: {', '.join(valid)}.",
                    error={"message": f"Unknown operation: {operation}"},
                )

        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                output=f"Video generation failed: {exc}",
                error={"message": str(exc), "type": type(exc).__name__},
            )

    # ------------------------------------------------------------------
    # Client construction
    # ------------------------------------------------------------------

    def _build_client(self, genai: Any) -> Any:
        """Build a Gemini API client (Developer API or Vertex AI)."""
        use_vertexai = self.vertexai or bool(self.project)

        if use_vertexai:
            if not self.project:
                raise ValueError(
                    "Vertex AI mode requires a Google Cloud project. "
                    "Set the GOOGLE_CLOUD_PROJECT environment variable or "
                    "configure 'project' in the tool config."
                )
            return genai.Client(
                vertexai=True,
                project=self.project,
                location=self.location,
            )

        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError(
                "GOOGLE_API_KEY environment variable is not set. "
                "Set GOOGLE_API_KEY for the Gemini Developer API, or set "
                "GOOGLE_CLOUD_PROJECT (+ Application Default Credentials) for Vertex AI."
            )
        return genai.Client(api_key=api_key)

    # ------------------------------------------------------------------
    # Operation implementations
    # ------------------------------------------------------------------

    async def _generate(
        self,
        client: Any,
        types: Any,
        input_data: dict[str, Any],
        model: str,
        output_path: Path,
        poll_interval: int,
    ) -> ToolResult:
        """Text-to-video generation."""
        prompt = input_data.get("prompt")
        if not prompt:
            return ToolResult(
                success=False,
                output="'prompt' is required for the 'generate' operation.",
                error={"message": "Missing required field: prompt"},
            )

        config = self._build_config(types, input_data, operation="generate")

        await self.coordinator.hooks.emit(
            "tool.veo.generate",
            {"model": model, "operation": "generate", "prompt_length": len(prompt)},
        )

        op = await asyncio.to_thread(
            client.models.generate_videos,
            model=model,
            prompt=prompt,
            config=config,
        )

        return await self._poll_and_download(client, op, output_path, poll_interval)

    async def _image_to_video(
        self,
        client: Any,
        types: Any,
        input_data: dict[str, Any],
        model: str,
        output_path: Path,
        poll_interval: int,
    ) -> ToolResult:
        """Image-to-video (first frame animation, with optional interpolation via last_frame)."""
        prompt = input_data.get("prompt")
        if not prompt:
            return ToolResult(
                success=False,
                output="'prompt' is required for the 'image_to_video' operation.",
                error={"message": "Missing required field: prompt"},
            )

        image_path_str = input_data.get("image_path")
        if not image_path_str:
            return ToolResult(
                success=False,
                output="'image_path' is required for the 'image_to_video' operation.",
                error={"message": "Missing required field: image_path"},
            )

        try:
            image = self._load_image(types, image_path_str)
        except FileNotFoundError:
            return ToolResult(
                success=False,
                output=f"Image file not found: {image_path_str}",
                error={"message": f"File not found: {image_path_str}"},
            )

        # Optional last frame for interpolation
        extra: dict[str, Any] = {}
        last_frame_path_str = input_data.get("last_frame_path")
        if last_frame_path_str:
            try:
                extra["last_frame"] = self._load_image(types, last_frame_path_str)
            except FileNotFoundError:
                return ToolResult(
                    success=False,
                    output=f"Last frame image not found: {last_frame_path_str}",
                    error={"message": f"File not found: {last_frame_path_str}"},
                )
            # Interpolation requires duration=8; auto-upgrade if caller didn't specify or went lower.
            if not input_data.get("duration_seconds") or int(input_data["duration_seconds"]) < 8:
                input_data = {**input_data, "duration_seconds": 8}

        config = self._build_config(types, input_data, operation="image_to_video", extra=extra)

        await self.coordinator.hooks.emit(
            "tool.veo.image_to_video",
            {
                "model": model,
                "operation": "image_to_video",
                "image_path": image_path_str,
                "has_last_frame": bool(last_frame_path_str),
            },
        )

        op = await asyncio.to_thread(
            client.models.generate_videos,
            model=model,
            prompt=prompt,
            image=image,
            config=config,
        )

        return await self._poll_and_download(client, op, output_path, poll_interval)

    async def _reference_images(
        self,
        client: Any,
        types: Any,
        input_data: dict[str, Any],
        model: str,
        output_path: Path,
        poll_interval: int,
    ) -> ToolResult:
        """Reference-image-guided generation (Veo 3.1 only)."""
        prompt = input_data.get("prompt")
        if not prompt:
            return ToolResult(
                success=False,
                output="'prompt' is required for the 'reference_images' operation.",
                error={"message": "Missing required field: prompt"},
            )

        ref_paths: list[str] = input_data.get("reference_image_paths", [])
        if not ref_paths:
            return ToolResult(
                success=False,
                output=(
                    "'reference_image_paths' is required for the 'reference_images' operation. "
                    "Provide a list of 1–3 image file paths."
                ),
                error={"message": "Missing required field: reference_image_paths"},
            )

        if len(ref_paths) > 3:
            return ToolResult(
                success=False,
                output=f"Too many reference images ({len(ref_paths)}). Maximum is 3.",
                error={"message": "Exceeded maximum of 3 reference images"},
            )

        ref_type = input_data.get("reference_type", "asset")

        try:
            reference_images = [
                types.VideoGenerationReferenceImage(
                    image=self._load_image(types, p),
                    reference_type=ref_type,
                )
                for p in ref_paths
            ]
        except FileNotFoundError as exc:
            return ToolResult(
                success=False,
                output=f"Reference image file not found: {exc}",
                error={"message": str(exc)},
            )

        config = self._build_config(
            types,
            input_data,
            operation="reference_images",
            extra={"reference_images": reference_images},
        )

        await self.coordinator.hooks.emit(
            "tool.veo.reference_images",
            {
                "model": model,
                "operation": "reference_images",
                "num_references": len(ref_paths),
            },
        )

        op = await asyncio.to_thread(
            client.models.generate_videos,
            model=model,
            prompt=prompt,
            config=config,
        )

        return await self._poll_and_download(client, op, output_path, poll_interval)

    async def _extend_video(
        self,
        client: Any,
        types: Any,
        input_data: dict[str, Any],
        model: str,
        output_path: Path,
        poll_interval: int,
    ) -> ToolResult:
        """Extend a previously generated Veo video (Veo 3.1 / 3.1 Fast only)."""
        video_uri = input_data.get("video_uri")
        if not video_uri:
            return ToolResult(
                success=False,
                output=(
                    "'video_uri' is required for the 'extend' operation. "
                    "Provide the Gemini Files API URI returned by a prior generation "
                    "(e.g. 'files/abc123def456')."
                ),
                error={"message": "Missing required field: video_uri"},
            )

        prompt: str = input_data.get("prompt") or ""

        # Reconstruct the Video object from the Files API URI
        video = types.Video(uri=video_uri)

        config = self._build_config(types, input_data, operation="extend")

        await self.coordinator.hooks.emit(
            "tool.veo.extend",
            {"model": model, "operation": "extend", "video_uri": video_uri},
        )

        op = await asyncio.to_thread(
            client.models.generate_videos,
            model=model,
            prompt=prompt,
            video=video,
            config=config,
        )

        return await self._poll_and_download(client, op, output_path, poll_interval)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_config(
        self,
        types: Any,
        input_data: dict[str, Any],
        operation: str = "generate",
        extra: dict[str, Any] | None = None,
    ) -> Any | None:
        """Build a GenerateVideosConfig from input_data plus any extra kwargs.

        Automatically applies the correct person_generation default per operation:
        - image_to_video / reference_images: 'allow_adult' (Veo 3.x requirement)
        - generate / extend: 'allow_all' (Veo 3.x default for text-to-video)
        """
        kwargs: dict[str, Any] = {}

        if aspect_ratio := input_data.get("aspect_ratio"):
            kwargs["aspect_ratio"] = aspect_ratio
        if duration := input_data.get("duration_seconds"):
            kwargs["duration_seconds"] = int(duration)  # API expects integer, not string
        if resolution := input_data.get("resolution"):
            kwargs["resolution"] = resolution
        if num_videos := input_data.get("number_of_videos"):
            kwargs["number_of_videos"] = int(num_videos)
        if seed := input_data.get("seed"):
            kwargs["seed"] = int(seed)

        # person_generation: use explicit value if provided; otherwise apply sensible default.
        # Veo 3.x image-based operations REQUIRE allow_adult (not allow_all).
        # Without the correct value, the API returns "Your use case is currently not supported."
        person_gen = input_data.get("person_generation")
        if person_gen:
            kwargs["person_generation"] = person_gen
        elif operation in ("image_to_video", "reference_images"):
            # Default for image-based Veo 3.x operations
            kwargs["person_generation"] = "allow_adult"
        # For 'generate' and 'extend', omit person_generation to let the API use its default.

        if extra:
            kwargs.update(extra)

        return types.GenerateVideosConfig(**kwargs) if kwargs else None

    async def _poll_and_download(
        self,
        client: Any,
        op: Any,
        output_path: Path,
        poll_interval: int,
    ) -> ToolResult:
        """Poll for completion, then download and save all generated videos."""
        while not op.done:
            await asyncio.sleep(poll_interval)
            op = await asyncio.to_thread(client.operations.get, op)

        if not op.response or not op.response.generated_videos:
            return ToolResult(
                success=False,
                output=(
                    "Generation completed but no videos were produced. "
                    "The request may have been blocked by safety filters or the audio "
                    "processing pipeline. You will not be charged for blocked generations."
                ),
                error={"message": "No generated_videos in response"},
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)

        saved_paths: list[str] = []
        video_uris: list[str] = []

        for i, gv in enumerate(op.response.generated_videos):
            if i == 0:
                save_path = output_path
            else:
                save_path = output_path.parent / f"{output_path.stem}_{i}{output_path.suffix}"

            # Fetch bytes from the Files API
            await asyncio.to_thread(client.files.download, file=gv.video)
            # Write to disk via the SDK helper
            await asyncio.to_thread(gv.video.save, str(save_path))

            saved_paths.append(str(save_path))
            if hasattr(gv.video, "uri") and gv.video.uri:
                video_uris.append(gv.video.uri)

        primary_uri = video_uris[0] if video_uris else None

        return ToolResult(
            success=True,
            output={
                "saved_to": saved_paths[0] if len(saved_paths) == 1 else saved_paths,
                "videos_generated": len(saved_paths),
                "video_uri": primary_uri,
                "all_video_uris": video_uris,
                "operation_name": getattr(op, "name", None),
                "note": (
                    "video_uri can be passed to 'extend' operation within 48 hours. "
                    "Videos are watermarked with SynthID."
                ),
            },
        )

    def _load_image(self, types: Any, path_str: str) -> Any:
        """Load an image from a file path and return a types.Image object."""
        path = self._resolve_path(path_str)
        if not path.exists():
            raise FileNotFoundError(path_str)

        mime_type, _ = mimetypes.guess_type(str(path))
        if not mime_type or not mime_type.startswith("image/"):
            # Default to JPEG for unknown extensions
            mime_type = "image/jpeg"

        image_bytes = path.read_bytes()
        return types.Image(image_bytes=image_bytes, mime_type=mime_type)

    def _resolve_path(self, path_str: str) -> Path:
        """Resolve a path, honouring the session working directory."""
        path = Path(path_str).expanduser()
        if not path.is_absolute() and self.working_dir:
            path = Path(self.working_dir) / path
        return path

    def _resolve_output_path(self, path_str: str | None, operation: str) -> Path:
        """Resolve the output path, generating a timestamped default if not provided."""
        if path_str:
            return self._resolve_path(path_str)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"veo_{operation}_{timestamp}.mp4"

        if self.working_dir:
            return Path(self.working_dir) / filename
        return Path(filename)
