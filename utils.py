import configparser
import logging
import os
import sys

import appdirs

logger = logging.getLogger("photoeditor.utils")


def get_user_config_path():
    """Get path for config.ini"""
    user_config_dir = appdirs.user_config_dir("Photoed", "YourCompany")
    if not os.path.exists(user_config_dir):
        os.makedirs(user_config_dir)
    return os.path.join(user_config_dir, "config.ini")

def resource_path(relative_path):
    """Get absolute path to resource"""
    if hasattr(sys, '_MEIPASS'):
        # If run from .exe, than use temporary folder PyInstaller
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def load_config():
    """Load settings from config.ini"""
    config = configparser.ConfigParser()
    # Сначала пытаемся загрузить из пользовательской директории
    user_config_path = get_user_config_path()
    logger.debug("User config path: %s", user_config_path)
    if os.path.exists(user_config_path):
        logger.debug("Loading user config...")
        config.read(user_config_path)
    else:
        # Если пользовательского файла нет, пытаемся загрузить из ресурсов
        default_config_path = resource_path("config.ini")
        logger.debug("Default config path: %s", default_config_path)
        if os.path.exists(default_config_path):
            logger.debug("Loading default config...")
            config.read(default_config_path)

        # Добавляем секции, если их нет
        if 'General' not in config:
            logger.debug("Adding default General section...")
            config['General'] = {
                'theme': 'dark',
                'window_width': '800',
                'window_height': '600'
            }
        if 'Editor' not in config:
            logger.debug("Adding default Editor section...")
            config['Editor'] = {
                'default_zoom': '1.0',
                'show_rulers': 'true'
            }
        if 'RecentFiles' not in config:
            logger.debug("Adding default RecentFiles section...")
            config['RecentFiles'] = {}
        # Сохраняем в пользовательскую директорию
        save_config(config)
    return config

def save_config(config):
    """Сохранить настройки в config.ini в пользовательской директории"""
    config_path = get_user_config_path()  # Используем ту же директорию, что и в load_config
    logger.debug("Saving config to: %s", config_path)
    try:
        with open(config_path, 'w') as configfile:
            config.write(configfile)
    except Exception as e:
        logger.exception("Failed to save config: %s", e)


def add_recent_file(config, file_path):
    """Добавить файл в список недавних файлов (максимум 5)."""
    if not file_path or not os.path.exists(file_path):
        return

    # Получаем текущий список недавних файлов
    recent_files = []
    if 'RecentFiles' in config:
        recent_files = [config['RecentFiles'].get(f'file{i}', '') for i in range(1, 6)]
        recent_files = [f for f in recent_files if f]  # Удаляем пустые записи

    # Удаляем файл из списка, если он уже есть
    if file_path in recent_files:
        recent_files.remove(file_path)

    # Добавляем файл в начало списка
    recent_files.insert(0, file_path)

    # Ограничиваем список 5 файлами
    recent_files = recent_files[:5]

    # Обновляем секцию RecentFiles
    config['RecentFiles'] = {f'file{i+1}': path for i, path in enumerate(recent_files)}
    # Примечание: вызывающая сторона (MainWindow.openFile) сохраняет конфиг сразу после вызова

def get_recent_files(config):
    """Получить список недавних файлов."""
    if 'RecentFiles' not in config:
        return []
    recent_files = [config['RecentFiles'].get(f'file{i}', '') for i in range(1, 6)]
    # Фильтруем только существующие файлы
    return [f for f in recent_files if f and os.path.exists(f)]
