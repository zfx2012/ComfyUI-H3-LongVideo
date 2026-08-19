# ComfyUI-H3-LongVideo

ComfyUI custom nodes for planning, naming, and assembling MiniMax H3 long-video segments. The package also includes a simple **比例预设** node for selecting image aspect ratios and 1K/2K/4K resolution tiers.

## Installation

Clone this repository into ComfyUI's `custom_nodes` directory, then restart ComfyUI:

```powershell
cd <ComfyUI>\custom_nodes
git clone https://github.com/zfx2012/ComfyUI-H3-LongVideo.git
```

The long-video assembly node requires `imageio-ffmpeg` or ComfyUI-VideoHelperSuite so that FFmpeg is available.

## Nodes

### 比例预设

Category: `Utilities/Resolution`

Select an aspect ratio and a resolution tier. It outputs integer `width` and `height` values that can connect directly to nodes such as `EmptyLatentImage`.

The resolution tier is based on the **longest edge**, not total pixel count:

- `1K 1024 x 1024`: longest edge is 1024 pixels
- `2K 2048 x 2048`: longest edge is 2048 pixels
- `4K 4096 x 4096`: longest edge is 4096 pixels

| Ratio | 1K output | 2K output | 4K output |
| --- | --- | --- | --- |
| 1:1 | 1024 x 1024 | 2048 x 2048 | 4096 x 4096 |
| 2:3 | 683 x 1024 | 1366 x 2048 | 2732 x 4096 |
| 3:2 | 1024 x 683 | 2048 x 1366 | 4096 x 2732 |
| 3:4 | 768 x 1024 | 1536 x 2048 | 3072 x 4096 |
| 4:3 | 1024 x 768 | 2048 x 1536 | 4096 x 3072 |
| 4:5 | 819 x 1024 | 1638 x 2048 | 3276 x 4096 |
| 5:4 | 1024 x 819 | 2048 x 1638 | 4096 x 3276 |
| 9:16 | 576 x 1024 | 1152 x 2048 | 2304 x 4096 |
| 16:9 | 1024 x 576 | 2048 x 1152 | 4096 x 2304 |

### H3 Long Video Plan

Creates a long-video plan from one prompt per segment. Prompts can be supplied as a JSON string array or separated by a line containing `---SEGMENT---` or `===SEGMENT===`.

`segment_count` must equal the number of supplied prompt blocks. The node outputs a plan, the segment count, and a summary string.

### H3 Long Video Step

Selects a single prompt from an H3 long-video plan by zero-based index. It also returns a consistent output filename prefix:

```text
h3_long/<job_name>/segment_001
```

### H3 Long Video Assemble

After all segments have been encoded, finds segment files under:

```text
output/h3_long/<job_name>/
```

It assembles them with video and audio crossfades, writes the final MP4 to the same directory, and saves a JSON manifest beside it.

## Validation

Run the included self-check with the same Python interpreter used by ComfyUI:

```powershell
<ComfyUI Python> test_nodes.py
```

For the portable Windows build, for example:

```powershell
& 'F:\ComfyUI_windows_portable\python_embeded\python.exe' test_nodes.py
```
