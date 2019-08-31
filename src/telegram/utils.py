"""This module contains different utilities to make it easier to interface with telegram."""
from typing import Optional


class TelegramHelper:
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

        return local['path'] if local is not None else None
