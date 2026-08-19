import importlib.util
from pathlib import Path


def load_nodes_module():
    path = Path(__file__).with_name("nodes.py")
    spec = importlib.util.spec_from_file_location("h3_long_video_nodes", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_prompt_parsing_and_names():
    nodes = load_nodes_module()
    assert nodes.parse_prompt_blocks('["one", "two"]') == ["one", "two"]
    assert nodes.parse_prompt_blocks("one\n---SEGMENT---\ntwo") == ["one", "two"]
    assert nodes.safe_job_name(" 30 秒测试 ") == "30_秒测试"

    plan, count, _ = nodes.H3LongVideoPlan().build(
        '["one", "two"]', "check", 4.0, 2
    )
    prompt, prefix, number = nodes.H3LongVideoStep().select(plan, 1)

    assert count == 2
    assert prompt == "two"
    assert prefix == "h3_long/check/segment_002"
    assert number == 2
    assert plan["target_seconds"] == 8.0

    graph, video, audio, duration = nodes.build_crossfade_filter([124, 124, 124], 24, 3)
    assert "xfade=transition=fade:duration=0.125000:offset=5.041667" in graph
    assert "acrossfade=d=0.125000" in graph
    assert video == "vx2"
    assert audio == "ax2"
    assert round(duration, 3) == 15.25

    assert nodes.OneKAspectRatio().select("2:3", "1K 1024 x 1024") == (683, 1024)
    assert nodes.OneKAspectRatio().select("9:16", "1K 1024 x 1024") == (576, 1024)
    assert nodes.OneKAspectRatio().select("4:3", "2K 2048 x 2048") == (2048, 1536)
    assert nodes.OneKAspectRatio().select("1:1", "4K 4096 x 4096") == (4096, 4096)


if __name__ == "__main__":
    test_prompt_parsing_and_names()
    print("H3 long-video node self-check passed")
