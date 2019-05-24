"""
A module containing an object that wraps the C td_json_client object and provides a Python interface to access some of
its methods.
"""
from ctypes.util import find_library
from ctypes import *
from enum import Enum
import json
import logging
import os
import platform
import threading
import time
from typing import List, Tuple


def on_fatal_error_callback(error_message: str):
    """A function to handle TDLib JSON library fatal errors

    Args:
        error_message: Received error message.
    """
    logging.critical(f"TDLib JSON library returned with an error: {error_message}.")


class TelegramAuthError(Exception):
    """Error raised in case of Telegram authentication error"""


class TelegramAlbumMediaType(Enum):
    """Media types supported in album messages
    """
    IMAGE = 1
    VIDEO = 2


class TelegramMediaType(Enum):
    """Media types supported in media messages
    """
    IMAGE = TelegramAlbumMediaType.IMAGE
    VIDEO = TelegramAlbumMediaType.VIDEO
    ANIMATION = 3
    DOCUMENT = 4


class TelegramWrapper:
    """Object to access td_json_client methods via Python code.
    """
    _client_create = None
    _client_receive = None
    _client_send = None
    _client_execute = None
    _client_destroy = None

    _client = None

    _chat_id_map = None
    _chat_id_map_lock = None
    _receive_handler_thread = None
    _receive_handler_stop = None

    def _td_client_send(self, query):
        query = json.dumps(query).encode('utf-8')
        self._client_send(self._client, query)

    def _td_client_receive(self):
        result = self._client_receive(self._client, 1.0)
        if result:
            result = json.loads(result.decode('utf-8'))
        return result

    def _td_client_execute(self, query):
        query = json.dumps(query).encode('utf-8')
        result = self._client_execute(self._client, query)
        if result:
            result = json.loads(result.decode('utf-8'))
        return result

    def _td_receive_handler(self):
        logging.debug(f"TDLib JSON message receiver thread started.")
        while not self._receive_handler_stop.is_set():
            event = self._td_client_receive()

            if event:
                # In the next section all of incoming messages should be processed
                # print(event)
                if event['@type'] == 'updateNewChat':
                    chat_title = event['chat']['title']
                    chat_id = event['chat']['id']
                    logging.debug(f"TDLib JSON: chat ID saved: {chat_title}:{chat_id}")
                    with self._chat_id_map_lock:
                        self._chat_id_map[chat_title] = chat_id

    @staticmethod
    def _get_media_fie_content(media_path: str, media_type: TelegramMediaType, caption: str = ""):
        media = {'@type': 'inputFileLocal', 'path': media_path}
        if media_type == TelegramMediaType.ANIMATION:
            content = {'@type': 'inputMessageAnimation', 'animation': media, 'caption': {'text': caption}}
        elif media_type == TelegramMediaType.IMAGE:
            content = {'@type': 'inputMessagePhoto', 'photo': media, 'caption': {'text': caption}}
        elif media_type == TelegramMediaType.DOCUMENT:
            content = {'@type': 'inputMessageDocument', 'document': media, 'caption': {'text': caption}}
        else:
            content = {'@type': 'inputMessageVideo',
                       'video': media,
                       'caption': {'text': caption},
                       'supports_streaming': True}
        return content

    def __init__(self,
                 tdlib_api_id: int,
                 tdlib_api_hash: str,
                 tdlib_allow_input: bool = True,
                 tdlib_auth_info: map = None,
                 tdlib_database_directory: str = "tdlib_db",
                 tdlib_auth_timeout: int = 10,
                 tdlib_log_verbosity: int = 0,
                 tdlib_log_file: str = None,
                 tdlib_log_max_size: int = 10):
        """Initialize TelegramWrapper object.

        Args:
            tdlib_api_id: Application identifier for Telegram API access, which can be obtained
                at https://my.telegram.org.
            tdlib_api_hash: Application identifier hash for Telegram API access, which can be obtained
                at https://my.telegram.org.
            tdlib_allow_input: If True - user will be able to enter authentication info through the console.
                If False - authentication info is retrieved from tdlib_auth_info dictionary.
                Note: if MFA is enabled the input of authentication code is expected on first login.
            tdlib_auth_info: Dictionary of authentication parameters.
                Expected to contain 'phone' and 'password' key-value pairs.
            tdlib_database_directory: Location of the directory to store TDLib data.
            tdlib_auth_timeout: Amount of time in seconds to wait for authentication confirmation.
            tdlib_log_verbosity: Log verbosity level for TDLib JSON library. Range: [0-5+].
            tdlib_log_file: TDLib JSON library log file location.
            tdlib_log_max_size: TDLib JSON library log file max size (in MB).

        Raises:
            ModuleNotFoundError: Cannot locate the TDLib JSON library.
            TelegramAuthError: Authentication error encountered.
        """
        module_dir = os.path.dirname(__file__)
        tdjson_path = find_library('tdjson') or f"{module_dir}/lib/{platform.uname()[4]}/libtdjson.so"
        logging.debug(f"Loading TDLib JSON with this location: {tdjson_path}")

        if tdjson_path is None:
            logging.critical("TDLib JSON library not found. Cannot initialize TelegramWrapper object.")
            raise ModuleNotFoundError("TDLib JSON library not found. Cannot initialize TelegramWrapper object.")
        tdjson = CDLL(tdjson_path)
        logging.info("TDLib JSON lib loaded successfully.")

        self._client_create = tdjson.td_json_client_create
        self._client_create.restype = c_void_p
        self._client_create.argtypes = []

        self._client_receive = tdjson.td_json_client_receive
        self._client_receive.restype = c_char_p
        self._client_receive.argtypes = [c_void_p, c_double]

        self._client_send = tdjson.td_json_client_send
        self._client_send.restype = None
        self._client_send.argtypes = [c_void_p, c_char_p]

        self._client_execute = tdjson.td_json_client_execute
        self._client_execute.restype = c_char_p
        self._client_execute.argtypes = [c_void_p, c_char_p]

        self._client_destroy = tdjson.td_json_client_destroy
        self._client_destroy.restype = None
        self._client_destroy.argtypes = [c_void_p]

        # Error callback handling
        fatal_error_callback_type = CFUNCTYPE(None, c_char_p)
        td_set_log_fatal_error_callback = tdjson.td_set_log_fatal_error_callback
        td_set_log_fatal_error_callback.restype = None
        td_set_log_fatal_error_callback.argtypes = [fatal_error_callback_type]
        c_on_fatal_error_callback = fatal_error_callback_type(on_fatal_error_callback)
        td_set_log_fatal_error_callback(c_on_fatal_error_callback)

        # setting low verbosity level before client is created
        self._td_client_execute({'@type': 'setLogVerbosityLevel',
                                          'new_verbosity_level': 0})

        self._client = self._client_create()
        logging.info("TDLib JSON client created.")

        # TDLib JSON logging handling
        result = self._td_client_execute({'@type': 'setLogVerbosityLevel',
                                          'new_verbosity_level': tdlib_log_verbosity})
        if result and result['@type'] == 'ok':
            logging.info(f"TDLib JSON log verbosity changed to {tdlib_log_verbosity}.")
        else:
            logging.warning(f"TDLib JSON log verbosity change not confirmed.")

        if tdlib_log_file is not None:
            log_stream_file = {'@type': 'logStreamFile', 'path': tdlib_log_file, 'max_file_size': tdlib_log_max_size}
            result = self._td_client_execute({'@type': 'setLogStream',
                                              'log_stream': tdlib_log_file})
            if result and result['@type'] == 'ok':
                logging.info(f"TDLib JSON log location changed to {log_stream_file}.")
            else:
                logging.warning(f"TDLib JSON log location change not confirmed.")

        # TDLib JSON authentication handling
        logging.debug(f"TDLib JSON authentication stage started.")
        countdown_start = time.time()
        authenticated = False
        while time.time() - countdown_start <= tdlib_auth_timeout:
            event = self._td_client_receive()

            if event and event['@type'] == 'updateAuthorizationState':
                auth_state = event['authorization_state']

                if auth_state['@type'] == 'authorizationStateWaitTdlibParameters':
                    self._td_client_send({'@type': 'setTdlibParameters', 'parameters': {
                                              'database_directory': tdlib_database_directory,
                                              'api_id': tdlib_api_id,
                                              'api_hash': tdlib_api_hash,
                                              'system_language_code': 'en',
                                              'device_model': 'Desktop',
                                              'system_version': 'Linux',
                                              'application_version': '0.1',
                                              'enable_storage_optimizer': True}})

                if auth_state['@type'] == 'authorizationStateWaitEncryptionKey':
                    self._td_client_send({'@type': 'checkDatabaseEncryptionKey', 'key': 'my_key'})

                if auth_state['@type'] == 'authorizationStateWaitPhoneNumber':
                    if tdlib_auth_info is not None and 'phone' in tdlib_auth_info:
                        phone_number = tdlib_auth_info['phone']
                    elif tdlib_allow_input:
                        phone_number = input('Please insert your phone number: ')
                        countdown_start = time.time()  # countdown is reset if user input is expected
                    else:
                        logging.error("TDLib JSON: phone number is requested but not provided.")
                        raise TelegramAuthError("TDLib JSON: phone number is requested but not provided.")

                    self._td_client_send({'@type': 'setAuthenticationPhoneNumber', 'phone_number': phone_number})

                if auth_state['@type'] == 'authorizationStateWaitCode':
                    if tdlib_allow_input:
                        code = input('Please insert the authentication code you received: ')
                        countdown_start = time.time()  # countdown is reset if user input is expected
                    else:
                        logging.error("TDLib JSON: authentication code is requested but not provided.")
                        raise TelegramAuthError("TDLib JSON: authentication code is requested but not provided.")
                    self._td_client_send({'@type': 'checkAuthenticationCode', 'code': code})

                if auth_state['@type'] == 'authorizationStateWaitPassword':
                    if tdlib_auth_info is not None and 'password' in tdlib_auth_info:
                        password = tdlib_auth_info['password']
                    elif tdlib_allow_input:
                        password = input('Please insert your password: ')
                        countdown_start = time.time()  # countdown is reset if user input is expected
                    else:
                        logging.error("TDLib JSON: password is requested but not provided.")
                        raise TelegramAuthError("TDLib JSON: password is requested but not provided.")

                    self._td_client_send({'@type': 'checkAuthenticationPassword', 'password': password})

                if auth_state['@type'] == 'authorizationStateReady':
                    authenticated = True
                    logging.info(f"TDLib JSON client authenticated.")
                    break

        if not authenticated:
            logging.error("TDLib JSON client authentication unknown error.")
            raise TelegramAuthError("TDLib JSON client authentication unknown error.")

        logging.debug(f"TDLib JSON message receiver thread initialization.")
        self._chat_id_map = {}
        self._chat_id_map_lock = threading.Lock()
        self._receive_handler_stop = threading.Event()
        self._receive_handler_thread = threading.Thread(target=self._td_receive_handler, args=())
        self._receive_handler_thread.start()
        logging.info(f"TDLib JSON message receiver thread initialization finished.")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._receive_handler_stop is not None:
            self._receive_handler_stop.set()
            self._receive_handler_thread.join()

    # Public methods
    def update_chat_ids(self, limit: int = 1000):
        """Update the list of chat IDs. It is needed for successful send_text_message execution with only chat title
        specified.

        Args:
            limit: Max number of chats to be received. Most recent chats will be received.
        """
        self._td_client_send({'@type': 'getChats', 'limit': limit})

    def send_text_message(self, text: str, **kwargs) -> bool:
        """Send a text message to a chat specified by either a chat id or chat title.

        Args:
            text: Text to send.
            **chat_id (int): ID of the target chat.
            **chat_title (str): Title of the target chat.
                Use this option only after executing update_chat_ids at least once.
        Returns:
            bool: True if the message is sent. False otherwise. Delivery is not guaranteed.
        """
        chat_id = None
        if 'chat_id' in kwargs:
            chat_id = kwargs['chat_id']
        elif 'chat_title' in kwargs:
            with self._chat_id_map_lock:
                if kwargs['chat_title'] in self._chat_id_map:
                    chat_id = self._chat_id_map[kwargs['chat_title']]

        if chat_id is not None:
            logging.debug(f"Sending the next text message: {text} to chat id {chat_id}.")
            content = {'@type': 'inputMessageText', 'text': {'text': text}}
            self._td_client_send({'@type': 'sendMessage', 'chat_id': chat_id, 'input_message_content': content})
            return True
        else:
            return False

    def send_media_message(self,
                           media_path: str,
                           media_type: TelegramMediaType = TelegramMediaType.IMAGE,
                           **kwargs) -> bool:
        """Send a media message to a chat specified by either a chat id or chat title.

        Args:
            media_path: Path to a media file.
            media_type: Type of media file.
            **caption (str): Caption for an image.
            **chat_id (int): ID of the target chat.
            **chat_title (str): Title of the target chat.
                Use this option only after executing update_chat_ids at least once.
        Returns:
            bool: True if the message is sent. False otherwise. Delivery is not guaranteed.
        """
        chat_id = None
        if 'chat_id' in kwargs:
            chat_id = kwargs['chat_id']
        elif 'chat_title' in kwargs:
            with self._chat_id_map_lock:
                if kwargs['chat_title'] in self._chat_id_map:
                    chat_id = self._chat_id_map[kwargs['chat_title']]

        if chat_id is not None:
            logging.debug(f"Sending the next media message: {media_path} to chat id {chat_id}.")
            caption_text = kwargs['caption'] if 'caption' in kwargs else ''
            content = TelegramWrapper._get_media_fie_content(media_path, media_type, caption_text)
            self._td_client_send({'@type': 'sendMessage', 'chat_id': chat_id, 'input_message_content': content})
            return True
        else:
            return False

    def send_album_message(self, media_list: List[Tuple[str, TelegramAlbumMediaType, str]], **kwargs) -> bool:
        """Send an media album message to a chat specified by either a chat id or chat title.

        Args:
            media_list: A list of media files. Each media file is a Tuple consisting of path, media type and a caption.
            **chat_id (int): ID of the target chat.
            **chat_title (str): Title of the target chat.
                Use this option only after executing update_chat_ids at least once.
        Returns:
            bool: True if the message is sent. False otherwise. Delivery is not guaranteed.
        """
        chat_id = None
        if 'chat_id' in kwargs:
            chat_id = kwargs['chat_id']
        elif 'chat_title' in kwargs:
            with self._chat_id_map_lock:
                if kwargs['chat_title'] in self._chat_id_map:
                    chat_id = self._chat_id_map[kwargs['chat_title']]

        if chat_id is not None:
            logging.debug(f"Sending the album message of {len(media_list)} entities to chat id {chat_id}.")
            contents = [TelegramWrapper._get_media_fie_content(x[0], TelegramMediaType(x[1]), x[2]) for x in media_list]
            self._td_client_send({'@type': 'sendMessageAlbum', 'chat_id': chat_id, 'input_message_contents': contents})
            return True
        else:
            return False
