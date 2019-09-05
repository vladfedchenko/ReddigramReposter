"""This module contains different utilities to make it easier to interface with telegram."""
import os
from typing import Optional
from telegram.telegram_wrapper import TelegramMediaType


class TelegramHelper:
    @staticmethod
    def determine_media_type(file_path: str) -> TelegramMediaType:
        """Determine the type of media of a file based on its extension.

        Args:
            file_path: Path to media file.
        Returns:
            TelegramMediaType: Media type based on file extension. If extension not recognized - DOCUMENT type returned.
        """
        ext = os.path.splitext(file_path)[1][1:]
        ret_type = TelegramMediaType.DOCUMENT
        if ext == 'gif':
            ret_type = TelegramMediaType.ANIMATION
        elif ext == 'jpg' or ext == 'png':
            ret_type = TelegramMediaType.IMAGE
        elif ext == 'mp4' or ext == 'avi' or ext == 'webm':
            ret_type = TelegramMediaType.VIDEO
        return ret_type

    @staticmethod
    def extract_media_path(message: dict) -> Optional[str]:
        """Extract media file location, if available, from a telegram message.

        Args:
            message: Message with media. messagePhoto, messageVideo, messageAnimation, messageAudio, messageDocument
                types are supported.
        Returns:
            str or None: Path to a media file if exists.
        """
        local = None
        if message['content']['@type'] == 'messagePhoto':
            photo = message['content']['photo']
            for photo_size in photo['sizes']:
                if photo_size['type'] == 'i':
                    local = photo_size['photo']['local']

        elif message['content']['@type'] == 'messageVideo':
            video = message['content']['video']
            local = video['video']['local']

        elif message['content']['@type'] == 'messageAnimation':
            animation = message['content']['animation']
            local = animation['animation']['local']

        elif message['content']['@type'] == 'messageDocument':
            document = message['content']['document']
            local = document['document']['local']

        elif message['content']['@type'] == 'messageAudio':
            audio = message['content']['audio']
            local = audio['audio']['local']

        return local['path'] if local is not None and len(local['path']) > 0 else None
