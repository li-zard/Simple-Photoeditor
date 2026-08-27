"""Тесты утилит MRU (недавние файлы) — этап 4 роадмапа.

Проверяются: порядок (свежие сверху), дедупликация, лимит 5 записей,
фильтрация несуществующих путей.
"""

import configparser

from utils import add_recent_file, get_recent_files


def _touch(path):
    path.write_text("x")
    return str(path)


def _config():
    config = configparser.ConfigParser()
    config["RecentFiles"] = {}
    return config


class TestAddRecentFile:
    def test_first_file_added(self, tmp_path):
        config = _config()
        a = _touch(tmp_path / "a.png")

        add_recent_file(config, a)

        assert get_recent_files(config) == [a]

    def test_most_recent_first(self, tmp_path):
        config = _config()
        a = _touch(tmp_path / "a.png")
        b = _touch(tmp_path / "b.png")
        c = _touch(tmp_path / "c.png")

        add_recent_file(config, a)
        add_recent_file(config, b)
        add_recent_file(config, c)

        assert get_recent_files(config) == [c, b, a]

    def test_dedup_moves_to_top(self, tmp_path):
        config = _config()
        a = _touch(tmp_path / "a.png")
        b = _touch(tmp_path / "b.png")

        add_recent_file(config, a)
        add_recent_file(config, b)
        add_recent_file(config, a)  # повторное открытие

        assert get_recent_files(config) == [a, b]

    def test_limit_five_drops_oldest(self, tmp_path):
        config = _config()
        paths = [_touch(tmp_path / f"{i}.png") for i in range(7)]

        for p in paths:
            add_recent_file(config, p)

        recent = get_recent_files(config)
        assert len(recent) == 5
        assert recent == [paths[6], paths[5], paths[4], paths[3], paths[2]]
        # Самые старые вытеснены
        assert paths[0] not in recent
        assert paths[1] not in recent

    def test_nonexistent_path_ignored(self, tmp_path):
        config = _config()
        existing = _touch(tmp_path / "real.png")
        missing = str(tmp_path / "missing.png")

        add_recent_file(config, missing)
        assert get_recent_files(config) == []

        add_recent_file(config, existing)
        add_recent_file(config, missing)
        assert get_recent_files(config) == [existing]

    def test_empty_path_ignored(self, tmp_path):
        config = _config()
        add_recent_file(config, "")
        assert get_recent_files(config) == []

    def test_keys_written_as_file1_to_file5(self, tmp_path):
        config = _config()
        a = _touch(tmp_path / "a.png")
        b = _touch(tmp_path / "b.png")

        add_recent_file(config, a)
        add_recent_file(config, b)

        section = config["RecentFiles"]
        assert section["file1"] == b
        assert section["file2"] == a


class TestGetRecentFiles:
    def test_filters_nonexistent(self, tmp_path):
        config = _config()
        existing = _touch(tmp_path / "exists.png")
        config["RecentFiles"] = {
            "file1": existing,
            "file2": str(tmp_path / "deleted.png"),
        }

        assert get_recent_files(config) == [existing]

    def test_empty_when_no_section(self):
        config = configparser.ConfigParser()
        assert get_recent_files(config) == []

    def test_empty_section(self):
        config = _config()
        assert get_recent_files(config) == []
