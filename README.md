# amplifier-module-tool-veo

Generate videos with [Google Veo 3.1](https://ai.google.dev/gemini-api/docs/video) inside your Amplifier sessions.
Text-to-video, image-to-video, interpolation, reference-image guidance, and video extension — all from a single tool.

---

## Prerequisites

### 1. Google API key

Get one at [aistudio.google.com/apikey](https://aistudio.google.com/apikey), then export it in your shell:

```bash
export GOOGLE_API_KEY="your-key-here"
```

To make it permanent, add the line above to your `~/.zshrc` (or `~/.bashrc`).

> Veo 3.1 requires a paid Gemini API plan. Check [pricing](https://ai.google.dev/gemini-api/docs/pricing) before running long jobs.

---

## Installation

```bash
amplifier bundle add git+https://github.com/kenotron-ms/amplifier-module-tool-veo@main --app
```

---

## What you can say in a session

Once the bundle is loaded the `veo` tool and `veo-expert` agent are available. Just describe what you want:

```
Generate an 8-second cinematic video of a misty mountain range at sunrise, landscape, 1080p.
```

```
Animate this product photo into a 6-second video: product_shot.png
```

```
Take start.png and end.png and interpolate a smooth video between them.
```

```
Use these three images as references and generate a video of the character walking on a beach:
reference_image_paths: [face.png, outfit.png, shoes.png]
```

```
Extend the video I just generated — have the camera slowly pan right.
```

---

## Operations

| Operation | When to use | Required inputs |
|---|---|---|
| `generate` | Pure text-to-video | `prompt` |
| `image_to_video` | Animate an image (first frame) | `prompt`, `image_path` |
| `image_to_video` + `last_frame_path` | Interpolate between two images | `prompt`, `image_path`, `last_frame_path` |
| `reference_images` | Preserve a subject's appearance (Veo 3.1 only) | `prompt`, `reference_image_paths` (1–3) |
| `extend` | Continue a prior Veo video by 7 s (Veo 3.1/Fast only) | `video_uri` from a prior generation |

---

## Parameters

| Parameter | Values | Default | Notes |
|---|---|---|---|
| `model` | see Models table below | `veo-3.1` | |
| `aspect_ratio` | `16:9`, `9:16` | `16:9` | |
| `duration_seconds` | `"4"`, `"6"`, `"8"` | API default | Must be `"8"` with 1080p, 4k, reference images, or extension |
| `resolution` | `720p`, `1080p`, `4k` | `720p` | `4k` requires Veo 3.1 (not Lite) and `duration_seconds: "8"` |
| `person_generation` | `allow_all`, `allow_adult`, `dont_allow` | — | Restricted in EU/UK/CH/MENA — see [docs](https://ai.google.dev/gemini-api/docs/video#limitations) |
| `number_of_videos` | `1`, `2` | `1` | Veo 3.x is always 1; Veo 2 supports up to 2 |
| `seed` | any integer | — | Veo 3.x only; improves (not guarantees) reproducibility |
| `output_path` | file path | timestamped `.mp4` | Relative paths resolve from the session working directory |
| `poll_interval_seconds` | `5`–`60` | `10` | How often to check status; generation takes 11 s – 6 min |

---

## Models

| Alias | Full model ID | Audio | Max res | Extension | Reference images |
|---|---|---|---|---|---|
| `veo-3.1` **(default)** | `veo-3.1-generate-preview` | yes | 4k | yes | yes |
| `fast` | `veo-3.1-fast-generate-preview` | yes | 1080p | yes | yes |
| `lite` | `veo-3.1-lite-generate-preview` | yes | 1080p | no | no |
| `veo-3` | `veo-3.0-generate-001` | yes | 1080p | no | no |
| `veo-3-fast` | `veo-3.0-fast-generate-001` | yes | 1080p | no | no |
| `veo-2` | `veo-2.0-generate-001` | no | 720p | no | no |

---

## Things to know

- **Videos are stored for 48 hours.** Save the file locally — the `veo` tool downloads it automatically to `output_path`.
- **The `video_uri` in the output** (e.g. `files/abc123`) is what you pass to `extend` within those 48 hours.
- **All Veo videos are watermarked** with [SynthID](https://deepmind.google/technologies/synthid/).
- **Safety filters** may block a generation. You are not charged for blocked videos.
- **Audio cues** work best with explicit descriptions — put dialogue in quotes, name sound effects directly.

---

## License

MIT
