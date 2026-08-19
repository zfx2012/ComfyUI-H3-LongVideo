import json
import re
import subprocess
from pathlib import Path

import folder_paths


SEGMENT_DELIMITER = re.compile(r"^\s*(?:---\s*SEGMENT\s*---|===\s*SEGMENT\s*===)\s*$", re.IGNORECASE | re.MULTILINE)


def parse_prompt_blocks(value):
    text = value.strip()
    if not text:
        raise ValueError("Prompt schedule is empty")

    if text.startswith("["):
        try:
            prompts = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Prompt schedule is not valid JSON: {exc}") from exc
        if not isinstance(prompts, list) or not all(isinstance(item, str) for item in prompts):
            raise ValueError("Prompt JSON must be an array of strings")
    else:
        prompts = SEGMENT_DELIMITER.split(text)

    prompts = [item.strip() for item in prompts if item.strip()]
    if not prompts:
        raise ValueError("Prompt schedule contains no usable prompts")
    return prompts


def safe_job_name(value):
    name = re.sub(r"[^\w.-]+", "_", value.strip(), flags=re.UNICODE).strip(" ._")
    if not name:
        raise ValueError("Job name must contain at least one letter or number")
    return name


def find_ffmpeg():
    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        executable = get_ffmpeg_exe()
    except Exception as exc:
        raise RuntimeError("FFmpeg is unavailable; install imageio-ffmpeg or VideoHelperSuite") from exc
    if not executable or not Path(executable).is_file():
        raise RuntimeError("FFmpeg executable was not found")
    return executable


def build_crossfade_filter(frame_counts, frame_rate, transition_frames):
    transition = transition_frames / frame_rate
    filters = []
    for index in range(len(frame_counts)):
        filters.append(f"[{index}:a]aresample=32000,asetpts=PTS-STARTPTS[a{index}]")

    video_label = "0:v"
    audio_label = "a0"
    timeline = frame_counts[0] / frame_rate
    for index in range(1, len(frame_counts)):
        offset = timeline - transition
        next_video = f"vx{index}"
        next_audio = f"ax{index}"
        filters.append(
            f"[{video_label}][{index}:v]xfade=transition=fade:duration={transition:.6f}:offset={offset:.6f}[{next_video}]"
        )
        filters.append(
            f"[{audio_label}][a{index}]acrossfade=d={transition:.6f}:c1=tri:c2=tri[{next_audio}]"
        )
        video_label = next_video
        audio_label = next_audio
        timeline += frame_counts[index] / frame_rate - transition
    return ";".join(filters), video_label, audio_label, timeline


class H3LongVideoPlan:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt_blocks": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "First segment prompt\n---SEGMENT---\nSecond segment prompt",
                    },
                ),
                "job_name": ("STRING", {"default": "h3_long_video"}),
                "segment_seconds": ("FLOAT", {"default": 5.0, "min": 1.0, "max": 30.0, "step": 0.1}),
                "segment_count": ("INT", {"default": 3, "min": 1, "max": 720, "step": 1}),
            }
        }

    RETURN_TYPES = ("H3_LONG_VIDEO_PLAN", "INT", "STRING")
    RETURN_NAMES = ("plan", "segment_count", "summary")
    FUNCTION = "build"
    CATEGORY = "MiniMax H3/Long Video"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def build(self, prompt_blocks, job_name, segment_seconds, segment_count):
        prompts = parse_prompt_blocks(prompt_blocks)
        segment_seconds = float(segment_seconds)
        segment_count = int(segment_count)
        if segment_seconds <= 0:
            raise ValueError("Segment duration must be greater than zero")
        if segment_count < 1:
            raise ValueError("Segment count must be at least 1")
        if len(prompts) != segment_count:
            raise ValueError(
                f"Need {segment_count} prompts, but found {len(prompts)}"
            )
        target_seconds = segment_seconds * segment_count
        job = safe_job_name(job_name)
        plan = {
            "job_name": job,
            "target_seconds": target_seconds,
            "segment_seconds": segment_seconds,
            "segment_count": segment_count,
            "prompts": prompts,
        }
        summary = f"{job}: {segment_count} segments, {target_seconds:g}s target"
        return plan, segment_count, summary


class OneKAspectRatio:
    PRESETS = {
        "1:1": (1024, 1024),
        "2:3": (683, 1024),
        "3:2": (1024, 683),
        "3:4": (768, 1024),
        "4:3": (1024, 768),
        "4:5": (819, 1024),
        "5:4": (1024, 819),
        "9:16": (576, 1024),
        "16:9": (1024, 576),
    }

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "ratio": (list(cls.PRESETS), {"default": "9:16"}),
                "resolution_tier": (
                    ["1K 1024 x 1024", "2K 2048 x 2048", "4K 4096 x 4096"],
                    {"default": "1K 1024 x 1024"},
                ),
            }
        }

    RETURN_TYPES = ("INT", "INT")
    RETURN_NAMES = ("width", "height")
    FUNCTION = "select"
    CATEGORY = "Utilities/Resolution"

    def select(self, ratio, resolution_tier):
        multiplier = {
            "1K 1024 x 1024": 1,
            "2K 2048 x 2048": 2,
            "4K 4096 x 4096": 4,
        }[resolution_tier]
        width, height = self.PRESETS[ratio]
        return width * multiplier, height * multiplier


class H3LongVideoStep:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "plan": ("H3_LONG_VIDEO_PLAN",),
                "index": ("INT", {"default": 0, "min": 0, "max": 9999}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "INT")
    RETURN_NAMES = ("prompt", "filename_prefix", "segment_number")
    FUNCTION = "select"
    CATEGORY = "MiniMax H3/Long Video"

    def select(self, plan, index):
        count = plan["segment_count"]
        if index < 0 or index >= count:
            raise ValueError(f"Segment index {index} is outside 0..{count - 1}")

        number = index + 1
        prefix = f"h3_long/{plan['job_name']}/segment_{number:03d}"
        return plan["prompts"][index], prefix, number


class H3LongVideoAssemble:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "plan": ("H3_LONG_VIDEO_PLAN",),
                "final_tail_frame": ("IMAGE",),
                "transition_frames": ("INT", {"default": 3, "min": 1, "max": 12, "step": 1}),
            }
        }

    RETURN_TYPES = ("VHS_FILENAMES",)
    RETURN_NAMES = ("final_video",)
    FUNCTION = "assemble"
    OUTPUT_NODE = True
    CATEGORY = "MiniMax H3/Long Video"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def assemble(self, plan, final_tail_frame, transition_frames):
        del final_tail_frame  # Execution dependency: assembly starts only after the loop finishes.
        output_root = Path(folder_paths.get_output_directory()).resolve()
        job_dir = output_root / "h3_long" / plan["job_name"]
        segments = []

        for number in range(1, plan["segment_count"] + 1):
            candidates = list(job_dir.glob(f"segment_{number:03d}_*-audio.mp4"))
            if not candidates:
                candidates = [
                    path
                    for path in job_dir.glob(f"segment_{number:03d}_*.mp4")
                    if not path.name.endswith("-audio.mp4")
                ]
            if not candidates:
                raise ValueError(f"Missing encoded segment {number:03d} in {job_dir}")
            segments.append(max(candidates, key=lambda path: path.stat().st_mtime_ns))

        job_dir.mkdir(parents=True, exist_ok=True)
        existing = list(job_dir.glob(f"{plan['job_name']}_final_*.mp4"))
        counters = []
        for path in existing:
            match = re.search(r"_final_(\d+)\.mp4$", path.name)
            if match:
                counters.append(int(match.group(1)))
        counter = max(counters, default=0) + 1
        final_path = job_dir / f"{plan['job_name']}_final_{counter:05d}.mp4"

        from imageio_ffmpeg import count_frames_and_secs

        frame_rate = 24
        frame_counts = [count_frames_and_secs(str(segment))[0] for segment in segments]
        if any(count <= transition_frames for count in frame_counts):
            raise ValueError("Transition is longer than an encoded segment")
        filter_graph, video_label, audio_label, timeline = build_crossfade_filter(
            frame_counts, frame_rate, transition_frames
        )
        command = [find_ffmpeg(), "-hide_banner", "-loglevel", "error"]
        for segment in segments:
            command.extend(["-i", str(segment)])
        command.extend(
            [
                "-filter_complex",
                filter_graph,
                "-map",
                f"[{video_label}]",
                "-map",
                f"[{audio_label}]",
                "-t",
                f"{min(plan['target_seconds'], timeline):.6f}",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-ar",
                "32000",
                "-movflags",
                "+faststart",
                str(final_path),
            ]
        )
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg crossfade failed: {result.stderr.strip()}")

        manifest = {
            "job_name": plan["job_name"],
            "target_seconds": plan["target_seconds"],
            "segments": [str(path) for path in segments],
            "transition_frames": transition_frames,
            "final_video": str(final_path),
        }
        final_path.with_suffix(".json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        relative = final_path.relative_to(output_root)
        preview = {
            "filename": final_path.name,
            "subfolder": relative.parent.as_posix(),
            "type": "output",
            "format": "video/h264-mp4",
            "frame_rate": 24,
            "fullpath": str(final_path),
        }
        return {
            "ui": {"gifs": [preview]},
            "result": ((True, [str(final_path)]),),
        }


NODE_CLASS_MAPPINGS = {
    "OneKAspectRatio": OneKAspectRatio,
    "H3LongVideoPlan": H3LongVideoPlan,
    "H3LongVideoStep": H3LongVideoStep,
    "H3LongVideoAssemble": H3LongVideoAssemble,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "OneKAspectRatio": "比例预设",
    "H3LongVideoPlan": "H3 Long Video Plan",
    "H3LongVideoStep": "H3 Long Video Step",
    "H3LongVideoAssemble": "H3 Long Video Assemble",
}
