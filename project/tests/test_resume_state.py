from pathlib import Path

from app.progress import init_state, load_state, save_state


def test_progress_resume(tmp_path: Path):
    p = tmp_path / "progress.json"
    st = init_state(p, "2020-05-20", "2020-05-22", 3)
    st.done_days = 1
    save_state(p, st)
    st2 = load_state(p)
    assert st2 is not None
    assert st2.done_days == 1

