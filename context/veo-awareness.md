# Veo Tool Awareness

A `veo` tool is available for video generation via Google Veo 3.1.

## When to use the veo tool directly

- Simple, one-shot video generation with a clear prompt
- Quick parameter lookups (model names, supported resolutions, etc.)

## When to delegate to veo-expert agent

- The user needs help writing an effective prompt
- Multi-step workflows (generate → extend; image pipeline with Nano Banana)
- Choosing between generation modes or models
- Troubleshooting blocked generations

## Tool quick reference

```
operation: generate | image_to_video | reference_images | extend
model:     veo-3.1-generate-preview (default)
           veo-3.1-fast-generate-preview
           veo-3.1-lite-generate-preview
           veo-3.0-generate-001
           veo-2.0-generate-001
```

Key parameters: `aspect_ratio`, `duration_seconds`, `resolution`, `person_generation`, `seed`
Image inputs: `image_path`, `last_frame_path`, `reference_image_paths`
Extension:    `video_uri` (from a prior generation's output)
