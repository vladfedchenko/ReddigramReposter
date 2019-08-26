"""Utility functions."""
import filetype
import os
import subprocess


class DownloadManager:

    @staticmethod
    def download_media(download_url: str, file_path: str, default_extension: str) -> str:
        """Download a file to a specified location.

        Args:
            download_url: URL to download the file from.
            file_path: Location to where to store the file.
            default_extension: Default extension of the file

        Returns:
            str: Actual location of the saved file.
        """
        subprocess.run(['wget', download_url, '-O', file_path, '-q'])
        kind = filetype.guess(file_path)
        new_name = f"{file_path}.{default_extension}"
        if kind is not None:
            new_name = f"{file_path}.{kind.extension}"
        os.rename(file_path, new_name)
        return new_name
